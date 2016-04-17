# lxnstack is a program to align and stack atronomical images
# Copyright (C) 2013-2015  Maurizio D'Addona <mauritiusdadd@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import paths
import time
import subprocess
import errno
import ctypes
import select
import mmap
from fcntl import ioctl

import cv2
import numpy as np
from PyQt4 import Qt, QtCore, QtGui, uic

import translation as tr
import utils
import videodev2 as v4l2
import log
import logging


def listVideoDevices():
    vd_list = _list_v4l2_devices()
    vd_list += _list_cv2_devices()
    return vd_list


class GenericVideoDevice(Qt.QObject):
    # Generic capture interface
    # (parent object of all video capture interfaces)

    newFrameReady = QtCore.pyqtSignal()
    locked = QtCore.pyqtSignal()
    unlocked = QtCore.pyqtSignal()
    lockStateChanged = QtCore.pyqtSignal(bool)

    def __init__(self):
        Qt.QObject.__init__(self)
        self.name = ""
        self._control_ui = None
        self.resetDeviceInfo()
        self._info_ui = None
        self.lastframe = None
        self._locked = False

    def __del__(self):
        try:
            self.close()
        except NotImplementedError:
            pass

    def __str__(self):
        if self._device_info['bus id']:
            fmtstr = "{0} - {1} ({2}) with driver: \'{3} [{4}]\'"
        else:
            fmtstr = "{0} - {1} with driver: \'{3} [{4}]\'"
        return fmtstr.format(self._device_info['device file'],
                             self._device_info['device name'],
                             self._device_info['bus id'],
                             self._device_info['driver backend'],
                             self._device_info['driver version'])

    def shortinfo(self):

        if self._device_info['bus id']:
            fmtstr = "{0} ({1}) [{2}]"
        else:
            fmtstr = "{0} [{2}]"

        return fmtstr.format(self._device_info['device name'],
                             self._device_info['bus id'],
                             self._device_info['driver backend'])

    def resetDeviceInfo(self):
        self._device_info = {'device file': "",
                             'device name': "",
                             'bus id': "",
                             'driver backend': "",
                             'driver version': ""}

    def getName(self):
        return self.name

    def open(self):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def isOpened(self):
        raise NotImplementedError()

    def getFrameRate(self):
        raise NotImplementedError()

    def getFrame(self):
        raise NotImplementedError()

    def getLastFrame(self):
        return self.lastframe

    def setFrameRate(self):
        raise NotImplementedError()

    def setFrameSize(self):
        raise NotImplementedError()

    def setPixelFormat(self):
        raise NotImplementedError()

    def showDeviceInfo(self):
        if isinstance(self.getDeviceInfo(), QtCore.QObject):
            self._info_ui.show()

    def getDeviceInfo(self, ui=True):
        if ui and Qt.QApplication.instance():
            return self._update_device_info_ui()
        else:
            return self._device_info

    def getControlUI(self):
        return self._control_ui

    def showControlUI(self):
        if isinstance(self._control_ui, QtCore.QObject):
            self._control_ui.show()

    def isLocked(self):
        return self._locked

    def requestLock(self):

        log.log(repr(self),
                "Requesting exclusive lock for the device \'" +
                self.shortinfo()+"\'",
                level=logging.DEBUG)

        if utils.timeouted_loop(self.isLocked,
                                timeout=1,
                                t_step=0.1,
                                c_val=False):

            if self._control_ui is not None:
                fmt_menu = self._control_ui.findChild(QtGui.QComboBox,
                                                      "format menu")
                if fmt_menu is not None:
                    fmt_menu.setEnabled(False)

                frm_menu = self._control_ui.findChild(QtGui.QComboBox,
                                                      "size menu")
                if frm_menu is not None:
                    frm_menu.setEnabled(False)

                fps_menu = self._control_ui.findChild(QtGui.QComboBox,
                                                      "framerate menu")
                if fps_menu is not None:
                    fps_menu.setEnabled(False)

            log.log(repr(self),
                    "Exclusive lock established for the device \'" +
                    self.shortinfo()+"\'",
                    level=logging.DEBUG)

            self._locked = True
            self.locked.emit()
            self.lockStateChanged.emit(True)
            return True

        else:

            log.log(repr(self),
                    "Cannot establish exclusive lock for the device \'" +
                    self.shortinfo()+"\': device already locked",
                    level=logging.WARNING)
        return False

    def requestUnlock(self):

        log.log(repr(self),
                "Removing exclusive lock for the device \'" +
                self.shortinfo()+"\'",
                level=logging.DEBUG)

        if self._control_ui is not None:

            fmt_menu = self._control_ui.findChild(QtGui.QComboBox,
                                                  "format menu")
            if fmt_menu is not None:
                fmt_menu.setEnabled(True)

            frm_menu = self._control_ui.findChild(QtGui.QComboBox,
                                                  "size menu")
            if frm_menu is not None:
                frm_menu.setEnabled(True)

            fps_menu = self._control_ui.findChild(QtGui.QComboBox,
                                                  "framerate menu")
            if fps_menu is not None:
                fps_menu.setEnabled(True)

        self.unlocked.emit()
        self.lockStateChanged.emit(False)
        self._locked = False
        return True

    def _build_ui_controls_interface(self):
        if Qt.QApplication.instance():
            self._qt_build_ui_controls_interface()
        else:
            self._control_ui = None

    def _update_device_info_ui(self):
        if self._info_ui is None:
            self._info_ui = Qt.QWidget()
            layout = QtGui.QGridLayout()
            self._info_ui.setLayout(layout)
        else:
            layout = self._info_ui.layout()

        for old_label in self._info_ui.findChildren(QtGui.QLabel):
            old_label.setParent(None)
            del old_label

        row = 0
        for key in self._device_info.keys():
            label1 = Qt.QLabel(str(key)+":")
            label2 = Qt.QLabel(str(self._device_info[key]))
            layout.addWidget(label1, row, 0)
            layout.addWidget(label2, row, 2)
            row += 1

        return self._info_ui


class V4l2VideoDevice(GenericVideoDevice):
    # v4l2 video capture interface

    """
    Video4Linux2 userspace API

    The informations used to write this code are taken from:

    * http://linuxtv.org/downloads/v4l-dvb-apis/
    * http://linuxtv.org/downloads/v4l-dvb-apis/capture-example.html
    * http://linuxtv.org/downloads/v4l-dvb-apis/v4l2grab-example.html
    * http://linuxtv.org/downloads/v4l-dvb-apis/control.html
    """

    MEMORY_READ = 0
    MEMORY_MMAP = 1
    MEMORY_USERPTR = 2

    supported_pixel_formats = [v4l2.V4L2_PIX_FMT_RGB32,
                               v4l2.V4L2_PIX_FMT_RGB24,
                               v4l2.V4L2_PIX_FMT_BGR32,
                               v4l2.V4L2_PIX_FMT_BGR24]

    def __init__(self):
        GenericVideoDevice.__init__(self)
        self._fd = None
        self._reopening = False
        self._device_filename = ''
        self._devindex = None
        self._io = None
        self._n_userp_buff = 4
        self._buffers = {}
        self._timeout = 2.0
        self._format = None
        self._capture_capability = 0
        self._capture_controls = {v4l2.V4L2_CTRL_CLASS_USER: []}
        self._is_streaming = False
        self._cap_field = v4l2.V4L2_FIELD_NONE  # V4L2_FIELD_INTERLACED
        self._available_reading_modes = {}
        self._available_pixel_format = {}

    def open(self, device=None, mode=None, pixfmt=None):

        """
        opens the device-file 'device' using the reading mode 'mode'

        the reading mode can be self.MEMORY_MMAP, self.MEMORY_READ
        or self.MEMORY_USERPTR. Note that not all methods may be supported
        by your device. You can obtain a list of supported methos by calling
        the function 'getAvailableReadingModes()'
        """

        if device is None:
            if self._device_filename:
                return self._reopen()
            else:
                raise ValueError("No device specified!")

        if self.isOpened():
            self.close()

        self._device_filename = device
        try:
            if v4l2.HAS_LIBV4L2:
                self._fd = v4l2.v4l2_open(device, os.O_RDWR)
            else:
                self._fd = os.open(device, os.O_RDWR)
        except Exception:
            return False

        if not self._reopening:
            cap = v4l2.v4l2_capability()
            cropcap = v4l2.v4l2_cropcap()
            crop = v4l2.v4l2_crop()

            r, err = self._xioctl(v4l2.VIDIOC_QUERYCAP, cap)
            if (r == -1):
                if (err == errno.EINVAL):
                    log.log(repr(self),
                            self._device_filename+"is not a V4L2 device",
                            level=logging.WARNING)
                    return False
                else:
                    return False

            if (not (cap.capabilities & v4l2.V4L2_CAP_VIDEO_CAPTURE)):
                log.log(repr(self),
                        self._device_filename+"is no video capture device",
                        level=logging.WARNING)
                return False

            if (not (cap.capabilities & v4l2.V4L2_CAP_READWRITE)):
                log.log(repr(self),
                        self._device_filename+"does not support read i/o",
                        level=logging.WARNING)
                can_read = False
            else:
                mods = 'userspace char buffers'
                self._available_reading_modes[self.MEMORY_READ] = mods
                can_read = True

            if (not (cap.capabilities & v4l2.V4L2_CAP_STREAMING)):
                log.log(repr(self),
                        self._device_filename+"does not support streaming i/o",
                        level=logging.WARNING)
                can_stream = False
                return False
            else:
                can_stream = True
                mods1 = 'userspace memory mapping'
                mods2 = 'userspace pointer'
                self._available_reading_modes[self.MEMORY_MMAP] = mods1
                self._available_reading_modes[self.MEMORY_USERPTR] = mods2

            # self._clear(cropcap)

            self._device_driver_name = cap.driver
            self._device_name = cap.card
            self._device_bus = cap.bus_info
            self._device_driver_version = "{0:d}.{1:d}.{2:d}".format(
                (cap.version >> 16) & 255,
                (cap.version >> 8) & 255,
                cap.version & 255)

            self.resetDeviceInfo()
            self._device_info['device name'] = self._device_name
            self._device_info['device file'] = self._device_filename
            self._device_info['bus id'] = self._device_bus
            self._device_info['driver backend'] = 'video4linux v2'
            self._device_info['driver name'] = self._device_driver_name
            self._device_info['driver version'] = self._device_driver_version
            self._device_info['support straming'] = can_stream
            self._device_info['support read/write'] = can_read

            cropcap.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE

            if (0 == self._xioctl(v4l2.VIDIOC_CROPCAP, cropcap)[0]):
                crop.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
                crop.c = cropcap.defrect  # reset to default

                if (-1 == self._xioctl(v4l2.VIDIOC_S_CROP, crop)[0]):
                    log.log(repr(self),
                            "Cropping not supported",
                            level=logging.WARNING)
                    self._device_info['support cropping'] = False
                else:
                    self._device_info['support cropping'] = True
            else:
                self._device_info['support cropping'] = False
                pass

            if self._get_capture_param() is None:
                return False
        else:
            mode = self._io

        if mode is None:
            # automatically detect working method
            if can_stream:
                self._io = self.MEMORY_MMAP
                if not self._init_device(pixfmt):
                    self._io = self.MEMORY_USERPTR
                    if not self._init_device(pixfmt):
                        log.log(repr(self),
                                "Error in device initializazion! " +
                                "(MEMORY_MMAP)",
                                level=logging.ERROR)
                        return False
            elif can_read:
                self._io = self.MEMORY_READ
                if not self._init_device(pixfmt):
                    log.log(repr(self),
                            "Error in device initializazion! (MEMORY_READ)",
                            level=logging.ERROR)
                    return False
            else:
                log.log(repr(self),
                        "Cannot open the device " + device +
                        ": wrong or not supported reading mode!",
                        level=logging.ERROR)
                return False
        elif mode in self._available_reading_modes:
            self._io = mode
            if not self._init_device(pixfmt):
                log.log(repr(self),
                        "Error in device initializazion! (PIXFMT)",
                        level=logging.ERROR)
                return False
        else:
            log.log(repr(self),
                    "Cannot open the device " + device +
                    ": wrong or not supported reading mode!",
                    level=logging.ERROR)
            return False

        self._reopening = False
        return True

    def close(self):
        if not self.isOpened():
            return True
        elif not self._uninit_device():
            return False
        elif v4l2.HAS_LIBV4L2:
            if (-1 == v4l2.v4l2_close(self._fd)):
                self._errno_exit("close")
                return False

            self._fd = -1
        else:
            try:
                os.close(self._fd)
            except:
                self._errno_exit("close")
                return False

        return True

    def _reopen(self, pixfmt=None):
        if self.isOpened():
            was_streaming = self.isStreaming()
            if not self.close():
                return False
        else:
            was_streaming = False

        self._reopening = True
        if not self.open(self._device_filename, self._io, pixfmt):
            return False
        if was_streaming:
            return self._streamon()

        return True

    def isOpened(self):
        """Returns True if the the device is opened"""
        return self._fd >= 0

    def isStreaming(self):
        """Returns True if the the device is capturing images"""
        return (self._is_streaming | (self._io == self.MEMORY_READ))

    def getName(self):
        """Returns a string the name of the device"""
        return self._device_name

    def getFullName(self):
        """Returns a string the name and the bus info of the device"""
        return self._device_name+" ("+self._device_bus+")"

    def getDriverName(self):
        """Returns a string containing the name of the driver"""
        return self._device_driver_name

    def getDriverVersion(self):
        """Returns a string containing the version of the driver"""
        return self._device_driver_version

    def getDeviceFilename(self):
        """Returns a string containing the url of the file-device"""
        return self._device_filename

    def getDeviceBus(self):
        """Returns a string containing bus of the device"""
        return self._device_bus

    def getAvailableReadingModes(self):
        """
        Returns a dictionary containing supported reading modes.

        The keys of the dictionary are the values that can be passed
        as argument 'mode' in the function 'open'.

        The values of the dictionary contain the description of the
        corrisponding reading mode.
        """
        return self._available_reading_modes

    def isHighQualityDevice(self):
        """
        Returns true whenever the device supports the High Quality Mode,
        else return False.

        For more information see:
            http://linuxtv.org/downloads/v4l-dvb-apis/vidioc-g-parm.html
        """
        return bool(self._capture_capability & v4l2.V4L2_MODE_HIGHQUALITY)

    def hasShutterSpeed(self):
        """
        Returns true whenever the device can change its frame interval.

        For more information see:
            http://linuxtv.org/downloads/v4l-dvb-apis/vidioc-g-parm.html
        """
        return bool(self._capture_capability & v4l2.V4L2_CAP_TIMEPERFRAME)

    def getFrameRate(self):
        parm = self._get_capture_param()
        if parm is None:
            return -1
        else:
            frmival = parm.parm.capture.timeperframe
            return float(frmival.denominator)/float(frmival.numerator)

    def setFrameRate(self, fps):
        if not self.isOpened():
            return False

        width = self._format.pix.width
        height = self._format.pix.height
        pixfmt = self._format.pix.pixelformat

        size_list = self._available_pixel_format[pixfmt]['framse_size']
        ival_list = size_list[(width, height)]

        for x in ival_list:
            if fps == x[0]:
                ival = v4l2.v4l2_fract()
                ival.numerator = ctypes.c_uint32(x[1][0])
                ival.denominator = ctypes.c_uint32(x[1][1])
                return self._set_capture_param(frmival=ival)

        log.log(repr(self),
                "Invalid frame rate",
                level=logging.WARNING)
        return False

    def getFrameSize(self):
        return (self._format.pix.width, self._format.pix.height)

    def setFrameSize(self, width, height):

        if not self.isOpened():
            return False

        fmt = self._get_pixel_format()
        pix_fmt = self._available_pixel_format[fmt.fmt.pix.pixelformat]

        if fmt is None:
            return False
        elif (width, height) not in pix_fmt['framse_size']:
            return False
        else:
            fmt.fmt.pix.width = width
            fmt.fmt.pix.height = height

            return self._reopen(fmt)

    def getPixelFormat(self):
        return self._format.pix.pixelformat

    def setPixelFormat(self, pixfmt):

        if not self.isOpened():
            return False

        if not (pixfmt in self._available_pixel_format):
            return False
        else:

            fmt = self._get_pixel_format()

            if fmt is None:
                return False

            # We try to set the old resolution,
            # if available.
            curr_w = fmt.fmt.pix.width
            curr_h = fmt.fmt.pix.height

            pix_fmt = self._available_pixel_format[pixfmt]
            if (curr_w, curr_h) in pix_fmt['framse_size']:
                new_size = (curr_w, curr_h)
            else:
                try:
                    new_size = pix_fmt['framse_size'][0]
                except:
                    # something went wrong
                    return False

            fmt.fmt.pix.pixelformat = pixfmt
            fmt.fmt.pix.width = new_size[0]
            fmt.fmt.pix.height = new_size[1]

            return self._reopen(fmt)

    def setFormat(self, width, height, pixfmt):
        if not self.isOpened():
            return False

        fmt = self._get_pixel_format()

        if fmt is None:
            return False

        pix_fmt = self._available_pixel_format[pixfmt]
        if not (pixfmt in self._available_pixel_format):
            return False
        elif not ((width, height) in pix_fmt['framse_size']):
            return False

        fmt.fmt.pix.width = width
        fmt.fmt.pix.height = height
        fmt.fmt.pix.pixelformat = pixfmt
        fmt.fmt.pix.field = self._cap_field

        return self._reopen(fmt)

    def _destroy_ui_controls_interface(self):
        # children are automatically destroied
        pass

    def _qt_ui_helper_update_frame_sizes(self, frm_menu):
        frm_menu.clear()
        try:
            frm_menu.currentIndexChanged.disconnect()
        except:
            pass

        pix_fmt = self._available_pixel_format[self.getPixelFormat()]
        keys = pix_fmt['framse_size'].keys()
        keys.sort()

        for itemidx in keys:
            itemname = str(itemidx[0])+'x'+str(itemidx[1])+" pixels"
            qv = QtCore.QVariant(QtCore.QSize(itemidx[0], itemidx[1]))
            frm_menu.addItem(itemname, qv)

        csize = self.getFrameSize()
        cidx = frm_menu.findData(
            QtCore.QVariant(QtCore.QSizeF(csize[0], csize[1])))
        frm_menu.setCurrentIndex(cidx)
        frm_menu.currentIndexChanged.connect(self._ui_set_frame_size)

    def _qt_ui_helper_update_framerates(self, fps_menu):
        fps_menu.clear()
        try:
            fps_menu.currentIndexChanged.disconnect()
        except:
            pass

        pix_fmt = self._available_pixel_format[self.getPixelFormat()]
        keys = pix_fmt['framse_size'][self.getFrameSize()]
        keys.sort()
        keys.reverse()

        for item in keys:
            i0 = str(item[0])
            i10 = str(item[1][0])
            i11 = str(item[1][1])
            itemname = i0+' ('+i10+'/'+i11+') fps'
            qv = QtCore.QVariant(float(item[0]))
            fps_menu.addItem(itemname, qv)

        cidx = fps_menu.findData(QtCore.QVariant(int(self.getFrameRate())))
        fps_menu.setCurrentIndex(cidx)
        fps_menu.currentIndexChanged.connect(self._ui_set_framerate)

    def _qt_ui_helper_update_pixelformats(self, fmt_menu):
        fmt_menu.clear()
        try:
            fmt_menu.currentIndexChanged.disconnect()
        except:
            pass

        keys = self._available_pixel_format.keys()
        keys.sort()

        for itemidx in self._available_pixel_format:
            item = self._available_pixel_format[itemidx]
            itemname = item['desc']

            fccinfo = "("+item['fourcc']+")"

            if fccinfo not in itemname.replace(' ', ''):
                itemname += ' '+fccinfo

            if item['emulated']:
                itemname += ' (emulated)'

            if item['compressed']:
                itemname += ' (compressed)'

            qv = QtCore.QVariant(itemidx)
            fmt_menu.addItem(itemname, qv)

        cidx = fmt_menu.findData(QtCore.QVariant(self.getPixelFormat()))
        fmt_menu.setCurrentIndex(cidx)
        fmt_menu.currentIndexChanged.connect(self._ui_set_pixelformat)

    def _refresh_ui_controls(self):
        # refreshing controls
        for qcontrol in self._control_ui.findChildren(QtGui.QWidget):
            try:
                curr_val = self._get_control_value(qcontrol.ctrlid)
                cclass = qcontrol.ctrlclass
            except:
                continue

            if ((cclass == v4l2.V4L2_CTRL_TYPE_INTEGER) or
                    (cclass == v4l2.V4L2_CTRL_TYPE_INTEGER64)):
                qcontrol.setValue(curr_val)
            elif ((cclass == v4l2.V4L2_CTRL_TYPE_MENU) or
                  (cclass == v4l2.V4L2_CTRL_TYPE_INTEGER_MENU)):
                qcontrol.setCurrentIndex(curr_val)
            elif (cclass == v4l2.V4L2_CTRL_TYPE_STRING):
                qcontrol.setText(str(curr_val))
            elif (cclass == v4l2.V4L2_CTRL_TYPE_BOOLEAN):
                qcontrol.setCheckState(int(curr_val > 0)*2)
            elif (cclass == v4l2.V4L2_CTRL_TYPE_BUTTON):
                pass
            elif (cclass == v4l2.V4L2_CTRL_TYPE_BITMASK):
                sval = "{0:032X}".format(curr_val)
                qcontrol.setText(sval)
            else:
                continue

    def _qt_build_ui_controls_interface(self):

        del self._control_ui
        tab_widget = QtGui.QTabWidget()
        self._control_ui = tab_widget

        self._capture_controls = self._enumerate_controls()
        self._enum_pixel_format()

        if not (v4l2.V4L2_CTRL_CLASS_USER in self._capture_controls):
            self._capture_controls[v4l2.V4L2_CTRL_CLASS_USER] = []

        for ctrl_class in self._capture_controls.keys():
            widget = QtGui.QWidget()
            layout = Qt.QGridLayout()
            class_name = None
            widget.setLayout(layout)

            if ctrl_class == v4l2.V4L2_CTRL_CLASS_USER:

                # building menu for pixelformats
                fmt_label = Qt.QLabel("Pixel format")
                fmt_menu = Qt.QComboBox()
                fmt_menu.setObjectName("format menu")
                self._qt_ui_helper_update_pixelformats(fmt_menu)
                layout.addWidget(fmt_label, 0, 0)
                layout.addWidget(fmt_menu, 0, 1)

                # building menu for framesizes
                frm_label = Qt.QLabel("Frame size")
                frm_menu = Qt.QComboBox()
                frm_menu.setObjectName("size menu")
                self._qt_ui_helper_update_frame_sizes(frm_menu)
                layout.addWidget(frm_label, 1, 0)
                layout.addWidget(frm_menu, 1, 1)

                # building menu for frame intervals
                fps_label = Qt.QLabel("Framerate")
                fps_menu = Qt.QComboBox()
                fps_menu.setObjectName("framerate menu")
                self._qt_ui_helper_update_framerates(fps_menu)
                layout.addWidget(fps_label, 2, 0)
                layout.addWidget(fps_menu, 2, 1)

            row = 3

            for control in self._capture_controls[ctrl_class]:
                ctrlid = control['id']

                if (control['flags'] & v4l2.V4L2_CTRL_FLAG_DISABLED):
                    enabled = False
                else:
                    enabled = True

                # Not used, we automatically add a slider control
                # is_slider = control['flags'] & V4L2_CTRL_FLAG_SLIDER

                curr_val = self._get_control_value(ctrlid)
                label = None

                qctrl1 = None
                qctrl2 = None

                if ((control['type'] == v4l2.V4L2_CTRL_TYPE_INTEGER) or
                        (control['type'] == v4l2.V4L2_CTRL_TYPE_INTEGER64)):
                    label = Qt.QLabel(control['name'])

                    qctrl1 = Qt.QSlider(QtCore.Qt.Horizontal)
                    qctrl1.setMinimum(control['minimum'])
                    qctrl1.setMaximum(control['maximum'])
                    qctrl1.setSingleStep(control['step'])

                    qctrl2 = Qt.QSpinBox()
                    qctrl2.setMinimum(control['minimum'])
                    qctrl2.setMaximum(control['maximum'])
                    qctrl2.setSingleStep(control['step'])

                    qctrl2.setValue(curr_val)
                    qctrl1.setValue(curr_val)

                    qctrl1.valueChanged.connect(qctrl2.setValue)
                    qctrl2.valueChanged.connect(qctrl1.setValue)
                    qctrl1.valueChanged.connect(self._ui_set_control_value)

                elif ((control['type'] == v4l2.V4L2_CTRL_TYPE_MENU) or
                      (control['type'] == v4l2.V4L2_CTRL_TYPE_INTEGER_MENU)):

                    label = Qt.QLabel(control['name'])
                    qctrl1 = Qt.QComboBox()

                    for itemidx in control['menuitems']:
                        qctrl1.insertItem(itemidx,
                                          str(control['menuitems'][itemidx]))

                    qctrl1.setCurrentIndex(curr_val)
                    qctrl1.currentIndexChanged.connect(
                        self._ui_set_control_value)

                elif (control['type'] == v4l2.V4L2_CTRL_TYPE_STRING):
                    qctrl1 = Qt.QLineEdit()
                    label = Qt.QLabel(control['name'])

                    mins = "X"*control['minimum']
                    maxs = "x"*(control['maximum']-control['minimum'])
                    mask = mins+maxs+";\n"

                    qctrl1.setInputMask(mask)
                    qctrl1.setText(str(curr_val))
                    qctrl1.textChanged.connect(self._ui_set_control_text)

                elif (control['type'] == v4l2.V4L2_CTRL_TYPE_BOOLEAN):
                    qctrl1 = Qt.QCheckBox(control['name'])
                    qctrl1.setCheckState(int(curr_val > 0)*2)
                    qctrl1.stateChanged.connect(self._ui_set_control_bool)

                elif (control['type'] == v4l2.V4L2_CTRL_TYPE_BUTTON):
                    qctrl1 = Qt.QPushButton(control['name'])
                    qctrl1.stateChanged.connect(self._ui_set_control_bool)

                elif (control['type'] == v4l2.V4L2_CTRL_TYPE_BITMASK):
                    label = Qt.QLabel(control['name'])
                    qctrl1 = Qt.QLineEdit()
                    qctrl1.setInputMask("\\0\\xHHHH;\n")
                    sval = "{0:032X}".format(curr_val)
                    qctrl1.setText(sval)
                    qctrl1.textChanged.connect(self._ui_set_control_bitmask)

                elif (control['type'] == v4l2.V4L2_CTRL_TYPE_CTRL_CLASS):
                    # NOTE: this should never happen because no control
                    #       have this type id. For more informations see
                    #       http://linuxtv.org/downloads/v4l-dvb-apis/vidioc-queryctrl.html
                    class_name = str(control.name)
                    continue

                if label is not None:
                    layout.addWidget(label, row, 0)
                    label.setEnabled(enabled)
                    label.setWordWrap(True)

                if qctrl1 is not None:
                    qctrl1.ctrlid = ctrlid
                    qctrl1.ctrlclass = control['type']
                    qctrl1.setEnabled(enabled)
                    layout.addWidget(qctrl1, row, 1)

                if qctrl2 is not None:
                    qctrl2.ctrlid = ctrlid
                    qctrl2.ctrlclass = control['type']
                    qctrl2.setEnabled(enabled)
                    layout.addWidget(qctrl2, row, 2)
                row += 1

            if class_name is None:
                # Probably we are in the weird situation in which the
                # the driver supports extended controls but does not
                # support V4L2_CTRL_TYPE_CTRL_CLASS.
                class_name = self._get_control_class_name(ctrl_class)
            area = QtGui.QScrollArea()
            area.setWidget(widget)
            tab_widget.addTab(area, class_name)

        return tab_widget

    def _ui_set_pixelformat(self, idx):

        fmt_menu = self._control_ui.findChild(QtGui.QComboBox, "format menu")
        if fmt_menu is None:
            return
        else:
            pixelformat = fmt_menu.itemData(idx).toUInt()[0]
            self.setPixelFormat(pixelformat)

        size_menu = self._control_ui.findChild(QtGui.QComboBox, "size menu")
        if size_menu is not None:
            self._qt_ui_helper_update_frame_sizes(size_menu)
        self._refresh_ui_controls()

    def _ui_set_frame_size(self, idx):

        frm_menu = self._control_ui.findChild(QtGui.QComboBox, "size menu")
        if frm_menu is None:
            return

        size = frm_menu.itemData(idx).toSize()
        self.setFrameSize(int(size.width()), int(size.height()))

        frt_mnu = self._control_ui.findChild(QtGui.QComboBox, "framerate menu")
        self._qt_ui_helper_update_framerates(frt_mnu)
        self._refresh_ui_controls()

    def _ui_set_framerate(self, idx):

        fps_mnu = self._control_ui.findChild(QtGui.QComboBox, "framerate menu")
        if fps_mnu is None:
            return

        fps = fps_mnu.itemData(idx).toFloat()[0]
        self.setFrameRate(fps)
        self._refresh_ui_controls()

    def _ui_set_control_value(self, value):
        if isinstance(self._control_ui, QtCore.QObject):
            ctrlid = self._control_ui.sender().ctrlid
        else:
            return False
        return self._set_control_value(ctrlid, value)

    def _ui_set_control_text(self, text):
        if isinstance(self._control_ui, QtCore.QObject):
            ctrlid = self._control_ui.sender().ctrlid
        else:
            return False
        return self._set_control_value(ctrlid, str(text))

    def _ui_set_control_bool(self, checked):
        if isinstance(self._control_ui, QtCore.QObject):
            ctrlid = self._control_ui.sender().ctrlid
        else:
            return False
        value = int(checked > 0)
        return self._set_control_value(ctrlid, value)

    def _ui_set_control_bitmask(self, text):
        if isinstance(self._control_ui, QtCore.QObject):
            ctrlid = self._control_ui.sender().ctrlid
        else:
            return False
        value = int(str(text)[2:], 16)
        return self._set_control_value(ctrlid, value)

    def _xioctl(self, request, arg):
        if not self.isOpened():
            return (-1, errno.EBADFD)
        maxiter = 10

        if v4l2.HAS_LIBV4L2:
            while maxiter:
                maxiter -= 1
                r = v4l2.v4l2_ioctl(ctypes.c_int8(self._fd),
                                    ctypes.c_uint32(request),
                                    ctypes.pointer(arg))
                eno = v4l2.v4l2_errno()
                if (r == -1):
                    if ((errno.EINTR == eno) or (errno.EAGAIN == eno)):
                        time.sleep(0.005)
                    continue
                else:
                    return (r, eno)
            # fmt = "xioctl error[{0:03d}]: \"{1}\" request: 0x{2:08X} arg:{3}"
            # log.log(repr(self),
            #         fmt.format(eno,os.strerror(eno),request,str(arg)),
            #         level=logging.WARNING)
            return (r, eno)
        else:
            while maxiter:
                maxiter -= 1
                try:
                    r = ioctl(self._fd, request, arg)
                    return (r, 0)
                except Exception as exc:
                    if ((exc.errno == errno.EINTR) or
                            (exc.errno == errno.EAGAIN)):
                        time.sleep(0.005)
                    else:
                        return (-1, exc.errno)
            return (-1, -1)

    def _secure_xioctl(self, request, arg):
        was_streaming = self.isStreaming()
        if was_streaming:
            # In order to change some parameters,
            # we must first disable the video streaming...
            if not self._streamoff():
                return (-1, -1)
        r, err = self._xioctl(request, arg)
        if was_streaming:
            # ...and we must not forget to re-enable it.
            if not self._streamon():
                return (-1, -2)
        return (r, err)

    def _errno_exit(self, name):
        log.log(repr(self),
                "Error while setting "+str(name),
                level=logging.ERROR)

    def _get_control_value(self, ctrlid):
        control = v4l2.v4l2_control()
        control.id = ctrlid

        r, err = self._xioctl(v4l2.VIDIOC_G_CTRL, control)
        if r == -1:
            if err == errno.EINVAL:
                log.log(repr(self),
                        "(_get_control_value) invalid control id: " +
                        str(control.id),
                        level=logging.ERROR)
            else:
                self._errno_exit("VIDIOC_G_CTRL")
            return False

        return control.value

    def _set_control_value(self, ctrlid, value):
        control = v4l2.v4l2_control()
        control.id = ctrlid
        control.value = value

        r, err = self._xioctl(v4l2.VIDIOC_S_CTRL, control)
        if r == -1:
            if err == errno.EINVAL:
                log.log(repr(self),
                        "(_set_control_value) invalid control id: " +
                        str(control.id),
                        level=logging.ERROR)
            else:
                self._errno_exit("VIDIOC_S_CTRL")

            return False
        return True

    def _get_control_class_name(self, class_id):
        queryctrl = v4l2.v4l2_queryctrl()

        try:
            queryctrl.id = int(class_id)
        except:
            return str(class_id)

        r, err = self._xioctl(v4l2.VIDIOC_QUERYCTRL, queryctrl)
        if r == -1:
            if class_id == v4l2.V4L2_CTRL_CLASS_USER:
                return "User controls"
            elif class_id == v4l2.V4L2_CTRL_CLASS_MPEG:
                return "MPEG-compression controls"
            elif class_id == v4l2.V4L2_CTRL_CLASS_CAMERA:
                return "Camera controls"
            elif class_id == v4l2.V4L2_CTRL_CLASS_FM_TX:
                return "FM Modulator controls"
            elif class_id == v4l2.V4L2_CTRL_CLASS_FLASH:
                return "Camera flash controls"
            elif class_id == v4l2.V4L2_CTRL_CLASS_JPEG:
                return "JPEG-compression controls"
            elif class_id == v4l2.V4L2_CTRL_CLASS_IMAGE_SOURCE:
                return "Image source controls"
            elif class_id == v4l2.V4L2_CTRL_CLASS_IMAGE_PROC:
                return "Image processing controls"
            elif class_id == v4l2.V4L2_CTRL_CLASS_DV:
                return "Digital Video controls"
            elif class_id == v4l2.V4L2_CTRL_CLASS_FM_RX:
                return "FM Receiver controls"
            elif class_id == v4l2.V4L2_CID_PRIVATE_BASE:
                return "Driver controls"
            else:
                return hex(class_id)
        else:
            return queryctrl.name

    def _enumerate_controls(self):

        controlslist = {}

        queryctrl = v4l2.v4l2_queryctrl()
        queryctrl.id = v4l2.V4L2_CTRL_FLAG_NEXT_CTRL

        r, err = self._xioctl(v4l2.VIDIOC_QUERYCTRL, queryctrl)

        if r >= 0:
            # Extended controls are available
            while r >= 0:

                #
                # NOTE: This will be handled by the ui constructor function
                #

                # if (queryctrl.flags & v4l2.V4L2_CTRL_FLAG_DISABLED):
                #     log.log(repr(self), "disabled id: "+str(queryctrl.id))

                ctrldic = {
                    'id': queryctrl.id,
                    'type': queryctrl.type,
                    'name': queryctrl.name,
                    'minimum': queryctrl.minimum,
                    'maximum': queryctrl.maximum,
                    'step': queryctrl.step,
                    'default': queryctrl.default_value,
                    'flags': queryctrl.flags,
                    'menuitems': {}}

                log.log(repr(self),
                        "Control :"+queryctrl.name,
                        level=logging.DEBUG)

                if (queryctrl.type == v4l2.V4L2_CTRL_TYPE_MENU):
                    log.log(repr(self),
                            "this is a menu: "+str(queryctrl.id),
                            level=logging.DEBUG)
                    ctrldic['menuitems'] = self._enumerate_menu(queryctrl)

                ctrl_class = v4l2.V4L2_CTRL_ID2CLASS(queryctrl.id)

                if not ((ctrl_class) in controlslist.keys()):
                    controlslist[ctrl_class] = []

                controlslist[ctrl_class].append(ctrldic)
                queryctrl.id |= v4l2.V4L2_CTRL_FLAG_NEXT_CTRL
                r, err = self._xioctl(v4l2.VIDIOC_QUERYCTRL, queryctrl)
        else:
            # old enumeration method
            controlslist = {v4l2.V4L2_CTRL_CLASS_USER: [],
                            v4l2.V4L2_CID_PRIVATE_BASE: []}
            queryctrl.id = 0

            for queryctrl.id in range(v4l2.V4L2_CID_BASE,
                                      v4l2.V4L2_CID_LASTP1+1):
                r, err = self._xioctl(v4l2.VIDIOC_QUERYCTRL, queryctrl)
                if r == -1:
                    if err == errno.EINVAL:
                        log.log(repr(self),
                                "invalid control id: "+str(queryctrl.id),
                                level=logging.ERROR)
                        continue
                    else:
                        self._errno_exit("VIDIOC_QUERYCTRL")
                        return None
                #
                # NOTE: This will be handled by the ui constructor function
                #

                # if (queryctrl.flags & v4l2.V4L2_CTRL_FLAG_DISABLED):
                #     log.log(repr(self), "disabled id: "+str(queryctrl.id))

                ctrldic = {
                    'id': queryctrl.id,
                    'type': queryctrl.type,
                    'name': queryctrl.name,
                    'minimum': queryctrl.minimum,
                    'maximum': queryctrl.maximum,
                    'step': queryctrl.step,
                    'default': queryctrl.default_value,
                    'flags': queryctrl.flags,
                    'menuitems': {}}

                log.log(repr(self),
                        "Control "+queryctrl.name,
                        level=logging.DEBUG)

                if (queryctrl.type == v4l2.V4L2_CTRL_TYPE_MENU):
                    log.log(repr(self),
                            "this is a menu: "+str(queryctrl.id),
                            level=logging.DEBUG)
                    ctrldic['menuitems'] = self._enumerate_menu(queryctrl)

                controlslist[v4l2.V4L2_CTRL_CLASS_USER].append(ctrldic)

            queryctrl.id = v4l2.V4L2_CID_PRIVATE_BASE
            while 1:
                r, err = self._xioctl(v4l2.VIDIOC_QUERYCTRL, queryctrl)
                if r == -1:
                    if err == errno.EINVAL:
                        log.log(repr(self),
                                "invalid control id: "+str(queryctrl.id),
                                level=logging.ERROR)
                        break
                    else:
                        self._errno_exit("VIDIOC_QUERYCTRL")
                        break

                ctrldic = {
                    'id': queryctrl.id,
                    'type': queryctrl.type,
                    'name': queryctrl.name,
                    'minimum': queryctrl.minimum,
                    'maximum': queryctrl.maximum,
                    'step': queryctrl.step,
                    'default': queryctrl.default_value,
                    'flags': queryctrl.flags,
                    'menuitems': {}}

                if (queryctrl.type == v4l2.V4L2_CTRL_TYPE_MENU):
                    log.log(repr(self),
                            "this is a menu: "+str(queryctrl.id),
                            level=logging.DEBUG)
                    ctrldic['menuitems'] = self._enumerate_menu(queryctrl,
                                                                True)
                elif (queryctrl.type == v4l2.V4L2_CTRL_TYPE_INTEGER_MENU):
                    log.log(repr(self),
                            "this is a menu: "+str(queryctrl.id),
                            level=logging.DEBUG)
                    ctrldic['menuitems'] = self._enumerate_menu(queryctrl,
                                                                False)

                controlslist[v4l2.V4L2_CID_PRIVATE_BASE].append(ctrldic)
                queryctrl.id += 1

        return controlslist

    def _enumerate_menu(self, queryctrl, use_name=True):

        querymenu = v4l2.v4l2_querymenu()
        querymenu.id = queryctrl.id

        log.log(repr(self),
                "menu items for "+str(querymenu.id)+":",
                level=logging.DEBUG)

        menudic = {}
        log.log(repr(self),
                "this is a menu: "+str(queryctrl.id),
                level=logging.DEBUG)
        if use_name:
            for querymenu.index in range(queryctrl.minimum,
                                         queryctrl.maximum+1):
                r, err = self._xioctl(v4l2.VIDIOC_QUERYMENU, querymenu)
                if (r == -1):
                    log.log(repr(self),
                            "Error "+str(err)+": "+os.strerror(err),
                            level=logging.ERROR)
                    continue
                menudic[querymenu.index] = str(querymenu._u54.name)
                log.log(repr(self),
                        str(querymenu.index)+":"+str(querymenu._u54.name),
                        level=logging.DEBUG)
        else:
            for querymenu.index in range(queryctrl.minimum,
                                         queryctrl.maximum+1):
                r, err = self._xioctl(v4l2.VIDIOC_QUERYMENU, querymenu)
                if (r == -1):
                    log.log(repr(self),
                            "Error "+str(err)+": "+os.strerror(err),
                            level=logging.ERROR)
                    continue
                menudic[querymenu.index] = str(querymenu._u54.value)
                log.log(repr(self),
                        str(querymenu.index)+":"+str(querymenu._u54.value),
                        level=logging.DEBUG)
        return menudic

    def _set_capture_param(self, frmival=None, hiq=None, override_parm=None):
        fmt = self._get_pixel_format()
        if fmt is None:
            return False

        was_streaming = self.isStreaming()
        self._reopening = True
        if not (self.close() and
                self.open(self._device_filename, self._io, fmt)):
            self._reopening = False
            return False

        if override_parm is None:
            log.log(repr(self),
                    "getting capture params...",
                    level=logging.DEBUG)
            parm = self._get_capture_param()
            if type(parm) != v4l2.v4l2_streamparm:
                # There was an error reading capture parameters
                log.log(repr(self),
                        "failed to obtain capture params...",
                        level=logging.ERROR)
                return False
        elif type(override_parm) == v4l2.v4l2_streamparm:
            parm = override_parm
        else:
            log.log(repr(self),
                    "invalid parameter type",
                    level=logging.ERROR)
            return False

        if parm.type != v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE:
            log.log(repr(self),
                    self._device_filename+" is not a capture device!",
                    level=logging.ERROR)
            return False

        if frmival is not None:
            log.log(repr(self),
                    "setting frame interval",
                    level=logging.DEBUG)
            if type(frmival) != v4l2.v4l2_fract:
                log.log(repr(self),
                        "VIDIOC_S_PARM: Invalid frame interval type",
                        level=logging.ERROR)
                return False

            parm.parm.capture.timeperframe = frmival

        if (hiq is not None) and self.isHighQualityDevice():
            log.log(repr(self),
                    "setting frame high quality",
                    level=logging.DEBUG)
            if hiq:
                hiq = v4l2.V4L2_MODE_HIGHQUALITY
            else:
                hiq = 0

            parm.parm.capture.capturemode = hiq

        if parm:
            r, err = self._secure_xioctl(v4l2.VIDIOC_S_PARM, parm)
            if r == -1:
                if err == -1:
                    log.log(repr(self),
                            "Error while disabling video stream " +
                            "before setting capture parameters",
                            level=logging.DEBUG)
                elif err == -2:
                    log.log(repr(self),
                            "Error while reenalbing video stream " +
                            "after setting capture parameters",
                            level=logging.DEBUG)
                else:
                    self._errno_exit("Error in setting capture parameters")
                return False
        else:
            return False

        if was_streaming:
            return self._streamon()
        return True

    def _get_capture_param(self):

        if not self.isOpened():
            return None

        parm = v4l2.v4l2_streamparm()
        parm.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE

        r, err = self._xioctl(v4l2.VIDIOC_G_PARM, parm)
        if r == -1:
            log.log(repr(self),
                    self._device_filename +
                    " cannot retrieve capture parameters",
                    level=logging.ERROR)
            return None

        # NOTE: We use only video_capture devices and thus parm.type
        #       should be always V4L2_BUF_TYPE_VIDEO_CAPTURE.
        if parm.type != v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE:
            log.log(repr(self),
                    self._device_filename +
                    " is not a capture device!",
                    level=logging.ERROR)
            return None

        self._capture_capability = parm.parm.capture.capability

        return parm

    def _enum_frame_intervals(self, pixfmt, width, height):
        if not self.hasShutterSpeed():
            return False

        frmival = v4l2.v4l2_frmivalenum()
        frmival.pixel_format = pixfmt
        frmival.width = width
        frmival.height = height
        frmival.index = 0

        frm_sizes = self._available_pixel_format[pixfmt]['framse_size']
        frm_sizes[(width, height)] = []

        while 1:
            r, err = self._xioctl(v4l2.VIDIOC_ENUM_FRAMEINTERVALS, frmival)
            if r == -1:
                break

            if frmival.type == v4l2.V4L2_FRMIVAL_TYPE_DISCRETE:
                i_num = frmival._u20.discrete.numerator
                i_den = frmival._u20.discrete.denominator
                fps = float(i_den)/float(i_num)
                frm_sizes[(width, height)].append((fps, (i_num, i_den)))
                frmival.index += 1

            elif (frmival.type == v4l2.V4L2_FRMIVAL_TYPE_STEPWISE or
                  frmival.type == v4l2.V4L2_FRMIVAL_TYPE_CONTINUOUS):

                i_min_num = frmival._u20.stepwise.min.numerator
                i_min_den = frmival._u20.stepwise.min.denominator
                i_max_num = frmival._u20.stepwise.max.numerator
                i_max_den = frmival._u20.stepwise.max.denominator
                i_stp_num = frmival._u20.stepwise.step.numerator
                i_stp_den = frmival._u20.stepwise.step.denominator

                i_min_fps = float(i_min_den)/float(i_min_num)
                # i_max_fps=float(i_max_den)/float(i_max_num)

                frm_sizes[(width, height)].append((i_min_fps,
                                                   (i_min_num, i_min_den)))

                max_i = float(i_max_num)/float(i_max_den)

                n = i_min_num*i_stp_den + i_min_den*i_stp_num
                d = i_stp_den*i_min_den

                val = float(n)/float(d)

                while val <= max_i:
                    n += i_min_den*i_stp_num
                    val = float(n)/float(d)
                    fps = float(d)/float(n)
                    frm_sizes[(width, height)].append((fps, (n, d)))

                break

    def _enum_frame_size(self, pixfmt):
        frmsize = v4l2.v4l2_frmsizeenum()
        frmsize.pixel_format = pixfmt
        frmsize.index = 0

        pix_fmt = self._available_pixel_format[pixfmt]
        pix_fmt['framse_size'] = {}

        while 1:
            r, err = self._xioctl(v4l2.VIDIOC_ENUM_FRAMESIZES, frmsize)
            if r == -1:
                break

            if frmsize.type == v4l2.V4L2_FRMSIZE_TYPE_DISCRETE:
                w = frmsize._u16.discrete.width
                h = frmsize._u16.discrete.height
                pix_fmt['framse_size'][(w, h)] = None
                self._enum_frame_intervals(pixfmt, w, h)
                frmsize.index += 1

            elif (frmsize.type == v4l2.V4L2_FRMSIZE_TYPE_STEPWISE or
                  frmsize.type == v4l2.V4L2_FRMSIZE_TYPE_CONTINUOUS):

                min_w = frmsize._u16.stepwise.min_width
                max_w = frmsize._u16.stepwise.max_width
                stp_w = frmsize._u16.stepwise.step_width

                w_list = range(min_w, max_w, stp_w)

                if max_w not in w_list:
                    w_list += [max_w]

                min_h = frmsize._u16.stepwise.min_height
                max_h = frmsize._u16.stepwise.max_height
                stp_h = frmsize._u16.stepwise.step_height

                h_list = range(min_h, max_h, stp_h)

                if max_h not in h_list:
                    h_list += [max_h]

                # I'm not sure how to handle this case:
                # assuming that width and height are pairs
                # and are not indipendet values
                for wxh in zip(w, h):
                    pix_fmt['framse_size'][(w, h)] = None
                    self._enum_frame_intervals(pixfmt, w, h)
                break

    def _enum_pixel_format(self):
        if not self.isOpened():
            return

        fmtdesc = v4l2.v4l2_fmtdesc()
        fmtdesc.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
        fmtdesc.index = 0

        self._available_pixel_format = {}

        while 1:
            try:
                r, err = self._xioctl(v4l2.VIDIOC_ENUM_FMT, fmtdesc)
                if r == -1:
                    break
            except:
                break

            fourcc = v4l2.v4l2_fourcc_string(fmtdesc.pixelformat)

            self._available_pixel_format[fmtdesc.pixelformat] = {
                'fourcc': fourcc,
                'desc': fmtdesc.description,
                'flags': fmtdesc.flags,
                'compressed': bool(fmtdesc.flags & 1),
                'emulated': bool(fmtdesc.flags & 2)}
            self._enum_frame_size(fmtdesc.pixelformat)
            fmtdesc.index += 1

    def _get_pixel_format(self):
        fmt = v4l2.v4l2_format()
        fmt.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
        if (-1 == self._xioctl(v4l2.VIDIOC_G_FMT, fmt)):
            self._errno_exit("VIDIOC_G_FMT")
            return None
        else:
            return fmt

    def _set_pixel_format(self, wid=None, hei=None,
                          pixfmt=None, field=None,
                          preserve=True, override=None):

        if not self.isOpened():
            return None

        if override is None:
            fmt = v4l2.v4l2_format()

            # self._clear(fmt)

            if pixfmt is None:
                if v4l2.V4L2_PIX_FMT_RGB32 in self._available_pixel_format:
                    pixfmt = v4l2.V4L2_PIX_FMT_RGB32
                elif v4l2.V4L2_PIX_FMT_RGB24 in self._available_pixel_format:
                    pixfmt = v4l2.V4L2_PIX_FMT_RGB24
                elif v4l2.V4L2_PIX_FMT_BGR32 in self._available_pixel_format:
                    pixfmt = v4l2.V4L2_PIX_FMT_BGR32
                elif v4l2.V4L2_PIX_FMT_BGR24 in self._available_pixel_format:
                    pixfmt = v4l2.V4L2_PIX_FMT_BGR24
                else:
                    pixfmt = self._available_pixel_format.keys()[0]

            pix_fmt = self._available_pixel_format[pixfmt]
            if (wid is None) and (hei is None):
                try:
                    wid, hei = pix_fmt['framse_size'].keys()[-1]
                except Exception:
                    return None

            elif (wid is not None) and (hei is not None):
                if not ((wid, hei) in pix_fmt['framse_size']):
                    return None
            else:
                log.log(repr(self),
                        "Both width and height must be specified!",
                        level=logging.ERROR)
                return None

            if field is None:
                field = self._cap_field

            fmt.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
            if preserve:
                # Preserve original settings as set by v4l2-ctl for example
                log.log(repr(self),
                        "trying to preserve the original format settings",
                        level=logging.DEBUG)

                if self._format is None:
                    logmsg = "setting default format"
                    if (-1 == self._xioctl(v4l2.VIDIOC_G_FMT, fmt)):
                        self._errno_exit("VIDIOC_G_FMT")
                        return None

                    fmt_list = self.supported_pixel_formats
                    if fmt.fmt.pix.pixelformat not in fmt_list:
                        fmt.fmt.pix.pixelformat = pixfmt

                else:
                    logmsg = "setting old format"

                    fmt.fmt.pix.width = self._format.pix.width
                    fmt.fmt.pix.height = self._format.pix.height

                    fmt.fmt.pix.pixelformat = self._format.pix.pixelformat
                    fmt.fmt.pix.field = self._format.pix.field

                log.log(repr(self),
                        logmsg+": {0:d}x{1:d} [{2:s}]".format(
                            fmt.fmt.pix.width,
                            fmt.fmt.pix.height,
                            v4l2.v4l2_fourcc_string(fmt.fmt.pix.pixelformat)),
                        level=logging.DEBUG)
            else:
                fmt.fmt.pix.width = wid
                fmt.fmt.pix.height = hei

                fmt.fmt.pix.pixelformat = pixfmt
                fmt.fmt.pix.field = field

                log.log(repr(self),
                        "setting new format: {0:d}x{1:d} [{2:s}]".format(
                            fmt.fmt.pix.width,
                            fmt.fmt.pix.height,
                            v4l2.v4l2_fourcc_string(fmt.fmt.pix.pixelformat)),
                        level=logging.DEBUG)

            fmtmatch = (fmt.fmt.pix.pixelformat == pixfmt)

        elif type(override) == v4l2.v4l2_format:
            fmt = override
            fmtmatch = True

        fmt_list = self._available_pixel_format.keys()
        fmtavail = (fmt.fmt.pix.pixelformat in fmt_list)

        if not (fmtmatch and fmtavail):
            log.log(repr(self),
                    "Pixel format not supported by device!",
                    level=logging.ERROR)
            return None
        elif fmt.fmt.pix.pixelformat not in self.supported_pixel_formats:
            log.log(repr(self),
                    "Pixel format not supported by " +
                    "lxnstack decoding routines!",
                    level=logging.WARNING)

        if (-1 == self._secure_xioctl(v4l2.VIDIOC_S_FMT, fmt)[0]):
            # Note VIDIOC_S_FMT may change width and height.
            self._errno_exit("VIDIOC_S_FMT")
            return None

        # Buggy driver paranoia.
        minw = fmt.fmt.pix.width * 2
        if (fmt.fmt.pix.bytesperline < minw):
            fmt.fmt.pix.bytesperline = minw

        minb = fmt.fmt.pix.bytesperline * fmt.fmt.pix.height
        if (fmt.fmt.pix.sizeimage < minb):
            fmt.fmt.pix.sizeimage = minb

        self._format = fmt.fmt

        return fmt

    def _uninit_device(self):
        # deallocating/unmapping memory
        if self._io == self.MEMORY_READ:
            self._buffers.pop(0)
        else:
            if not self._streamoff():
                return False

            if self._io == self.MEMORY_MMAP:
                for i in self._buffers.keys():
                    if v4l2.HAS_LIBV4L2:
                        buf_start = self._buffers[i]['start']
                        buf_length = self._buffers[i]['length']
                        log.log(repr(self),
                                "unmapping buffer {0:02d}".format(i),
                                level=logging.DEBUG)
                        rval = v4l2.v4l2_munmap(ctypes.c_voidp(buf_start),
                                                ctypes.c_uint32(buf_length))
                        if (-1 == rval):
                            self._errno_exit("munmap")
                    else:
                        self._buffers.pop(i)

            elif self._io == self.MEMORY_USERPTR:
                for i in self._buffers.keys():
                    self._buffers.pop(i)

        self._buffers = {}
        return True

    def _init_device(self, pixfmt=None):

        if not self._reopening:
            self._enum_pixel_format()

        if pixfmt is None:
            if self._set_pixel_format(preserve=True) is None:
                return False
        else:
            if self._set_pixel_format(override=pixfmt) is None:
                if self._set_pixel_format(preserve=False) is None:
                    return False

        if not self._reopening:
            self._build_ui_controls_interface()

        if self._io == self.MEMORY_READ:
            log.log(repr(self),
                    "using reading mode",
                    level=logging.DEBUG)
            if not self._init_read():
                return False
        else:
            if self._io == self.MEMORY_MMAP:
                log.log(repr(self),
                        "using mmap mode",
                        level=logging.DEBUG)
                if not self._init_mmap():
                    return False

                for i in self._buffers.keys():
                    buf = v4l2.v4l2_buffer()

                    # self._clear(buf)

                    buf.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
                    buf.memory = self.MEMORY_MMAP
                    buf.index = i

                    if (-1 == self._xioctl(v4l2.VIDIOC_QBUF, buf)[0]):
                        self._errno_exit("INIT:MMAP:VIDIOC_QBUF")
                        return False

            elif self._io == self.MEMORY_USERPTR:

                if not self._init_userp():
                    return False

                for i in self._buffers.keys():
                    buf = v4l2.v4l2_buffer()

                    # self._clear(buf)

                    buf.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
                    buf.memory = self.MEMORY_USERPTR
                    buf.index = i
                    buf.m.userptr = self._buffers[i]['start']
                    buf.length = self._buffers[i]['length']

                    if (-1 == self._xioctl(v4l2.VIDIOC_QBUF, buf)[0]):
                        self._errno_exit("INIT:USERPTR:VIDIOC_QBUF")
        return True

    def _streamon(self):
        if self._io == self.MEMORY_READ:
            return True
        elif self._is_streaming:
            return True
        elif (-1 == self._xioctl(v4l2.VIDIOC_STREAMON,
                                 v4l2.v4l2_buf_type(
                                     v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE)
                                 )[0]):
            self._errno_exit("VIDIOC_STREAMON")
            return False
        else:
            self._is_streaming = True
            return True

    def _streamoff(self):
        if self._io == self.MEMORY_READ:
            return True
        elif not self._is_streaming:
            return True
        if (-1 == self._xioctl(v4l2.VIDIOC_STREAMOFF,
                               v4l2.v4l2_buf_type(
                                   v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE)
                               )[0]):
            self._errno_exit("VIDIOC_STREAMOFF")
            return False
        else:
            self._is_streaming = False
            return True

    def _init_read(self):
        buffer_size = self._format.pix.sizeimage
        try:
            sbuf = ctypes.create_string_buffer(buffer_size)
        except MemoryError:
            log.log(repr(self),
                    "Out of memory",
                    level=logging.ERROR)
            return False
        except:
            return False
        self._buffers = {
            0: {'start': ctypes.addressof(sbuf),
                'length': buffer_size,
                'arr': sbuf}
            }
        return True

    def _init_mmap(self):

        req = v4l2.v4l2_requestbuffers()

        # self._clear(req)

        req.count = self._n_userp_buff
        req.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
        req.memory = self.MEMORY_MMAP

        r, err = self._xioctl(v4l2.VIDIOC_REQBUFS, req)

        if (-1 == r):
            if (errno.EINVAL == err):
                log.log(repr(self),
                        self._device_filename +
                        " does not support memory mapping",
                        level=logging.WARNING)
            else:
                self._errno_exit("MMAP:VIDIOC_REQBUFS")
                return False

        if (req.count < 2):
            log.log(repr(self),
                    "Insufficient buffer memory on " +
                    self._device_filename,
                    level=logging.ERROR)
            return False

        self._buffers = {}

        for n_buffers in range(req.count):
            buf = v4l2.v4l2_buffer()

            # self._clear(buf)

            buf.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
            buf.memory = self.MEMORY_MMAP
            buf.index = n_buffers

            log.log(repr(self),
                    "setting mmap buffer {0:02d}".format(n_buffers),
                    level=logging.DEBUG)

            if (-1 == self._xioctl(v4l2.VIDIOC_QUERYBUF, buf)[0]):
                self._errno_exit("VIDIOC_QUERYBUF")
                return False

            try:
                buff_length = buf.length
                if v4l2.HAS_LIBV4L2:
                    buff_start = v4l2.v4l2_mmap(
                        0,
                        buf.length,
                        mmap.PROT_READ | mmap.PROT_WRITE,
                        mmap.MAP_SHARED,
                        self._fd, buf.m.offset)
                    if (buff_start == -1):
                        self._errno_exit("ERROR: v4l2_mmap")
                        return False

                else:
                    buff_start = mmap.mmap(
                        self._fd,
                        buf.length,
                        prot=(mmap.PROT_READ | mmap.PROT_WRITE),
                        access=mmap.MAP_SHARED,
                        offset=buf.m.offset)

                self._buffers[n_buffers] = {
                    'start': buff_start,
                    'length': buff_length}

            except Exception as exc:
                self._errno_exit("mmap:"+str(exc))
                return False

        return True

    def _init_userp(self):
        req = v4l2.v4l2_requestbuffers()
        buffer_size = self._format.pix.sizeimage

        # self._clear(req)

        req.count = self._n_userp_buff
        req.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
        req.memory = self.MEMORY_USERPTR

        r, err = self._xioctl(v4l2.VIDIOC_REQBUFS, req)
        if (-1 == r):
            if (errno.EINVAL == err):
                    log.log(repr(self),
                            self._device_filename +
                            " does not support user pointer i/o",
                            level=logging.ERROR)
            else:
                self._errno_exit("UPTR:VIDIOC_REQBUFS")
            return False

        for n_buffers in range(self._n_userp_buff):

            try:
                sbuf = ctypes.create_string_buffer(buffer_size)
            except MemoryError:
                log.log(repr(self),
                        "Out of memory",
                        level=logging.ERROR)
                return False

            self._buffers[n_buffers] = {
                'start': ctypes.addressof(sbuf),
                'length': buffer_size,
                'arr': sbuf}
        return True

    def getFrame(self):
        if not self.isOpened():
            return None
        elif not self.isStreaming():
            self._streamon()

        ndframe = None

        maxiter = int(10.0/self._timeout)

        while maxiter:
            maxiter -= 1
            fds = [self._fd]

            try:
                r = select.select(fds, [], [], self._timeout)
            except Exception as exc:
                if (errno.EINTR == exc.errno):
                    continue
                else:
                    self._errno_exit("select")
                    return None

            if (0 == r):
                log.log(repr(self),
                        "select timeout",
                        level=logging.DEBUG)
                return None

            ndframe = self.read_frame()
            if (ndframe is not None):
                break

        self.lastframe = ndframe
        return ndframe

    def read_frame(self):
        buf = v4l2.v4l2_buffer()

        ndframe = None

        if self._io == self.MEMORY_READ:
            r = v4l2.v4l2_read(self._fd,
                               self._buffers[0]['start'],
                               self._buffers[0]['length'])
            if (-1 == r):
                if v4l2.v4l2_errno() == errno.EAGAIN:
                    return None
                elif v4l2.v4l2_errno() == errno.EIO:
                    # Could ignore EIO, see spec.
                    pass
                else:
                    self._errno_exit("read")
                    return None

            ndframe = self._process_image(self._buffers[0])

        elif self._io == self.MEMORY_MMAP:
            # self._clear(buf)

            buf.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
            buf.memory = self.MEMORY_MMAP

            r, err = self._xioctl(v4l2.VIDIOC_DQBUF, buf)

            if (-1 == r):
                if err == errno.EAGAIN:
                    return False
                elif err == errno.EIO:
                    # Could ignore EIO, see spec.
                    # fall through
                    pass
                else:
                    self._errno_exit("READ:MMAP:VIDIOC_DQBUF")
                    return False

            assert(buf.index < len(self._buffers))

            ndframe = self._process_image(self._buffers[buf.index])

            if (-1 == self._xioctl(v4l2.VIDIOC_QBUF, buf)[0]):
                self._errno_exit("READ:MMAP:VIDIOC_QBUF")
                return False
        elif self._io == self.MEMORY_USERPTR:
            # self._clear(buf)
            buf.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
            buf.memory = self.MEMORY_USERPTR

            r, err = self._xioctl(v4l2.VIDIOC_DQBUF, buf)
            if (-1 == r):
                if err == errno.EAGAIN:
                    return False
                elif err == errno.EIO:
                    # Could ignore EIO, see spec.
                    pass
                else:
                    self._errno_exit("READ:USERPTR:VIDIOC_DQBUF")
                    return False

            index = -1
            for i in self._buffers.keys():
                if (buf.m.userptr == self._buffers[i]['start'] and
                        buf.length == self._buffers[i]['length']):
                    index = i
                    break

            ndframe = self._process_image(self._buffers[index])
            if (-1 == self._xioctl(v4l2.VIDIOC_QBUF, buf)):
                    self._errno_exit("READ:USERPTR:VIDIOC_QBUF")
        return ndframe

    def _process_image(self, buf):
        if v4l2.HAS_LIBV4L2:
            bstart = buf['start']
            blen = buf['length']

            sbuf = ctypes.create_string_buffer(blen)
            if ctypes.memmove(sbuf, ctypes.c_void_p(bstart), blen) == 0:
                self._errno_exit("PROCESSING:MEMMOVE")
                return None

        w = self._format.pix.width
        h = self._format.pix.height

        try:
            if self._format.pix.pixelformat == v4l2.V4L2_PIX_FMT_RGB444:
                rawarr = np.ndarray((h, w),
                                    dtype=np.uint16,
                                    buffer=sbuf.raw,
                                    order='C')
                arr = np.ndarray((h, w, 3))
                arr[..., 0] = rawarr & 0b0000111100000000
                arr[..., 1] = rawarr & 0b0000000011110000
                arr[..., 2] = rawarr & 0b0000000000001111

            elif self._format.pix.pixelformat == v4l2.V4L2_PIX_FMT_RGB24:
                arr = np.ndarray((h, w, 3),
                                 dtype=np.uint8,
                                 buffer=sbuf.raw,
                                 order='C')

            elif self._format.pix.pixelformat == v4l2.V4L2_PIX_FMT_RGB32:
                arr = np.ndarray((h, w, 4),
                                 dtype=np.uint8,
                                 buffer=sbuf.raw,
                                 order='C')

            elif self._format.pix.pixelformat == v4l2.V4L2_PIX_FMT_BGR24:
                arr = np.ndarray((h, w, 3),
                                 dtype=np.uint8,
                                 buffer=sbuf.raw,
                                 order='C')

            elif self._format.pix.pixelformat == v4l2.V4L2_PIX_FMT_BGR32:
                arr = np.ndarray((h, w, 4),
                                 dtype=np.uint8,
                                 buffer=sbuf.raw,
                                 order='C')

            elif self._format.pix.pixelformat == v4l2.V4L2_PIX_FMT_GREY:
                arr = np.ndarray((h, w),
                                 dtype=np.uint8,
                                 buffer=sbuf.raw,
                                 order='C')

            elif self._format.pix.pixelformat == v4l2.V4L2_PIX_FMT_Y16:
                arr = np.ndarray((h, w),
                                 dtype=np.uint16,
                                 buffer=sbuf.raw,
                                 order='C')
            else:
                arr = np.random.random_integers(0, 100, (h, w))
        except Exception as exc:
            log.log(repr(self),
                    "frame processing error: \""+str(exc)+"\"",
                    level=logging.DEBUG)
            arr = np.random.random_integers(0, 100, (h, w))
        return arr


class Cv2VideoDevice(GenericVideoDevice):
    # cv2 video capture interface
    def __init__(self):
        GenericVideoDevice.__init__(self)
        self._device = None
        self._devfile = ''
        self._reopening = False
        self._devindex = None

    def __del__(self):
        self.close()
        del self._control_ui

    def open(self, device=None):
        idx = None
        if device is None:
            if self._devindex is None:
                raise IOError("No device specified!")
            else:
                device = self._devindex
        try:
            idx = int(device)
            self._device = cv2.VideoCapture(idx)
        except ValueError:
            filename = str(device)
            if (not os.path.exists(device) and
                    not os.path.isdir(device)):
                raise IOError("Cannot find the file \"" + filename + "\"")
            else:
                dev_file = os.path.basename(filename)
                if (len(dev_file) > 5) and (dev_file[:5] == "video"):
                    try:
                        idx = int(dev_file[5:])
                    except:
                        raise IOError("Cannot open the device \"" +
                                      filename + "\"")

                    self._device = cv2.VideoCapture(idx)
                    self._filename = filename
                else:
                    raise IOError("Cannot open the device \"" +
                                  filename + "\"")

        if self._device.isOpened():
            self._devindex = idx
            self.name = "cv2 video device"+str(self._devindex)

            self.resetDeviceInfo()
            self._device_info['device name'] = self.name
            self._device_info['driver backend'] = 'OpenCV v2'
            self._device_info['device file'] = self._filename

            if not self._reopening:
                self._build_ui_controls_interface()

            self._reopening = False

            return True
        else:
            return False

    def close(self):
        self._device.release()
        return not self._device.isOpened()

    def isOpened(self):
        if self._device is None:
            return False
        else:
            return self._device.isOpened()

    def _destroy_ui_controls_interface(self):
        # children are automatically destroied
        pass

    def _qt_ui_helper_update_frame_sizes(self, frm_menu):
        frm_menu.clear()

        try:
            frm_menu.currentIndexChanged.disconnect()
        except:
            pass

        keys = self._available_pixel_format[self.getPixelFormat()].keys()
        keys.sort()

        for size in keys:
            itemname = str(size[0])+'x'+str(size[1])+" pixels"
            qv = QtCore.QVariant(QtCore.QSize(int(size[0]), int(size[1])))
            frm_menu.addItem(itemname, qv)

        csize = self.getFrameSize()
        cidx = frm_menu.findData(QtCore.QVariant(QtCore.QSizeF(csize[0],
                                                               csize[1])))
        frm_menu.setCurrentIndex(cidx)
        frm_menu.currentIndexChanged.connect(self._ui_set_frame_size)

    def _qt_ui_helper_update_framerates(self, fps_menu):
        fps_menu.clear()
        try:
            fps_menu.currentIndexChanged.disconnect()
        except:
            pass

        size_list = self._available_pixel_format[self.getPixelFormat()]
        keys = size_list[self.getFrameSize()]
        keys.sort()
        keys.reverse()

        for item in keys:
            itemname = str(item)+' fps'
            qv = QtCore.QVariant(float(item))
            fps_menu.addItem(itemname, qv)

        cidx = fps_menu.findData(QtCore.QVariant(int(self.getFrameRate())))
        fps_menu.setCurrentIndex(cidx)
        fps_menu.currentIndexChanged.connect(self._ui_set_framerate)

    def _qt_ui_helper_update_pixelformats(self, fmt_menu):
        fmt_menu.clear()

        try:
            fmt_menu.currentIndexChanged.disconnect()
        except:
            pass

        keys = self._available_pixel_format.keys()
        keys.sort()

        for itemname in self._available_pixel_format:
            qv = QtCore.QVariant(itemname)
            fmt_menu.addItem(itemname, qv)

        cidx = fmt_menu.findData(QtCore.QVariant(self.getPixelFormat()))
        fmt_menu.setCurrentIndex(cidx)
        fmt_menu.currentIndexChanged.connect(self._ui_set_pixelformat)
        self._refresh_ui_controls()

    def _refresh_ui_controls(self):
        for qcontrol in self._control_ui.findChildren(QtGui.QWidget):
            try:
                curr_val = self._get_control_value(qcontrol.ctrlid)
            except:
                continue

            control = self._capture_controls[qcontrol.ctrlid]
            # Not used, we automatically add a slider control
            # is_slider = control['flags'] & V4L2_CTRL_FLAG_SLIDER

            try:
                curr_val = control['value']
            except:
                curr_val = control['default']

            if ((control['type'] == 'int') or
                    (control['type'] == 'int64')):
                qcontrol.setValue(curr_val)

            elif ('menu' in control['type']):
                qcontrol.setCurrentIndex(curr_val)

            elif (control['type'] == 'string'):
                qcontrol.setText(str(curr_val))

            elif (control['type'] == 'bool'):
                qcontrol.setCheckState(int(curr_val > 0)*2)

            elif (control['type'] == 'button'):
                qcontrol = Qt.QPushButton(control['name'])

            elif (control['type'] == 'bitmask'):
                try:
                    sval = "{0:032X}".format(curr_val)
                except:
                    try:
                        if '0x' == curr_val[0:2]:
                            sval = "{0:032X}".format(int(curr_val[0:2], 16))
                        else:
                            sval = "{0:032X}".format(int(curr_val, 16))
                    except:
                        sval = str(curr_val)
                qcontrol.setText(sval)
            else:
                continue

    def _qt_build_ui_controls_interface(self):
        del self._control_ui

        tab_widget = QtGui.QTabWidget()
        self._control_ui = tab_widget

        widget = QtGui.QWidget()
        layout = Qt.QGridLayout()
        widget.setLayout(layout)

        self._capture_controls = getV4L2DeviceProperties(self._filename)
        if 'formats' in self._capture_controls:
            frmat = self._capture_controls.pop('formats')
            self._available_pixel_format = frmat
        else:
            self._available_pixel_format = {}

        if self._capture_controls is None:
            self._control_ui = None
            return None

        # building menu for pixelformats
        fmt_label = Qt.QLabel("Pixel format")
        fmt_menu = Qt.QComboBox()
        fmt_menu.setObjectName("format menu")
        self._qt_ui_helper_update_pixelformats(fmt_menu)
        layout.addWidget(fmt_label, 0, 0)
        layout.addWidget(fmt_menu, 0, 1)

        # building menu for framesizes
        frm_label = Qt.QLabel("Frame size")
        frm_menu = Qt.QComboBox()
        frm_menu.setObjectName("size menu")
        self._qt_ui_helper_update_frame_sizes(frm_menu)
        layout.addWidget(frm_label, 1, 0)
        layout.addWidget(frm_menu, 1, 1)

        # building menu for frame intervals
        fps_label = Qt.QLabel("Framerate")
        fps_menu = Qt.QComboBox()
        fps_menu.setObjectName("framerate menu")
        self._qt_ui_helper_update_framerates(fps_menu)
        layout.addWidget(fps_label, 2, 0)
        layout.addWidget(fps_menu, 2, 1)

        row = 3

        for controlname in self._capture_controls:
            control = self._capture_controls[controlname]
            # Not used, we automatically add a slider control
            # is_slider = control['flags'] & V4L2_CTRL_FLAG_SLIDER

            try:
                curr_val = control['value']
            except:
                curr_val = control['default']

            label = None
            labeltext = controlname.replace('_', ' ')
            qctrl1 = None
            qctrl2 = None

            if ((control['type'] == 'int') or
                    (control['type'] == 'int64')):
                label = Qt.QLabel(labeltext)

                qctrl1 = Qt.QSlider(QtCore.Qt.Horizontal)
                qctrl1.setMinimum(control['min'])
                qctrl1.setMaximum(control['max'])
                qctrl1.setSingleStep(control['step'])

                qctrl2 = Qt.QSpinBox()
                qctrl2.setMinimum(control['min'])
                qctrl2.setMaximum(control['max'])
                qctrl2.setSingleStep(control['step'])

                qctrl2.setValue(int(curr_val))
                qctrl1.setValue(int(curr_val))

                qctrl1.valueChanged.connect(qctrl2.setValue)
                qctrl2.valueChanged.connect(qctrl1.setValue)
                qctrl1.valueChanged.connect(self._ui_set_control_value)

            elif ('menu' in control['type']):

                label = Qt.QLabel(labeltext)
                qctrl1 = Qt.QComboBox()

                for itemidx in control['menu']:
                    qctrl1.insertItem(control['menu'][itemidx], str(itemidx))

                qctrl1.setCurrentIndex(int(curr_val))
                qctrl1.currentIndexChanged.connect(self._ui_set_control_value)

            elif (control['type'] == 'string'):
                qctrl1 = Qt.QLineEdit()

                label = Qt.QLabel(labeltext)

                mins = "X"*control['min']
                maxs = "x"*(control['max']-control['min'])
                mask = mins+maxs+";\n"

                qctrl1.setInputMask(mask)
                qctrl1.setText(str(curr_val))
                qctrl1.textChanged.connect(self._ui_set_control_text)

            elif (control['type'] == 'bool'):
                qctrl1 = Qt.QCheckBox(labeltext)
                qctrl1.setCheckState(int(curr_val > 0)*2)
                qctrl1.stateChanged.connect(self._ui_set_control_bool)

            elif (control['type'] == 'button'):
                qctrl1 = Qt.QPushButton(labeltext)
                qctrl1.stateChanged.connect(self._ui_set_control_bool)

            elif (control['type'] == 'bitmask'):
                label = Qt.QLabel(labeltext)
                qctrl1 = Qt.QLineEdit()
                qctrl1.setInputMask("\\0\\xHHHH;\n")
                try:
                    sval = "{0:032X}".format(curr_val)
                except:
                    try:
                        if '0x' == curr_val[0:2]:
                            sval = "{0:032X}".format(int(curr_val[0:2], 16))
                        else:
                            sval = "{0:032X}".format(int(curr_val, 16))
                    except:
                        sval = str(curr_val)

                qctrl1.setText(sval)
                qctrl1.textChanged.connect(self._ui_set_control_bitmask)

            if label is not None:
                layout.addWidget(label, row, 0)
                label.setWordWrap(True)

            if qctrl1 is not None:
                qctrl1.ctrlclass = control['type']
                qctrl1.ctrlid = controlname
                layout.addWidget(qctrl1, row, 1)

            if qctrl2 is not None:
                qctrl2.ctrlclass = control['type']
                qctrl1.ctrlid = controlname
                layout.addWidget(qctrl2, row, 2)

            row += 1

        area = QtGui.QScrollArea()
        area.setWidget(widget)
        tab_widget.addTab(area, "User controls")
        return tab_widget

    def _ui_set_pixelformat(self, idx):
        fmt_menu = self._control_ui.findChild(QtGui.QComboBox, "format menu")
        if fmt_menu is None:
            return

        pixelformat = str(fmt_menu.itemData(idx).toString())
        self.setPixelFormat(pixelformat)
        self._qt_ui_helper_update_frame_sizes(
            self._control_ui.findChild(QtGui.QComboBox, "size menu"))
        self._refresh_ui_controls()

    def _ui_set_frame_size(self, idx):
        frm_menu = self._control_ui.findChild(QtGui.QComboBox, "size menu")
        if frm_menu is None:
            return

        size = frm_menu.itemData(idx).toSize()

        self.setFrameSize(int(size.width()), int(size.height()))
        self._qt_ui_helper_update_framerates(
            self._control_ui.findChild(QtGui.QComboBox, "framerate menu"))
        self._refresh_ui_controls()

    def _ui_set_framerate(self, idx):
        fps_menu = self._control_ui.findChild(QtGui.QComboBox,
                                              "framerate menu")
        if fps_menu is None:
            return

        fps = fps_menu.itemData(idx).toFloat()[0]
        self.setFrameRate(fps)
        self._refresh_ui_controls()

    def _ui_set_control_value(self, value):
        if isinstance(self._control_ui, QtCore.QObject):
            ctrlid = self._control_ui.sender().ctrlid
        else:
            return False
        return self._set_control_value(ctrlid, value)

    def _ui_set_control_text(self, text):
        if isinstance(self._control_ui, QtCore.QObject):
            ctrlid = self._control_ui.sender().ctrlid
        else:
            return False
        return self._set_control_value(ctrlid, str(text))

    def _ui_set_control_bool(self, checked):
        if isinstance(self._control_ui, QtCore.QObject):
            ctrlid = self._control_ui.sender().ctrlid
        else:
            return False
        value = int(checked > 0)
        return self._set_control_value(ctrlid, value)

    def _ui_set_control_bitmask(self, text):
        if isinstance(self._control_ui, QtCore.QObject):
            ctrlid = self._control_ui.sender().ctrlid
        else:
            return False
        value = int(str(text)[2:], 16)
        return self._set_control_value(ctrlid, value)

    def _set_control_value(self, ctrlid, value):
        if not setV4L2Ctrl(self._filename, ctrlid, value):
            return False
        return value == getV4L2Ctrl(ctrlid)

    def getFrame(self):
        self.lastframe = self._device.read()[1][..., (2, 1, 0)]
        return self.lastframe

    def mainloop(self):
        while (cv2.waitKey(1) != 27):
            cv2.imshow('mywin', self.getFrame())
            self._control_ui.show()
        self._device.release()
        return True

    def getPixelFormat(self):
        return getV4L2Format(self._filename)

    def setPixelFormat(self, fmt):
        _4CC = cv2.FOURCC(*list(fmt[0:4]))
        if self._device.set(cv2.CAP_PROP_FOURCC, _4CC):
            return True

        if not setV4L2Format(self._filename, 'pixelformat='+str(fmt)):
            return False

        return str(fmt) == self.getPixelFormat()

    def getFrameSize(self):
        size = getV4L2FrameSize(self._filename)
        return (int(size[0]), int(size[1]))

    def setFrameSize(self, width, height):

        if (self._device.set(3, int(width)) and
                self._device.set(4, int(height))):
            return True

        if not setV4L2Format(self._filename,
                             'width='+str(width)+',height='+str(height)):
            return False

        return (width, height) == self.getFrameSize()

    def getFrameRate(self):
        # NOTE: *very* often the function get is broken!
        val = self._device.get(cv2.CAP_PROP_FPS)

        if val > 0:
            return val

        try:
            v4l2_ctl = subprocess.Popen(['v4l2-ctl',
                                         '--device='+self._filename,
                                         '--get-parm'],
                                        stdout=subprocess.PIPE)
            v4l2_ctl.wait()
            rawdata = v4l2_ctl.stdout.read()
            rawdata = rawdata.replace(' ', '')
            rawdata = rawdata.replace('\t', '')
        except:
            return -1

        pos1 = rawdata.find('Framespersecond:') + 16
        pos2 = rawdata.find('(', pos1)

        fps = rawdata[pos1:pos2]
        return float(fps)

    def setFrameRate(self, fps):
        # NOTE: *very* often the function get is broken!
        if self._device.set(cv2.CAP_PROP_FPS, fps):
            return True

        try:
            v4l2_ctl = subprocess.Popen(['v4l2-ctl',
                                         '--device='+self._filename,
                                         '--set-parm='+str(fps)],
                                        stdout=subprocess.PIPE)
            v4l2_ctl.wait()
        except:
            return False

        if fps == self.getFrameRate():
            return True
        else:
            return False


class CaptureJob(Qt.QObject):
    # capture scheduler interface
    TypeVideo = 0
    TypeFrames = 1

    StatusError = -2
    StatusDone = -1
    StatusInactive = 0
    StatusInProgress = 1
    StatusActive = 2
    StatusWaiting = 3

    def __init__(self, destdir, name, deviceid=0, captype=1, parent=None):
        log.log(repr(self),
                "Initializing video capture job \'"+str(name)+"\'",
                level=logging.DEBUG)
        Qt.QObject.__init__(self)
        self.name = name
        self._start_time = 0
        self._end_time = 0
        self._n_of_frames = 0
        self._device = deviceid
        self.type = captype
        self._destdir = destdir
        self._status = 0
        self._parent = parent
        self._delay = 0
        self._output_file_type = "avi"
        self._capture_thread = None

    def __del__(self):
        log.log(repr(self),
                "Deleting video capture job \'"+self.name+"\'",
                level=logging.DEBUG)
        if self._capture_thread is not None:
            self.stop()

    def isDone(self):
        return bool(self._status == -1)

    def isActive(self):
        return bool(self._status > 0)

    def getDelay(self):
        return self._delay

    def getStatus(self):
        return self._status

    def getDestinationDir(self):
        return self._destdir

    def getName(self):
        return self.name

    def getType(self):
        return self.type

    def getCaptureDevice(self):
        return self._device

    def getStartTime(self):
        return self._start_time

    def getEndTime(self):
        return self._end_time

    def getNumberOfFrames(self):
        return self._n_of_frames

    def setDelay(self, val):
        self._delay = val

    def setDestinationDir(self, destdir):
        self._destdir = destdir

    def setName(self, name):
        self.name = name

    def setType(self, tpy):
        self.type = tpy

    def setCaptureDevice(self, deviceid):
        self._device = deviceid

    def activate(self):
        self._status = self.StatusWaiting

    def start(self):
        if self._status != self.StatusInProgress:
            log.log(repr(self),
                    "job \'"+self.name+"\': Starting video capture thread",
                    level=logging.DEBUG)
            self._status = self.StatusInProgress
            self._capture_thread = QtCore.QThread()
            # moving to a working thread
            self.moveToThread(self._capture_thread)
            self._capture_thread.started.connect(
                self.__threaded_video_capturing)
            self._capture_thread.start()
            return True
        else:
            # ignoring the call since the job is already started
            return False

    def stop(self):
        if ((self._status != self.StatusDone) and
                (self._capture_thread is not None)):
            log.log(repr(self),
                    "job \'"+self.name+"\': Stopping video capture thread",
                    level=logging.DEBUG)
            self._status = self.StatusDone
            self._capture_thread.quit()
            self._capture_thread.wait()
            self._capture_thread.deleteLater()
            del self._capture_thread
            self._capture_thread = None
            return True
        else:
            # ignoring the call since the job is already stopped
            return False

    def reset(self):
        self.stop()
        self._status = self.StatusInactive

    def __threaded_video_capturing(self):

        device_is_closed = not self._device.isOpened()

        if device_is_closed:
            if not self._device.open():
                self._status = self.StatusError

        # requesting the exclusive use of the device
        if self._device.requestLock():
            captured_frames = 0

            if self.type == self.TypeVideo:
                hexcnt = 0
                file_name = os.path.join(self.getDestinationDir(),
                                         str(self.name) +
                                         "-{0:04x}.".format(hexcnt) +
                                         self._output_file_type)

                # checking if the file already exists
                while os.path.exists(file_name):
                    hexcnt += 1
                    file_name = os.path.join(self.getDestinationDir(),
                                             str(self.name) +
                                             "-{0:04x}.".format(hexcnt) +
                                             self._output_file_type)

                fps = self._device.getFrameRate()
                sze = self._device.getFrameSize()
                fcc = v4l2.v4l2_fourcc('I', 'Y', 'U', 'V')

                log.log(repr(self),
                        "Opening video file \'"+file_name+"\'",
                        level=logging.INFO)

                log.log(repr(self),
                        "video fps:"+str(fps),
                        level=logging.DEBUG)

                log.log(repr(self),
                        "video size:"+str(sze),
                        level=logging.DEBUG)

                video_writer = cv2.VideoWriter(file_name, fcc, fps, sze)
                if video_writer.isOpened():
                    while(self._status == self.StatusInProgress):
                        try:
                            video_writer.write(
                                self._device.getFrame()[..., (2, 1, 0)])
                        except Exception as exc:
                            log.log(repr(self),
                                    "An error has occured during " +
                                    "video capturing:\'"+str(exc)+"\'",
                                    level=logging.ERROR)
                            self._status = self.StatusError
                            break
                        captured_frames += 1
                    video_writer.release()
                else:
                    log.log(repr(self),
                            "Cannot write to the file \'"+file_name+"\'",
                            level=logging.ERROR)
                    self._status = self.StatusError

            elif self.type == self.TypeFrames:
                hexcnt = 0
                dir_name = os.path.join(
                    self.getDestinationDir(),
                    str(self.name)+"-{0:04x}".format(hexcnt))

                # checking if the file already exists
                while os.path.exists(dir_name):
                    hexcnt += 1
                    dir_name = os.path.join(
                        self.getDestinationDir(),
                        str(self.name)+"-{0:04x}".format(hexcnt))

                try:
                    os.mkdir(dir_name)
                except Exception as exc:
                    log.log(repr(self),
                            "Cannot create output directory\'" +
                            str(dir_name)+"\':\'"+str(exc)+"\'",
                            level=logging.ERROR)
                    self._status = self.StatusError

                while (self._status == self.StatusInProgress):
                    file_name = os.path.join(dir_name,
                                             "{0:08x}".format(captured_frames))
                    frm = utils.Frame(file_name)
                    try:
                        frm.saveData(data=self._device.getFrame(),
                                     force_overwrite=True,
                                     save_dlg=False,
                                     frmat='fits',
                                     bits='16')
                    except Exception as exc:
                        log.log(repr(self),
                                "An error has occured during " +
                                "image capturing:\'"+str(exc)+"\'",
                                level=logging.ERROR)
                        self._status = self.StatusError
                        break
                    captured_frames += 1
            else:
                pass
        else:
            self._status = self.StatusError

        # waiting for the device to release the exclusive lock
        self._device.requestUnlock()

        if device_is_closed:
            self._device.close()

        # back to main thread
        self.moveToThread(QtGui.QApplication.instance().thread())

    def setStartTime(self, time):
        if isinstance(time, Qt.QDateTime):
            self._start_time = time.toMSecsSinceEpoch()
        else:
            self._start_time = float(time)

    def setEndTime(self, time):
        if isinstance(time, Qt.QDateTime):
            self._end_time = time.toMSecsSinceEpoch()
        else:
            self._end_time = float(time)

    def setNumberOfFrames(self, n):
        # n < 0 means that the job will never end uless manually stopped
        self._n_of_frames = n
        if n < 0:
            self.setEndTime(self.getStartTime()-1)


class CaptureScheduler(Qt.QObject):

    def __init__(self, capture_device=None):
        Qt.QObject.__init__(self)
        self.jobs = {}
        self._controlgui = uic.loadUi(
            os.path.join(paths.UI_PATH, 'sched_dialog.ui'))
        self._controlgui.jobListWidget.setSortingEnabled(False)

        self.jobTimeView = Qt.QLabel()

        self.jobTimeView.setAlignment(QtCore.Qt.AlignTop)
        self._controlgui.timeViewScrollArea.setWidget(self.jobTimeView)
        self._controlgui.timeViewScrollArea.setAlignment(QtCore.Qt.AlignTop)

        # reimplemented paintEvent callback
        self.jobTimeView.paintEvent = self.jobTimeViewPaintEvent

        self._timer = Qt.QTimer()
        self._timer.setInterval(100)

        self._timescale = 0.01
        self._past_view = 20000

        self._lock_ctrls(True)
        self._refreshing = False
        self._current_job = None
        self._global_status = False

        self._capture_device = None
        self.setCaptureDevice(capture_device)

        self._global_time = Qt.QDateTime()

        self._controlgui.addJobPushButton.setIcon(
            utils.getQIcon("document-new"))
        self._controlgui.deleteJobPushButton.setIcon(
            utils.getQIcon("edit-delete"))
        self._controlgui.deleteAllJobsPushButton.setIcon(
            utils.getQIcon("edit-delete"))
        self._controlgui.confirmPushButton.setIcon(
            utils.getQIcon("ok"))
        self._controlgui.closePushButton.setIcon(
            utils.getQIcon("window-close"))

        self._controlgui.jobListWidget.currentRowChanged.connect(
            self.refreshJobInfo)
        self._controlgui.addJobPushButton.clicked.connect(
            self.addJob)
        self._controlgui.deleteJobPushButton.clicked.connect(
            self.deleteJob)
        self._controlgui.deleteAllJobsPushButton.clicked.connect(
            self.deleteAllJobs)
        self._controlgui.confirmPushButton.clicked.connect(
            self._choosEditeAction)

        self._controlgui.startTimeNowRadioButton.toggled.connect(
            self.updateCurrentJobStartType)
        self._controlgui.startTimeAtRadioButton.toggled.connect(
            self.updateCurrentJobStartType)

        self._controlgui.endTimeDurationRadioButton.toggled.connect(
            self.updateCurrentJobEndType)
        self._controlgui.endTimeAtRadioButton.toggled.connect(
            self.updateCurrentJobEndType)
        self._controlgui.endTimeFramesRadioButton.toggled.connect(
            self.updateCurrentJobEndType)

        self._controlgui.captureTypeComboBox.currentIndexChanged.connect(
            self.updateCurrentJobType)
        self._controlgui.startDateTimeEdit.dateTimeChanged.connect(
            self.updateCurrentJobStartTime)
        self._controlgui.endDateTimeEdit.dateTimeChanged.connect(
            self.updateCurrentJobEndTime)
        self._controlgui.durationDoubleSpinBox.valueChanged.connect(
            self.updateCurrentJobDuration)
        self._controlgui.delayDoubleSpinBox.valueChanged.connect(
            self.updateCurrentJobDelay)

        self._timer.timeout.connect(self._updateAll)
        self._timer.start()

    def jobTimeViewPaintEvent(self, obj):
        xoff = int(self._past_view*self._timescale)

        painter = Qt.QPainter(self.jobTimeView)

        painter.setFont(Qt.QFont("Arial", 8))

        wmax = painter.device().width()
        hmax = painter.device().height()

        step = 10
        bigstep = 100
        bigstepround = 10000

        y0 = 10
        y1 = 15
        y2 = 25

        w0 = wmax/(2*step)

        _ctime = utils.getCurrentTimeMsec()
        _ctime_int = int(_ctime/bigstepround)*bigstepround

        _date = Qt.QDateTime()

        for x0 in range(-xoff, wmax+int(bigstep), step):

            time = (x0/self._timescale) + _ctime_int

            x = xoff+(time - _ctime)*self._timescale

            if x0 % bigstep == 0:
                _date.setMSecsSinceEpoch(time)

                txt = _date.toString("hh:mm:ss")

                painter.drawText(x-w0, 0,
                                 2*w0, y0,
                                 QtCore.Qt.AlignCenter,
                                 txt)
                painter.drawLine(x, y0, x, y1)
            else:
                painter.drawLine(x, y1, x, y1-2)

        for job in self.jobs.values():

            endless = (job._end_type == 2) and (job.getNumberOfFrames() < 0)

            if endless:
                x0 = xoff + (job.getStartTime()-_ctime)*self._timescale
                if x0 < 0:
                    x0 = 0
                    w = xoff
                else:
                    w = xoff - x0
            else:
                x0 = xoff + (job.getStartTime()-_ctime)*self._timescale
                w = (job.getEndTime()-job.getStartTime())*self._timescale

            if x0+w < 0:  # don't waste time drawing things
                continue  # that are not visible anymore

            status = job.getStatus()

            rect = Qt.QRectF(x0, y1+4, w, y2)

            if status == CaptureJob.StatusInactive:
                # Waiting the for the user fish the
                # editing and activate the job
                painter.setBrush(QtCore.Qt.gray)
                painter.drawRect(rect)
            elif status == CaptureJob.StatusInProgress:
                # Job is active and capturing is in progress
                painter.setBrush(QtCore.Qt.yellow)
                painter.drawRect(rect)
                painter.setBrush(QtCore.Qt.green)
                painter.drawRect(x0, y1+4, xoff-x0, y2)
            elif status == CaptureJob.StatusDone:
                # Job is active and capturing is completed
                painter.setBrush(QtCore.Qt.green)
                painter.drawRect(rect)
            elif status == CaptureJob.StatusWaiting:
                # Job is waiting until the start time is reached
                painter.setBrush(QtCore.Qt.white)
                painter.drawRect(rect)
            elif status == CaptureJob.StatusError:
                painter.setBrush(QtCore.Qt.red)
                painter.drawRect(rect)
            else:
                pass

            painter.setBrush(QtCore.Qt.NoBrush)

            painter.drawText(rect,
                             QtCore.Qt.AlignCenter,
                             job.name+"\n"+job._status_text)

        painter.drawLine(xoff, y0, xoff, hmax)

        painter.setBrush(QtCore.Qt.black)

        painter.drawPolygon(Qt.QPointF(xoff, y0+5),
                            Qt.QPointF(xoff+2.5, y0),
                            Qt.QPointF(xoff-2.5, y0))

        del _date
        return QtGui.QLabel.paintEvent(self.jobTimeView, obj)

    def setCaptureDevice(self, device):
        self._capture_device = device
        if device is None:
            self._controlgui.endTimeFramesRadioButton.setChecked(False)
        else:
            self._controlgui.endTimeFramesRadioButton.setEnabled(True)

    def getCaptureDevice(self):
        return self._capture_device

    def _lock_ctrls(self, locked=True):
        self._controlgui.deleteJobPushButton.setDisabled(locked)
        self._controlgui.deleteAllJobsPushButton.setDisabled(locked)
        self._controlgui.jobPropGroupBox.setDisabled(locked)
        self._controlgui.statusProgressBar.reset()
        self._controlgui.statusProgressBar.setMinimum(-int(locked))
        self._controlgui.statusLabel.setText("")

    def _lock_edit_ctrls(self, locked=True):
        self._controlgui.captureTypeComboBox.setDisabled(locked)
        self._controlgui.startTimeGroupBox.setDisabled(locked)
        self._controlgui.endTimeGroupBox.setDisabled(locked)
        self._controlgui.deleteJobPushButton.setDisabled(locked)
        self._controlgui.deleteAllJobsPushButton.setDisabled(locked)
        self._controlgui.addJobPushButton.setDisabled(locked)

    def exec_(self):
        return self._controlgui.exec_()

    def show(self):
        return self._controlgui.show()

    def hide(self):
        return self._controlgui.hide()

    def addJobs(self, jobs):
        for job in jobs:
            self.addJob(jobs[job], job)

    def addJob(self, job=None, jobid=None):

        add_new_job = not isinstance(job, CaptureJob)

        if add_new_job:
            log.log(repr(self),
                    "Adding a new video capture job to the scheduler",
                    level=logging.INFO)
            if (jobid is None) or (jobid in self.jobs.keys()):
                jobid = hex(Qt.QDateTime.toMSecsSinceEpoch(
                    Qt.QDateTime.currentDateTime()))
                jobid = jobid[2:-1].upper()
            destdir = paths.CAPTURED_PATH
            duration = 10000
            start_time = self.getLastJobEndsTime()
            end_time = start_time + duration
            captype = CaptureJob.TypeVideo

            log.log(repr(self),
                    "job ID : "+jobid,
                    level=logging.DEBUG)

            newjob = CaptureJob(destdir, jobid, self._capture_device, captype)
            newjob.setStartTime(start_time)
            newjob.setEndTime(end_time)
            newjob._status_text = ""

            self.jobs[jobid] = newjob
            self._current_job = newjob

            newjob._start_type = 0
            newjob._end_type = 0

        elif job not in self.jobs.values():
            log.log(repr(self),
                    "Adding an existing video capture job to the scheduler",
                    level=logging.INFO)
            if jobid is None:
                jobid = hex(Qt.QDateTime.toMSecsSinceEpoch(
                    Qt.QDateTime.currentDateTime()))
                jobid = jobid[2:-1].upper()
            log.log(repr(self),
                    "job ID : "+jobid,
                    level=logging.DEBUG)
            self.jobs[jobid] = job
        else:
            # the job is already scheduled
            log.log(repr(self),
                    "Trying to add to the scheduler a job already scheduled!",
                    level=logging.DEBUG)
            return

        itemname = "id: \"{0}\"".format(jobid)
        joblistwidgetitem = Qt.QListWidgetItem(
            itemname,
            self._controlgui.jobListWidget)
        joblistwidgetitem.jobid = jobid

        if add_new_job:
            end_date = Qt.QDateTime()
            end_date.setMSecsSinceEpoch(end_time)
            self.updateCurrentJobEndTime(end_date)
            self._controlgui.jobListWidget.setCurrentItem(joblistwidgetitem)
            self._controlgui.endDateTimeEdit.setDateTime(end_date)
            self._controlgui.durationDoubleSpinBox.setValue(duration/1000.0)

        self._updateListWidget()

        return jobid

    def setCurrentJob(self, job):
        if isinstance(job, CaptureJob):
            if job in self.jobs.values():
                for jobid in self.jobs:
                    if self.jobs[jobid] == job:
                        for item in self._controlgui.jobListWidget.items():
                            if item.jobid == jobid:
                                self._controlgui.jobListWidget.setCurrentItem(
                                    item)
                                return True
        elif type(job) is (str, unicode):
            if job in self.jobs.keys():
                for item in self._controlgui.jobListWidget.items():
                    if item.jobid == job:
                        self._controlgui.jobListWidget.setCurrentItem(item)
                        return True
        elif type(job) is int:
            self._controlgui.jobListWidget.setCurrentRow(job)
        else:
            self._controlgui.jobListWidget.setCurrentRow(-1)

    def updateCurrentJobStartType(self, arg):
        if self._controlgui.startTimeNowRadioButton.isChecked():
            self._current_job._start_type = 0
        else:
            self._current_job._start_type = 1

    def updateCurrentJobEndType(self, arg):
        if self._controlgui.endTimeDurationRadioButton.isChecked():
            self._current_job._end_type = 0
        elif self._controlgui.endTimeAtRadioButton.isChecked():
            self._current_job._end_type = 1
        else:
            self._current_job._end_type = 2

    def deleteJob(self):
        row = self._controlgui.jobListWidget.currentRow()
        joblistwidgetitem = self._controlgui.jobListWidget.takeItem(row)
        if joblistwidgetitem is not None:
            jobid = joblistwidgetitem.jobid
            log.log(repr(self),
                    "Deleting the video capture job \'"+jobid+"\'",
                    level=logging.DEBUG)
            job = self.jobs.pop(jobid)
            job.stop()
            del job
            del joblistwidgetitem
        self._updateListWidget()
        self.refreshJobInfo(row-1)

    def deleteAllJobs(self):
        log.log(repr(self),
                "Deleting all video capture jobs",
                level=logging.DEBUG)
        self._controlgui.jobListWidget.clear()
        self.jobs = {}
        self._updateListWidget()

    def getLastJobEndsTime(self):
        if self._controlgui.jobListWidget.count() > 0:
            row = self._controlgui.jobListWidget.count()-1
            jobid = self._controlgui.jobListWidget.item(row).jobid
            return self.getJob(jobid).getEndTime()
        else:
            return Qt.QDateTime.toMSecsSinceEpoch(
                Qt.QDateTime.currentDateTime())

    def refreshJobInfo(self, row):
        self._refreshing = True
        self._updateListWidget()
        joblistwidgetitem_curr = self._controlgui.jobListWidget.item(row)
        joblistwidgetitem_prev = self._controlgui.jobListWidget.item(row-1)
        joblistwidgetitem_next = self._controlgui.jobListWidget.item(row+1)

        if joblistwidgetitem_curr is not None:
            jobid = joblistwidgetitem_curr.jobid
            job = self.getJob(jobid)
            self._current_job = job

            if job._start_type == 0:
                self._controlgui.startTimeNowRadioButton.setChecked(True)
            elif job._start_type == 1:
                self._controlgui.startTimeAtRadioButton.setChecked(True)

            if job._end_type == 0:
                self._controlgui.endTimeDurationRadioButton.setChecked(True)
            elif job._end_type == 1:
                self._controlgui.endTimeAtRadioButton.setChecked(True)
            elif job._end_type == 2:
                self._controlgui.endTimeFramesRadioButton.setChecked(True)

            # setting capture date and time limits
            if joblistwidgetitem_prev is not None:
                prev_job = self.jobs[joblistwidgetitem_prev.jobid]
                start_date_limit = prev_job.getEndTime()+1
                min_start_date = Qt.QDateTime()
                min_start_date.setMSecsSinceEpoch(start_date_limit)
                self._controlgui.startDateTimeEdit.setMinimumDateTime(
                    min_start_date)
                del min_start_date
            else:
                self._controlgui.startDateTimeEdit.clearMinimumDateTime()

            if joblistwidgetitem_next is not None:
                next_job = self.jobs[joblistwidgetitem_next.jobid]
                end_date_limit = next_job.getStartTime()-1
                max_end_date = Qt.QDateTime()
                max_end_date.setMSecsSinceEpoch(end_date_limit)
                self._controlgui.endDateTimeEdit.setMaximumDateTime(
                    max_end_date)
                del max_end_date
            else:
                self._controlgui.endDateTimeEdit.clearMaximumDateTime()

            start_date = Qt.QDateTime()
            start_date.setMSecsSinceEpoch(job.getStartTime())

            end_date = Qt.QDateTime()
            end_date.setMSecsSinceEpoch(job.getEndTime())

            status = job.getStatus()
            duration = job.getEndTime() - job.getStartTime()

            if status == CaptureJob.StatusInactive:
                # Waiting the for the user fish the editing
                # and activate the job
                self._controlgui.statusProgressBar.setMaximum(0)
            else:
                self._controlgui.statusProgressBar.setMaximum(10000)

                if status == CaptureJob.StatusInProgress:
                    # Job is active and capturing is in progress
                    count = (utils.getCurrentTimeMsec()-job.getStartTime())
                    progress = 10000*count/duration

                    self._controlgui.statusProgressBar.setValue(progress)
                elif status == CaptureJob.StatusDone:
                    # Job is active and capturing is completed
                    self._controlgui.statusProgressBar.setValue(10000)
                elif status == CaptureJob.StatusWaiting:
                    # Job is waiting until the start time is reached
                    self._controlgui.statusProgressBar.setMaximum(0)
                elif status == CaptureJob.StatusError:
                    # Job has been stopped due to an error
                    self._controlgui.statusProgressBar.setMaximum(0)
                else:
                    self._controlgui.statusProgressBar.reset()

            self._controlgui.statusLabel.setText(job._status_text)
            self._controlgui.delayDoubleSpinBox.setValue(job.getDelay()/1000)
            self._controlgui.durationDoubleSpinBox.setValue(duration/1000.0)
            self._controlgui.startDateTimeEdit.setDateTime(start_date)
            self._controlgui.endDateTimeEdit.setDateTime(end_date)
            self._controlgui.jobIDLabel.setText(job.getName())
            self._controlgui.captureTypeComboBox.setCurrentIndex(job.getType())
        else:
            self._current_job = None
        self._refreshing = False

    def getJob(self, jobid):
        return self.jobs[jobid]

    def _updateAll(self, *args):
        _a_job_is_active = False
        _mintime = utils.getCurrentTimeMsec()
        _maxtime = 0

        self._controlgui.deleteAllJobsPushButton.setEnabled(
            (len(self.jobs) > 0) and not self._global_status)

        for row in range(self._controlgui.jobListWidget.count()):
            joblistwidgetitem = self._controlgui.jobListWidget.item(row)
            joblistwidgetitem_prev = self._controlgui.jobListWidget.item(row-1)
            if joblistwidgetitem is not None:
                jobid = joblistwidgetitem.jobid
                job = self.getJob(jobid)

                status = job.getStatus()

                _a_job_is_active |= job.isActive()

                if status == CaptureJob.StatusInactive:
                    # Waiting the for the user fish the
                    # editing and activate the job
                    joblistwidgetitem.setBackground(QtCore.Qt.lightGray)

                    status_txt = tr.tr("Inactive")

                    if job._start_type == 0:
                        delay = job.getDelay()
                        old_duration = job.getEndTime() - job.getStartTime()

                        curr_data_time = Qt.QDateTime.currentDateTime()
                        t_now = curr_data_time.toMSecsSinceEpoch()+delay

                        if joblistwidgetitem_prev is not None:
                            prevjob = self.getJob(joblistwidgetitem_prev.jobid)
                            t_last = prevjob.getEndTime() + delay
                            if t_now > t_last:
                                job.setStartTime(t_now)
                            else:
                                job.setStartTime(t_last)
                        else:
                            job.setStartTime(t_now)

                        job.setEndTime(job.getStartTime()+old_duration)

                elif status == CaptureJob.StatusDone:
                    # Job is active and capturing is completed
                    joblistwidgetitem.setBackground(QtCore.Qt.green)
                    status_txt = tr.tr("Completed")
                elif status == CaptureJob.StatusInProgress:
                    # Job is active and capturing is in progress
                    joblistwidgetitem.setBackground(QtCore.Qt.yellow)
                    count = (utils.getCurrentTimeMsec()-job.getStartTime())
                    status_txt = tr.tr("In progress")
                    status_txt += " {0:0.02f}sec".format(count/1000.0)
                    if job._end_type == 2:
                        if job.getNumberOfFrames() < 0:
                            # this means that the job will
                            # never end uless manually stopped
                            pass
                    elif utils.getCurrentTimeMsec() >= job.getEndTime():
                        job.stop()

                elif status == CaptureJob.StatusWaiting:
                    # Job is waiting until the start time is reached
                    joblistwidgetitem.setBackground(QtCore.Qt.white)
                    countdown = (utils.getCurrentTimeMsec()-job.getStartTime())
                    countdown /= 1000.0
                    status_txt = tr.tr("Waiting")
                    status_txt += " {0:0.02f} sec".format(countdown)
                    if utils.getCurrentTimeMsec() >= job.getStartTime():
                        job.start()
                elif status == CaptureJob.StatusError:
                    joblistwidgetitem.setBackground(QtCore.Qt.red)
                    status_txt = tr.tr("Error")
                else:
                    joblistwidgetitem.setBackground(QtCore.Qt.red)
                    status_txt = tr.tr("Unknown")

                job._status_text = status_txt

                start_time = job.getStartTime()
                end_time = job.getEndTime()

                _mintime = min(_mintime, start_time)
                _maxtime = max(_maxtime, end_time)

                start_date = Qt.QDateTime()
                start_date.setMSecsSinceEpoch(start_time)

                end_date = Qt.QDateTime()
                end_date.setMSecsSinceEpoch(end_time)

                fmt_str = "[ {5} ]\tid: \"{0}\" "
                fmt_str += "duration:{2:0.02f}  "
                fmt_str += "delay:{1:0.02f}  "
                fmt_str += "start: {3}  stop: {4}"

                itemname = fmt_str.format(
                    jobid,
                    job.getDelay()/1000.0,
                    (end_time-start_time)/1000.0,
                    start_date.toString("yyyy/MM/dd-hh:mm:ss.zzz"),
                    end_date.toString("yyyy/MM/dd-hh:mm:ss.zzz"),
                    status_txt)

                joblistwidgetitem.setText(itemname)

                if job == self._current_job:
                    self.refreshJobInfo(row)

        ww = _maxtime-utils.getCurrentTimeMsec() + self._past_view + 1000
        ww = int(ww*self._timescale)
        ww = max(self._controlgui.timeViewScrollArea.width(), ww)

        if (ww != self.jobTimeView.width()) and not self._global_status:
            self.jobTimeView.setMinimumWidth(ww)
            self.jobTimeView.setMaximumWidth(ww)

        self.jobTimeView.update()

        if self._global_status and not _a_job_is_active:
            self._choosEditeAction()

    def start(self):
        self._controlgui.confirmPushButton.setIcon(utils.getQIcon("stop"))
        self._controlgui.confirmPushButton.setText(tr.tr("Stop"))
        self._global_status = True
        self._lock_edit_ctrls(True)
        for job in self.jobs.values():
            job.activate()

    def stop(self):
        self._controlgui.confirmPushButton.setIcon(utils.getQIcon("ok"))
        self._controlgui.confirmPushButton.setText(tr.tr("Start"))
        self._global_status = False
        self._lock_edit_ctrls(False)
        for job in self.jobs.values():
            job.reset()

    def _choosEditeAction(self):
        if self._global_status:
            self.stop()
        else:
            self.start()
        self._updateAll()

    def updateCurrentJobType(self, idx):
        if self._refreshing:
            return
        self._current_job.setType(
            self._controlgui.captureTypeComboBox.currentIndex())

    def updateCurrentJobStartTime(self, start_date):
        if self._refreshing:
            return
        self._refreshing = True
        start_time = start_date.toMSecsSinceEpoch()

        if self._controlgui.endTimeDurationRadioButton.isChecked():
            duration_msec = self._controlgui.durationDoubleSpinBox.value()*1000
            end_time = start_time + duration_msec
            end_date = Qt.QDateTime()
            end_date.setMSecsSinceEpoch(end_time)
            self._controlgui.endDateTimeEdit.setDateTime(end_date)
            self._current_job.setEndTime(end_time)
        elif self._controlgui.endTimeAtRadioButton.isChecked():
            end_date_time = self._controlgui.endDateTimeEdit.dateTime()
            end_time = end_date_time.toMSecsSinceEpoch()
            duration = end_time - start_time
            self._controlgui.durationDoubleSpinBox.setValue(duration/1000.0)

        self._current_job.setStartTime(start_date)
        min_end_date = Qt.QDateTime()
        min_end_date.setMSecsSinceEpoch(start_time+1)
        self._controlgui.endDateTimeEdit.setMinimumDateTime(min_end_date)
        self._refreshing = False

    def updateCurrentJobEndTime(self, end_date):
        if self._refreshing:
            return
        self._refreshing = True
        start_date_time = self._controlgui.startDateTimeEdit.dateTime()
        start_time = start_date_time.toMSecsSinceEpoch()
        end_time = end_date.toMSecsSinceEpoch()
        duration = end_time - start_time

        self._current_job.setEndTime(end_date)
        self._controlgui.durationDoubleSpinBox.setValue(duration/1000.0)

        if self._capture_device is not None:
            fps = self._capture_device.getFrameRate()
            if fps >= 0:
                n_of_frames = int(duration*fps/1000)
                self._current_job.setNumberOfFrames(n_of_frames)
                self._controlgui.nFramesSpinBox.setValue(n_of_frames)
        self._refreshing = False

    def updateCurrentJobDelay(self, delay):
        if self._refreshing:
            return
        self._current_job.setDelay(delay*1000.0)

    def updateCurrentJobDuration(self, duration):
        if self._refreshing:
            return
        duration_msec = duration*1000.0

        self._refreshing = True
        start_date_time = self._controlgui.startDateTimeEdit.dateTime()
        start_time = start_date_time.toMSecsSinceEpoch()
        end_time = start_time + duration_msec
        end_date = Qt.QDateTime()
        end_date.setMSecsSinceEpoch(end_time)

        self._current_job.setEndTime(end_date)
        self._controlgui.endDateTimeEdit.setDateTime(end_date)

        if self._capture_device is not None:
            fps = self._capture_device.getFrameRate()
            if fps >= 0:
                fps = self._capture_device.getFrameRate()
                n_of_frames = int(duration*fps)
                self._current_job.setNumberOfFrames(n_of_frames)
                self._controlgui.nFramesSpinBox.setValue(n_of_frames)
        self._refreshing = False

    def _updateListWidget(self):
        if len(self.jobs) != self._controlgui.jobListWidget.count():
            # This should never never happens.
            utils.showErrorMsgBox(
                tr.tr("Somethig terrible wrong has happend!\n" +
                      "Please send a bug report to the author."),
                caller=self)
        elif len(self.jobs) <= 0:
            self._lock_ctrls(True)
        elif (len(self.jobs) > 0):
            if self._controlgui.jobListWidget.currentRow() >= 0:
                self._lock_ctrls(False)
            else:
                self._lock_ctrls(True)
                self._controlgui.deleteAllJobsPushButton.setEnabled(True)


#
# Some helper functions for v4l2 interface
#


def _list_v4l2_devices():
    devices = []
    for dev_file in os.listdir("/dev"):
        if (len(dev_file) > 5) and (dev_file[:5] == "video"):
            dev = os.path.join("/dev", dev_file)
            try:
                idx = int(dev_file[5:])
            except:
                continue

            vd = V4l2VideoDevice()
            if not vd.open(dev):
                del vd
                continue
            elif not vd.close():
                del vd
                continue
            else:
                devices.append({'device': vd,
                                'name': vd.getFullName(),
                                'file': dev,
                                'id': idx,
                                'interface': 'v4l2'})
    return devices


#
# some helper functions for cv2 interface
#


def _list_cv2_devices():
    devices = []
    for dev_file in os.listdir("/dev"):
        if (len(dev_file) > 5) and (dev_file[:5] == "video"):
            dev = os.path.join("/", "dev", dev_file)

            try:
                idx = int(dev_file[5:])
            except:
                continue

            try:
                v4l2_ctl = subprocess.Popen(
                    ['v4l2-ctl', '--device='+dev, '--info'],
                    stdout=subprocess.PIPE)
                v4l2_ctl.wait()
                data = v4l2_ctl.stdout.read().replace('\t', '').split('\n')
            except:
                continue

            dev_name = "Unknown"
            dev_bus = "unknown"
            for prop in data:
                lprop = prop.lower()
                if 'card type' in lprop:
                    dev_name = prop[prop.find(':')+1:].strip()
                elif 'bus info' in lprop:
                    dev_bus = prop[prop.find(':')+1:].strip()

            name = dev_name+" ("+dev_bus+")"

            vd = Cv2VideoDevice()
            if not vd.open(dev):
                del vd
                continue
            elif not vd.close():
                del vd
                continue
            else:

                vd.name = name
                vd._device_info['device name'] = name

                devices.append({'device': vd,
                                'name': name,
                                'file': dev,
                                'id': idx,
                                'interface': 'cv2'})
    return devices


def _parse_token(data, token, csep='=', cend=' ', casesensitive=False):
    if casesensitive:
        lodata = data
        lotoken = token
    else:
        lodata = data.lower()
        lotoken = token.lower()

    if lotoken not in lodata:
        return None
    else:
        start = lodata.find(lotoken)+len(lotoken)
        start = lodata.find(csep, start)+len(csep)
        end = lodata.find(cend, start)

        if end < 0:
            val = data[start:]
        else:
            val = data[start:end]

        return _autoType(val)


def _autoType(val):
    try:
        ret = float(val)
    except:
        try:
            ret = int(val)
        except:
            ret = val
    return ret


def setV4L2Format(device, cmd):
    try:
        v4l2_ctl = subprocess.Popen(
            ['v4l2-ctl',
             '--device='+device,
             '--set-fmt-video='+cmd])
        v4l2_ctl.wait()
    except:
        return False
    del v4l2_ctl
    return True


def getV4L2Format(device):
    fmt = {}
    try:
        v4l2_ctl = subprocess.Popen(
            ['v4l2-ctl',
             '--device='+device,
             '--get-fmt-video'],
            stdout=subprocess.PIPE)
        v4l2_ctl.wait()
        rawdata = v4l2_ctl.stdout.read().replace(' ', '').replace('\t', '')
    except Exception:
        return {}

    del v4l2_ctl
    fmt = _parse_token(rawdata, "PixelFormat", ':', '\n')[1:-1]
    return fmt


def getV4L2FrameSize(device):
    fmt = {}
    try:
        v4l2_ctl = subprocess.Popen(
            ['v4l2-ctl',
             '--device='+device,
             '--get-fmt-video'],
            stdout=subprocess.PIPE)
        v4l2_ctl.wait()
        rawdata = v4l2_ctl.stdout.read().replace(' ', '').replace('\t', '')
    except Exception:
        return {}

    del v4l2_ctl
    fmt = _parse_token(rawdata, "Width/Height", ':', '\n')
    w, h = fmt.split('/')
    return (int(w), int(h))


def getV4L2Ctrl(device, ctrl):
    try:
        v4l2_ctl = subprocess.Popen(
            ['v4l2-ctl',
             '--device='+device,
             '--get-ctrl='+ctrl],
            stdout=subprocess.PIPE)
        v4l2_ctl.wait()
        rawdata = v4l2_ctl.stdout.read().replace(' ', '').replace('\t', '')
    except:
        return None
    del v4l2_ctl
    return _parse_token(rawdata, ctrl, ':', '\n')


def setV4L2Ctrl(device, ctrl, data):
    try:
        v4l2_ctl = subprocess.Popen(
            ['v4l2-ctl',
             '--device='+device,
             '--set-ctrl='+ctrl+'='+str(data)])
        v4l2_ctl.wait()
    except:
        return False
    del v4l2_ctl


def getV4L2Fps(device):
    try:
        v4l2_ctl = subprocess.Popen(
            ['v4l2-ctl',
             '--device='+device,
             '--get-parm'],
            stdout=subprocess.PIPE)
        v4l2_ctl.wait()
        rawdata = v4l2_ctl.stdout.read().replace(' ', '').replace('\t', '')
    except:
        return False

    del v4l2_ctl

    pos1 = rawdata.find('Framespersecond:') + 16
    pos2 = rawdata.find('(', pos1)

    fps = rawdata[pos1:pos2]
    return float(fps)


def getV4L2DeviceProperties(device):
    formats = {}
    try:
        v4l2_ctl = subprocess.Popen(
            ['v4l2-ctl',
             '--device='+device,
             '--list-formats-ext'],
            stdout=subprocess.PIPE)
        v4l2_ctl.wait()
        rawdata = v4l2_ctl.stdout.read().replace(' ', '').replace('\t', '')
        del v4l2_ctl
    except:
        return {}

    blocks = rawdata.split('PixelFormat:\'')[1:]

    for block in blocks:
        format_name = block[:block.find('\'')]
        formats[format_name] = {}
        sizes = block.split('Size:Discrete')[1:]
        for size in sizes:
            lines = size.split('\n')
            size = lines[0]
            w, h = size.split('x')
            size = (int(w), int(h))
            formats[format_name][size] = []
            for line in lines[1:]:
                try:
                    fps = float(line[line.find('(')+1:line.find('fps)')])
                    formats[format_name][size].append(fps)
                except:
                    pass
    try:
        v4l2_ctl = subprocess.Popen(
            ['v4l2-ctl',
             '--device='+device,
             '-L'],
            stdout=subprocess.PIPE)
        v4l2_ctl.wait()
        rawdata = v4l2_ctl.stdout.readlines()
        del v4l2_ctl
    except:
        return {'formats': formats}

    props = {'formats': formats}

    for line in rawdata:
        if ' : ' in line:
            vals = line.replace('\n', '').replace('\r', '').split(':')
            name = vals[0][:vals[0].rfind('(')]
            name = name.replace(' ', '').replace('\t', '')
            typ = vals[0][vals[0].rfind('(')+1:vals[0].rfind(')')]

            props[name] = {
                'min': None,
                'max': None,
                'default': None,
                'value': None,
                'flags': None,
                'step': 1}

            for token in props[name]:
                props[name][token] = _parse_token(vals[1], token)

            props[name]['type'] = typ
            if typ == 'menu':
                props[name]['menu'] = {}

        elif ': ' in line:
            s = line.replace('\n', '').replace('\r', '').split(':')
            val = _autoType(s[0].replace(' ', '').replace('\t', ''))
            nme = s[1].replace(' ', '').replace('\t', '')
            props[name]['menu'][nme] = val
    return props
