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
import sys
import math
import time
import shutil
import webbrowser
import logging
from xml.dom import minidom

from PyQt4 import uic, Qt, QtCore, QtGui
import numpy as np
import scipy as sp
import cv2

import paths
import log
import utils
import styles
import videocapture
import imgfeatures
import mappedimage
import guicontrols
import colormaps as cmaps
import translation as tr
import lightcurves as lcurves


def Int(val):
    i = math.floor(val)
    if (val-i) < 0.5:
        return int(i)
    else:
        return int(math.ceil(val))


class theApp(Qt.QObject):

    def __init__(self, lang='', args=[]):

        Qt.QObject.__init__(self)

        self._fully_loaded = False

        self.checkArguments(args)

        log.log(repr(self),
                'Starting lxnstack...',
                level=logging.INFO)

        self._old_tab_idx = 0
        self.__operating = False           # used to avoid recursion loop
        self.__updating_mdi_ctrls = False  # used to avoid recursion loop
        self._updating_feature = False     # used to avoid recursion loop
        self._photo_time_clock = 0
        self._phase_align_data = None

        self.current_match_mode = cv2.TM_SQDIFF  # TODO: Add selection box

        self._generateOpenStrings()

        if not os.path.isdir(paths.TEMP_PATH):
            os.makedirs(paths.TEMP_PATH)

        if not os.path.isdir(paths.HOME_PATH):
            os.makedirs(paths.HOME_PATH)

        if not os.path.isdir(paths.CAPTURED_PATH):
            os.makedirs(paths.CAPTURED_PATH)

        self.temp_path = paths.TEMP_PATH

        self.__current_lang = lang
        self.zoom = 1
        self.min_zoom = 0
        self.actual_zoom = 1
        self.exposure = 0
        self.zoom_enabled = False
        self.zoom_fit = False
        self.current_dir = '~'

        self.wasCanceled = False
        self.__video_capture_stopped = False
        self.__video_capture_started = False
        self.isPreviewing = False
        self.shooting = False

        self.current_align_method = 0
        self.is_aligning = False

        self.image_idx = -1
        self.ref_image_idx = -1
        self.dif_image_idx = -1
        self.point_idx = -1
        self.star_idx = -1

        self.current_style = 0

        self._bas = None
        self._drk = None
        self._stk = None
        self._flt = None

        self._preview_data = None
        self._preview_image = None

        self._old_stk = None
        self._oldhst = None

        self.aap_rectangle = (256, 256)
        self.aap_wholeimage = 0

        self.manual_align = False

        self.ftype = np.float32

        self.mdi_windows = {}

        self.framelist = []
        self.biasframelist = []
        self.darkframelist = []
        self.flatframelist = []

        self.wnd = uic.loadUi(os.path.join(paths.UI_PATH,
                                           'main.ui'))
        self.dlg = guicontrols.OptionsDialog()
        self.about_dlg = guicontrols.AboutWindow()
        self.stack_dlg = guicontrols.StackingDialog()
        self.align_dlg = guicontrols.AlignmentDialog()
        self.video_dlg = guicontrols.VideSaveDialog()

        self.statusBar = self.wnd.statusBar()
        self.statusLabelMousePos = Qt.QLabel()

        self.mdi = self.wnd.mdiArea

        self.videoCaptureScheduler = videocapture.CaptureScheduler()

        self.buildMenus()
        self.setUpStatusBar()
        self.setUpToolBars()

        self.currentWidth = 0
        self.currentHeight = 0
        self.currentDepht = 0

        self.current_colormap = 0

        self.result_w = 0
        self.result_h = 0
        self.result_d = 3

        self.current_project_fname = None

        self.average_save_file = 'average'
        self.master_bias_save_file = 'master-bias'
        self.master_dark_save_file = 'master-dark'
        self.master_flat_save_file = 'master-flat'

        self.master_bias_file = None
        self.master_dark_file = None
        self.master_flat_file = None

        self.master_bias_mul_factor = 1.0
        self.master_dark_mul_factor = 1.0
        self.master_flat_mul_factor = 1.0

        self.tracking_align_point = False
        self.tracking_star_point = False

        self.checked_seach_dark_flat = 0
        self.checked_autodetect_rectangle_size = 2
        self.checked_autodetect_min_quality = 2
        self.checked_custom_temp_dir = 2
        self.custom_chkstate = 0
        self.ftype_idx = 0
        self.checked_compressed_temp = 0
        self.custom_temp_path = os.path.join(paths.HOME_PATH, '.temp')
        self.checked_show_phase_img = 2
        self.phase_interpolation_order = 0
        self.interpolation_order = 0
        self.use_image_time = True

        self.progress_dialog = Qt.QProgressDialog()
        self.progress_dialog.canceled.connect(self.canceled)

        self.frame_open_args = {'rgb_fits_mode': True,
                                'convert_cr2': False,
                                'assume_localtime': False,
                                'progress_bar': self.progress_dialog}

        self.current_cap_device = None
        self.current_cap_device_title = ""
        self.video_writer = cv2.VideoWriter()
        self.video_url = ''
        self.writing = False
        self.current_cap_combo_idx = -1
        self.devices = []

        self.max_points = 10
        self.min_quality = 0.20

        # exit callback
        self.wnd.closeEvent = self.mainWindowCloseEvent

        self.mdi.subWindowActivated.connect(self.updateMdiControls)

        self.wnd.alignGroupBox.setEnabled(False)
        self.mdi.setTabsClosable(True)
        self.mdi.setViewMode(QtGui.QMdiArea.TabbedView)
        self.wnd.manualAlignGroupBox.setEnabled(False)
        self.wnd.masterBiasGroupBox.setEnabled(False)
        self.wnd.masterDarkGroupBox.setEnabled(False)
        self.wnd.masterFlatGroupBox.setEnabled(False)
        self.wnd.masterBiasGroupBox.hide()
        self.wnd.masterDarkGroupBox.hide()
        self.wnd.masterFlatGroupBox.hide()
        self.wnd.magDoubleSpinBox.setEnabled(False)
        self.changeAlignMethod(self.current_align_method)

        self.wnd.addPushButton.clicked.connect(
            self.doLoadFiles)
        self.wnd.remPushButton.clicked.connect(
            self.removeImage)
        self.wnd.clrPushButton.clicked.connect(
            self.clearLightList)
        self.wnd.biasAddPushButton.clicked.connect(
            self.doAddBiasFiles)
        self.wnd.biasClearPushButton.clicked.connect(
            self.doClearBiasList)
        self.wnd.darkAddPushButton.clicked.connect(
            self.doAddDarkFiles)
        self.wnd.darkClearPushButton.clicked.connect(
            self.doClearDarkList)
        self.wnd.flatAddPushButton.clicked.connect(
            self.doAddFlatFiles)
        self.wnd.flatClearPushButton.clicked.connect(
            self.doClearFlatList)
        self.wnd.listCheckAllBtn.clicked.connect(
            self.checkAllListItems)
        self.wnd.listUncheckAllBtn.clicked.connect(
            self.uncheckAllListItems)
        self.wnd.alignDeleteAllPushButton.clicked.connect(
            self.clearAlignPoinList)
        self.wnd.starsDeleteAllPushButton.clicked.connect(
            self.clearStarsList)
        self.wnd.lightListWidget.currentRowChanged.connect(
            self.listItemChanged)
        self.wnd.lightListWidget.currentItemChanged.connect(
            self.showFrameItemInCurrentTab)
        self.wnd.darkListWidget.currentItemChanged.connect(
            self.showDarkFrameItemInCurrentTab)
        self.wnd.flatListWidget.currentItemChanged.connect(
            self.showFlatFrameItemInCurrentTab)
        self.wnd.biasListWidget.currentItemChanged.connect(
            self.showBiasFrameItemInCurrentTab)
        self.wnd.lightListWidget.itemDoubleClicked.connect(
            self.showFrameItemInNewTab)
        self.wnd.darkListWidget.itemDoubleClicked.connect(
            self.showDarkFrameItemInNewTab)
        self.wnd.flatListWidget.itemDoubleClicked.connect(
            self.showFlatFrameItemInNewTab)
        self.wnd.biasListWidget.itemDoubleClicked.connect(
            self.showBiasFrameItemInNewTab)
        self.wnd.listWidgetManualAlign.currentRowChanged.connect(
            self.manualAlignListItemChanged)
        self.wnd.listWidgetManualAlign.itemChanged.connect(
            self.currentManualAlignListItemChanged)
        self.wnd.starsListWidget.itemChanged.connect(
            self.starsListItemChanged)
        self.wnd.alignPointsListWidget.currentRowChanged.connect(
            self.alignListItemChanged)
        self.wnd.starsListWidget.currentRowChanged.connect(
            self.currentStarsListItemChanged)
        self.wnd.toolBox.currentChanged.connect(
            self.updateToolBox)
        self.wnd.spinBoxXAlign.valueChanged.connect(
            self.shiftX)
        self.wnd.spinBoxYAlign.valueChanged.connect(
            self.shiftY)
        self.wnd.spinBoxXStar.valueChanged.connect(
            self.shiftStarX)
        self.wnd.spinBoxYStar.valueChanged.connect(
            self.shiftStarY)
        self.wnd.innerRadiusDoubleSpinBox.valueChanged.connect(
            self.setInnerRadius)
        self.wnd.middleRadiusDoubleSpinBox.valueChanged.connect(
            self.setMiddleRadius)
        self.wnd.outerRadiusDoubleSpinBox.valueChanged.connect(
            self.setOuterRadius)
        self.wnd.magDoubleSpinBox.valueChanged.connect(
            self.setMagnitude)
        self.wnd.doubleSpinBoxOffsetX.valueChanged.connect(
            self.shiftOffsetX)
        self.wnd.doubleSpinBoxOffsetY.valueChanged.connect(
            self.shiftOffsetY)
        self.wnd.spinBoxOffsetT.valueChanged.connect(
            self.rotateOffsetT)
        self.wnd.addPointPushButton.clicked.connect(
            self.addAlignPoint)
        self.wnd.removePointPushButton.clicked.connect(
            self.removeAlignPoint)
        self.wnd.addStarPushButton.clicked.connect(
            self.addStar)
        self.wnd.removeStarPushButton.clicked.connect(
            self.removeStar)
        self.wnd.autoSetPushButton.clicked.connect(
            self.autoSetAlignPoint)
        self.wnd.autoDetectPushButton.clicked.connect(
            self.autoDetectAlignPoints)
        self.wnd.masterBiasCheckBox.stateChanged.connect(
            self.useMasterBias)
        self.wnd.masterDarkCheckBox.stateChanged.connect(
            self.useMasterDark)
        self.wnd.masterFlatCheckBox.stateChanged.connect(
            self.useMasterFlat)
        self.wnd.masterBiasPushButton.clicked.connect(
            self.loadMasterBias)
        self.wnd.masterDarkPushButton.clicked.connect(
            self.loadMasterDark)
        self.wnd.masterFlatPushButton.clicked.connect(
            self.loadMasterFlat)
        self.wnd.biasMulDoubleSpinBox.valueChanged.connect(
            self.setBiasMul)
        self.wnd.darkMulDoubleSpinBox.valueChanged.connect(
            self.setDarkMul)
        self.wnd.flatMulDoubleSpinBox.valueChanged.connect(
            self.setFlatMul)
        self.wnd.alignMethodComboBox.currentIndexChanged.connect(
            self.changeAlignMethod)

        self.dlg._dialog.devComboBox.currentIndexChanged.connect(
            self.setCurrentCaptureDevice)
        self.dlg._dialog.refreshPushButton.clicked.connect(
            self.updateCaptureDevicesList)
        self.dlg._dialog.fTypeComboBox.currentIndexChanged.connect(
            self.setFloatPrecision)
        self.dlg._dialog.tempPathPushButton.clicked.connect(
            self._set_temp_path)
        self.dlg._dialog.phaseIntOrderSlider.valueChanged.connect(
            self.setPhaseInterpolationOrder)
        self.dlg._dialog.intOrderSlider.valueChanged.connect(
            self.setInterpolationOrder)
        self.dlg._dialog.showPhaseImgCheckBox.stateChanged.connect(
            self.setShowPhaseIamge)

        self._resetPreferencesDlg()

        if not os.path.isdir(self.custom_temp_path):
            os.makedirs(self.custom_temp_path)

        self.updateCaptureDevicesList()

        self.newProject()

        log.log(repr(self),
                'Program started',
                level=logging.INFO)

    def setFullyLoaded(self):
        self._fully_loaded = True

    def fullyLoaded(self):
        return self._fully_loaded

    def __reload_modules__(self):
        # debug purpose only
        reload(paths)
        reload(utils)
        reload(styles)
        reload(videocapture)
        reload(imgfeatures)
        reload(mappedimage)
        reload(guicontrols)
        reload(colormaps)
        reload(translation)
        reload(lightcurves)

    def checkArguments(self, args):

        self.args = args

        # default values for project name

        if self.args['save_project'] is None:
            if self.args['load_project'] is not None:
                self.args['save_project'] = self.args['load_project']
            else:
                print("")
                print('No project name specified!')
                print('Please use --help for more informations')
                print("")
                sys.exit(1)

    def executeCommads(self):

        if self.args['load_project'] is not None:
            self.loadProject(self.args['load_project'])

        if self.args['add_images'] is not None:
            self.loadFiles(self.args['add_images'])

        if self.args['align'] is not None:
            self.wnd.toolBox.setCurrentIndex(1)

            if self.args['align'] == 'align-only':
                self.align(False, True, False)
            elif self.args['align'] == 'derotate-only':
                self.align(False, False, True)
            elif self.args['align'] == 'align-derotate':
                self.align(False, True, True)
            elif self.args['align'] == 'reset':
                self.align(True, False, False)

        if self.args['save_project']:
            self.current_project_fname = self.args['save_project']
            self._save_project()

        if self.args['stack'] is not None:
            val = self.args['stack']
            self.wnd.toolBox.setCurrentIndex(7)

            if val == 'average':
                stacking_mode = 0
            elif val == 'median':
                stacking_mode = 1
            elif val == 'sigma-clipping':
                stacking_mode = 2
            elif val == 'stddev':
                stacking_mode = 3
            elif val == 'variance':
                stacking_mode = 4
            elif val == 'maximum':
                stacking_mode = 5
            elif val == 'minimum':
                stacking_mode = 6
            elif val == 'maximum':
                stacking_mode = 7

            self.stack(stacking_mode)

        if self.args['lightcurve']:
            self.generateLightCurves(0)

        if self.args['style'] is not None:
            styles.setApplicationStyle(self.args['style'][0])

        self.setFullyLoaded()

    def criticalError(self, msg, msgbox=True):
        if msgbox:
            utils.showErrorMsgBox(msg, caller=self)
        else:
            log.log(repr(self),
                    msg,
                    level=logging.ERROR)
        sys.exit(1)

    def clearResult(self):

        del self._stk
        del self._drk
        del self._flt
        del self._preview_data

        self._stk = None
        self._bas = None
        self._drk = None
        self._flt = None
        self._preview_data = None
        self._preview_image = None

    def _generateOpenStrings(self):
        self.supported_formats = utils.getSupportedFormats()
        # all supported formats
        self.images_extensions = ' ('
        for ext in self.supported_formats.keys():
            self.images_extensions += '*'+str(ext)+' '
        self.images_extensions += ');;'

        ImageTypes = {}
        # each format
        for ext in self.supported_formats.keys():
            key = str(self.supported_formats[ext])

            if key in ImageTypes:
                ImageTypes[key] += ' *'+str(ext)
            else:
                ImageTypes[key] = ' *'+str(ext)

        for ext in ImageTypes:
            self.images_extensions += tr.tr('Image')+' '
            self.images_extensions += ext+' : '+ImageTypes[ext]
            self.images_extensions += '('+ImageTypes[ext]+');;'

    def setPhaseInterpolationOrder(self, val):
        self.phase_interpolation_order = val

    def setInterpolationOrder(self, val):
        self.interpolation_order = val

    def setShowPhaseIamge(self, val):
        self.checked_show_phase_img = val

    @QtCore.pyqtSlot(bool)
    def doLoadFiles(self, is_checked):
        self.loadFiles()

    @QtCore.pyqtSlot(bool)
    def doNewProject(self, is_checked):
        self.newProject()

    @QtCore.pyqtSlot(bool)
    def doSaveProjectAs(self, is_checked):
        self.saveProjectAs()

    @QtCore.pyqtSlot(bool)
    def doSaveProject(self, is_checked):
        self.saveProject()

    @QtCore.pyqtSlot(bool)
    def doLoadProject(self, is_checked):
        self.loadProject()

    @QtCore.pyqtSlot(bool)
    def doSetPreferences(self, is_checked):
        self.setPreferences()

    @QtCore.pyqtSlot(bool)
    def doShowAbout(self, is_checked):
        self.about_dlg.exec_()

    @QtCore.pyqtSlot(bool)
    def doShowUserMan(self, is_checked):
        self.showUserMan()

    @QtCore.pyqtSlot(bool)
    def doSaveVideo(self, is_checked):
        self.saveVideo()

    def changeAlignMethod(self, idx):
        self.current_align_method = idx

        if idx == 0:
            self.wnd.phaseGroupBox.show()
            self.wnd.alignGroupBox.hide()
        elif idx == 1:
            self.wnd.phaseGroupBox.hide()
            self.wnd.alignGroupBox.show()
        else:
            self.wnd.phaseGroupBox.hide()
            self.wnd.alignGroupBox.hide()
            # for other possible impementations

    def setFloatPrecision(self, idx):
        if idx == 0:
            self.ftype = np.float32
        elif idx == 1:
            self.ftype = np.float64

        log.log(repr(self),
                "setting float precision to " + str(self.ftype),
                level=logging.INFO)

    def showUserMan(self):
        webbrowser.open(os.path.join(paths.DOCS_PATH, 'usermanual.html'))

    def setBiasMul(self, val):
        self.master_bias_mul_factor = val

    def setDarkMul(self, val):
        self.master_dark_mul_factor = val

    def setFlatMul(self, val):
        self.master_flat_mul_factor = val

    def _resetPreferencesDlg(self):
        idx = self.dlg._dialog.langComboBox.findData(self.__current_lang)
        self.dlg._dialog.langComboBox.setCurrentIndex(idx)

        self.dlg._dialog.useCustomLangCheckBox.setCheckState(self.custom_chkstate)
        self.dlg._dialog.fTypeComboBox.setCurrentIndex(self.ftype_idx)

        self.dlg._dialog.rgbFitsCheckBox.setCheckState(
            int(self.frame_open_args['rgb_fits_mode'])*2)
        self.dlg._dialog.decodeCR2CheckBox.setCheckState(
            int(self.frame_open_args['convert_cr2'])*2)

        self.dlg._dialog.devComboBox.setCurrentIndex(self.current_cap_combo_idx)

        self.dlg._dialog.rWSpinBox.setValue(self.aap_rectangle[0])
        self.dlg._dialog.rHSpinBox.setValue(self.aap_rectangle[1])

        self.dlg._dialog.maxPointsSpinBox.setValue(self.max_points)
        self.dlg._dialog.minQualityDoubleSpinBox.setValue(self.min_quality)

        self.dlg._dialog.langFileLineEdit.setText(self.__current_lang)

        self.dlg._dialog.autoSizeCheckBox.setCheckState(
            self.checked_autodetect_rectangle_size)

        self.dlg._dialog.wholeImageCheckBox.setChecked(
            self.aap_wholeimage)

        self.dlg._dialog.autoSizeCheckBox.setChecked(
            self.checked_autodetect_rectangle_size)

        self.dlg._dialog.minQualitycheckBox.setCheckState(
            self.checked_autodetect_min_quality)

        self.dlg._dialog.autoFolderscheckBox.setCheckState(
            self.checked_seach_dark_flat)

        self.dlg._dialog.tempPathCheckBox.setCheckState(
            self.checked_custom_temp_dir)

        self.dlg._dialog.tempPathLineEdit.setText(
            self.custom_temp_path)

        self.dlg._dialog.compressedTempCheckBox.setCheckState(
            self.checked_compressed_temp)

        self.dlg._dialog.showPhaseImgCheckBox.setCheckState(
            self.checked_show_phase_img)

        self.dlg._dialog.phaseIntOrderSlider.setValue(
            self.phase_interpolation_order)

        self.dlg._dialog.intOrderSlider.setValue(
            self.interpolation_order)

        self.dlg._dialog.themeListWidget.setCurrentRow(
            self.current_style)

        if self.checked_custom_temp_dir == 2:
            self.temp_path = os.path.expandvars(self.custom_temp_path)
        else:
            self.temp_path = paths.TEMP_PATH

    def _set_temp_path(self):

        tmp_path = Qt.QFileDialog.getExistingDirectory(
            self.dlg,
            tr.tr("Choose the temporary folder"),
            self.temp_path,
            utils.DIALOG_OPTIONS)

        self.custom_temp_path = str(tmp_path)
        self.dlg._dialog.tempPathLineEdit.setText(self.custom_temp_path)

    def showCaptureProperties(self):

        self.dlg._dialog.tabWidget.setCurrentIndex(2)

        if self.isPreviewing:
            self.dlg._dialog.tabWidget.setCurrentIndex(2)
            self.dlg._dialog.show()
        else:
            current_tab_idx = self.dlg._dialog.tabWidget.currentIndex()
            self.dlg._dialog.exec_()
            self.dlg._dialog.tabWidget.setCurrentIndex(current_tab_idx)

    def setCurrentCaptureDevice(self, index):

        if self.current_cap_device is not None:
            if not self.current_cap_device.close():
                return False
            else:
                self.current_cap_device.lockStateChanged.disconnect(
                    self.dlg._dialog.refreshPushButton.setDisabled)
                self.dlg._dialog.controlsLayout.removeWidget(
                    self.current_cap_device.getControlUI())
                self.current_cap_device.getControlUI().setParent(None)
                self.current_cap_device.getControlUI().hide()

        self.current_cap_combo_idx = index
        self.current_cap_device = self.devices[index]['device']
        self.current_cap_device_title = self.dlg._dialog.devComboBox.currentText()
        self.current_cap_device.lockStateChanged.connect(
            self.dlg._dialog.refreshPushButton.setDisabled)

        log.log(repr(self),
                "Setting current capture device to " +
                str(self.current_cap_device),
                level=logging.INFO)

        _action_match = False
        for action in self.capture_devices_menu._video_action_group.actions():
            if index == action.index:
                _action_match = True
                action.setChecked(True)
                break

        if not _action_match:
            log.log(repr(self),
                    "BUG: no action for device " +
                    str(self.current_cap_device),
                    level=logging.DEBUG)

        self.action_enable_video.setEnabled(True)

        # adding the device's controls widget
        self.dlg._dialog.controlsLayout.addWidget(
            self.current_cap_device.getControlUI())
        self.current_cap_device.getControlUI().show()

        self.videoCaptureScheduler.setCaptureDevice(self.current_cap_device)

        if self.isPreviewing:
            self.current_cap_device.open()

    def _setCurrentCaptureDeviceFromActions(self, checked):
        for action in self.capture_devices_menu._video_action_group.actions():
            if action.isChecked():
                self.dlg._dialog.devComboBox.setCurrentIndex(action.index)

    def updateCaptureDevicesList(self):
        log.log(repr(self),
                "Updating video capture devices list",
                level=logging.DEBUG)
        self.devices = tuple(videocapture.listVideoDevices())
        self.dlg._dialog.devComboBox.clear()
        action_group = QtGui.QActionGroup(self.capture_devices_menu)
        self.capture_devices_menu._video_action_group = action_group
        self.capture_devices_menu.clear()

        for device in self.devices:
            index = self.devices.index(device)
            name = "[{0: ^6s}] {1}".format(device['interface'],
                                           device['name'])
            action = self.capture_devices_menu.addAction(name)
            action.index = index
            action.setCheckable(True)
            action.toggled.connect(self._setCurrentCaptureDeviceFromActions)
            self.capture_devices_menu._video_action_group.addAction(action)
            self.dlg._dialog.devComboBox.insertItem(index, name)

    def setPreferences(self):

        qtr = Qt.QTranslator()
        self.dlg._dialog.langComboBox.clear()
        for qmf in os.listdir(paths.LANG_PATH):
            fl = os.path.join(paths.LANG_PATH, qmf)
            if qtr.load(fl):
                self.dlg._dialog.langComboBox.addItem(qmf, fl)
        self._resetPreferencesDlg()

        if self.current_cap_combo_idx < 0:
            self.current_cap_combo_idx = 0

        self.dlg._dialog.devComboBox.setCurrentIndex(self.current_cap_combo_idx)

        if self.isPreviewing:
            self.dlg._dialog.tabWidget.setCurrentIndex(2)
            self.dlg._dialog.show()
            return True
        else:
            pass

        if self.dlg._dialog.exec_() == 1:
            # update settings
            r_w = int(self.dlg._dialog.rWSpinBox.value())
            r_h = int(self.dlg._dialog.rHSpinBox.value())

            self.aap_rectangle = (r_w, r_h)

            self.custom_chkstate = int(
                self.dlg._dialog.useCustomLangCheckBox.checkState())

            self.max_points = int(
                self.dlg._dialog.maxPointsSpinBox.value())

            self.min_quality = float(
                self.dlg._dialog.minQualityDoubleSpinBox.value())

            self.current_cap_combo_idx = int(
                self.dlg._dialog.devComboBox.currentIndex())

            self.aap_wholeimage = int(
                self.dlg._dialog.wholeImageCheckBox.checkState())

            self.checked_autodetect_rectangle_size = int(
                self.dlg._dialog.autoSizeCheckBox.checkState())

            self.frame_open_args['rgb_fits_mode'] = bool(
                int(self.dlg._dialog.rgbFitsCheckBox.checkState()) == 2)

            self.frame_open_args['convert_cr2'] = bool(
                int(self.dlg._dialog.decodeCR2CheckBox.checkState()) == 2)

            self.checked_autodetect_min_quality = int(
                self.dlg._dialog.minQualitycheckBox.checkState())

            self.checked_seach_dark_flat = int(
                self.dlg._dialog.autoFolderscheckBox.checkState())

            self.ftype_idx = int(
                self.dlg._dialog.fTypeComboBox.currentIndex())

            self.checked_custom_temp_dir = int(
                self.dlg._dialog.tempPathCheckBox.checkState())

            self.checked_compressed_temp = int(
                self.dlg._dialog.compressedTempCheckBox.checkState())

            self.custom_temp_path = str(
                self.dlg._dialog.tempPathLineEdit.text())

            self.current_style = int(
                    self.dlg._dialog.themeListWidget.currentRow())

            self.saveSettings()

            if self.checked_custom_temp_dir == 2:
                self.temp_path = self.custom_temp_path
            else:
                self.temp_path = paths.TEMP_PATH

            return True
        else:
            # discard changes
            self._resetPreferencesDlg()
            return False

    def _dismatchMsgBox(self, img):
        imw = img.shape[1]
        imh = img.shape[0]

        if len(img.shape) == 2:
            dep = 1 
        else:
            dep = img.shape[2]

        if self.framelist:
            if((imw != self.currentWidth) or
               (imh != self.currentHeight) or
               (dep != self.currentDepht)):
                utils.showErrorMsgBox(
                    tr.tr("Frame size or number of channels does not match."),
                    tr.tr('current size=') +
                    str(self.currentWidth) + 'x' +
                    str(self.currentHeight) +
                    tr.tr(' image size=') +
                    str(imw) + 'x' +
                    str(imh) + '\n' +
                    tr.tr('current channels=') +
                    str(self.currentDepht) +
                    tr.tr(' image channels=') +
                    str(dep),
                    parent=self.wnd,
                    caller=self)
                return True
            else:
                return False
        else:
            self.currentWidth = imw
            self.currentHeight = imh
            self.currentDepht = dep
            return False

    def unlockSidebar(self):
        if self.framelist:
            self.wnd.remPushButton.setEnabled(True)
            self.wnd.clrPushButton.setEnabled(True)
            self.wnd.listCheckAllBtn.setEnabled(True)
            self.wnd.listUncheckAllBtn.setEnabled(True)
            self.wnd.biasAddPushButton.setEnabled(True)
            self.wnd.darkAddPushButton.setEnabled(True)
            self.wnd.flatAddPushButton.setEnabled(True)
            self.wnd.masterBiasCheckBox.setEnabled(True)
            self.wnd.masterDarkCheckBox.setEnabled(True)
            self.wnd.masterFlatCheckBox.setEnabled(True)
            self.wnd.addStarPushButton.setEnabled(True)

            self.action_align.setEnabled(True)
            self.action_stack.setEnabled(True)
            self.action_save_video.setEnabled(True)

            for i in xrange(self.wnd.toolBox.count()):
                self.wnd.toolBox.setItemEnabled(i, True)

            if self.framelist[0].isRGB():
                self.action_enable_rawmode.setEnabled(False)
            else:
                self.action_enable_rawmode.setEnabled(True)

            if self.framelist[0].stars:
                self.action_gen_lightcurves.setEnabled(True)
        else:
            self.action_enable_rawmode.setEnabled(False)

    def lockSidebar(self):

        self.wnd.remPushButton.setEnabled(False)
        self.wnd.clrPushButton.setEnabled(False)
        self.wnd.listCheckAllBtn.setEnabled(False)
        self.wnd.listUncheckAllBtn.setEnabled(False)
        self.wnd.biasAddPushButton.setEnabled(False)
        self.wnd.darkAddPushButton.setEnabled(False)
        self.wnd.flatAddPushButton.setEnabled(False)
        self.wnd.masterBiasCheckBox.setEnabled(False)
        self.wnd.masterDarkCheckBox.setEnabled(False)
        self.wnd.masterFlatCheckBox.setEnabled(False)
        self.wnd.addStarPushButton.setEnabled(False)
        self.wnd.starsDeleteAllPushButton.setEnabled(False)
        self.wnd.removeStarPushButton.setEnabled(False)
        self.action_stack.setEnabled(False)
        self.action_align.setEnabled(False)
        self.action_save_video.setEnabled(False)
        self.action_gen_lightcurves.setEnabled(False)
        self.action_enable_rawmode.setChecked(False)
        self.action_enable_rawmode.setEnabled(False)

        self.wnd.toolBox.setItemEnabled(0, True)
        for i in xrange(self.wnd.toolBox.count()-1):
            self.wnd.toolBox.setItemEnabled(i+1, False)

    def lockRecording(self):
        self.lockSidebar()
        self.wnd.addPushButton.setEnabled(False)
        self.action_add_files.setEnabled(False)
        self.action_load_project.setEnabled(False)
        self.action_new_project.setEnabled(False)
        self.action_save_project.setEnabled(False)
        self.action_save_project_as.setEnabled(False)
        self.action_save_video.setEnabled(False)
        self.action_take_shot.setEnabled(False)
        self.action_stop_capture.setEnabled(True)
        self.action_start_capture.setEnabled(False)

        self.direct_capture_type_tcb.setEnabled(False)
        self.dlg._dialog.refreshPushButton.setEnabled(False)

        self.__video_capture_stopped = False
        self.__video_capture_started = True

    def unlockRecording(self):
        self.unlockSidebar()
        self.wnd.addPushButton.setEnabled(True)
        self.action_add_files.setEnabled(True)
        self.action_load_project.setEnabled(True)
        self.action_new_project.setEnabled(True)
        self.action_save_project.setEnabled(True)
        self.action_save_project_as.setEnabled(True)
        self.action_save_video.setEnabled(True)
        self.action_take_shot.setEnabled(True)
        self.action_stop_capture.setEnabled(False)
        self.action_start_capture.setEnabled(True)

        self.direct_capture_type_tcb.setEnabled(True)
        self.dlg._dialog.refreshPushButton.setEnabled(True)

        self.__video_capture_stopped = True
        self.__video_capture_started = False

    def oneShot(self):
        self.shooting = True

    def stopDirectVideoCapture(self):
        self.videoCaptureScheduler.stop()

        cs_gui = self.videoCaptureScheduler._controlgui
        cs_gui.jobPropGroupBox.setEnabled(True)
        cs_gui.jobListWidget.setEnabled(True)
        cs_gui.buttonsWidget.setEnabled(True)
        cs_gui.confirmPushButton.setEnabled(True)

        self.videoCaptureScheduler.deleteAllJobs()
        self.unlockRecording()
        try:
            self.videoCaptureScheduler.addJobs(
                self.videoCaptureScheduler.oldjoblist)
            del self.videoCaptureScheduler.oldjoblist
        except:
            pass

    def startDirectVideoCapture(self):

        self.videoCaptureScheduler.oldjoblist = self.videoCaptureScheduler.jobs

        self.videoCaptureScheduler.deleteAllJobs()

        jid = "direct-video-capturing-"+time.strftime("%Y%m%d-%H%M%S")

        direct_video_capture_job = self.videoCaptureScheduler.getJob(
            self.videoCaptureScheduler.addJob(jobid=jid))
        self.lockRecording()

        direct_video_capture_job.setType(
            self.direct_capture_type_tcb.currentIndex())
        direct_video_capture_job._end_type = 2
        direct_video_capture_job.setNumberOfFrames(-1)

        self.videoCaptureScheduler.setCurrentJob(None)

        cs_gui = self.videoCaptureScheduler._controlgui
        cs_gui.jobPropGroupBox.setEnabled(False)
        cs_gui.jobListWidget.setEnabled(False)
        cs_gui.buttonsWidget.setEnabled(False)
        cs_gui.confirmPushButton.setEnabled(False)
        self.videoCaptureScheduler.start()

    def enableVideoPreview(self, enabled=False, origin=None):

        if self.current_cap_device is not None:
            if enabled:
                if not self.current_cap_device.open():
                    return False

                self.action_start_capture.setEnabled(True)

                self.isPreviewing = True

                self.dlg._dialog.refreshPushButton.setEnabled(False)
                old_tooltip = str(self.dlg._dialog.refreshPushButton.toolTip())

                self.dlg._dialog.refreshPushButton.setToolTip(
                    tr.tr("Cannot refresh devices list") + ": " +
                    tr.tr("current device is in use"))

                log.log(repr(self),
                        "Starting live preview from device " +
                        str(self.current_cap_device),
                        level=logging.INFO)

                # preview main loop
                self.lockSidebar()

                self.direct_capture_type_tcb.setEnabled(True)
                while (self.isPreviewing):
                    QtGui.QApplication.instance().processEvents()
                    if self.current_cap_device.isLocked():
                        ndimage = self.current_cap_device.getLastFrame()
                    else:
                        ndimage = self.current_cap_device.getFrame()
                    self.showImage(ndimage,
                                   title=self.current_cap_device_title,
                                   override_cursor=False)

                self.current_cap_device.close()
                self.dlg._dialog.refreshPushButton.setEnabled(True)
                self.dlg._dialog.refreshPushButton.setToolTip(old_tooltip)
                self.stopDirectVideoCapture()
                self.action_start_capture.setEnabled(False)
                self.direct_capture_type_tcb.setEnabled(False)
            else:
                self.isPreviewing = False
                log.log(repr(self),
                        "Stopping live preview",
                        level=logging.INFO)

    def useMasterBias(self, state):
        if state == 2:
            self.wnd.masterBiasGroupBox.setEnabled(True)
            self.wnd.masterBiasGroupBox.show()
            self.wnd.biasFramesGroupBox.setEnabled(False)
            self.wnd.biasFramesGroupBox.hide()
        else:
            self.wnd.masterBiasGroupBox.setEnabled(False)
            self.wnd.masterBiasGroupBox.hide()
            self.wnd.biasFramesGroupBox.setEnabled(True)
            self.wnd.biasFramesGroupBox.show()

    def loadMasterBias(self):

        open_str = tr.tr("All supported images")
        open_str += self.images_extensions+";;"
        open_str += tr.tr("All files *.* (*.*)")

        master_bias_file = str(Qt.QFileDialog.getOpenFileName(
            self.wnd,
            tr.tr("Select master-dark file"),
            self.current_dir,
            open_str,
            None,
            utils.DIALOG_OPTIONS))

        if os.path.isfile(master_bias_file):
            try:
                i = utils.Frame(master_bias_file, **self.frame_open_args)
                if not i.is_good:
                    utils.showErrorMsgBox(tr.tr("Cannot open image") +
                                          " \"" + str(i.url) + "\"",
                                          parent=self.wnd,
                                          caller=self)
                    return False
                imw = i.width
                imh = i.height
                dep = i.getNumberOfComponents()
                if ((self.currentWidth == imw) and
                        (self.currentHeight == imh) and
                        (self.currentDepht == dep)):
                    self.master_bias_file = i.url
                    self.wnd.masterBiasLineEdit.setText(i.url)
                else:
                    utils.showErrorMsgBox(
                        tr.tr("Cannot use this file:") +
                        tr.tr(" size or number of channels does not match!"),
                        tr.tr('current size=') +
                        str(self.currentWidth) + 'x' +
                        str(self.currentHeight) + '\n' +
                        tr.tr('image size=') +
                        str(imw) + 'x' + str(imh) + '\n' +
                        tr.tr('current channels=') +
                        str(self.currentDepht) + '\n' +
                        tr.tr('image channels=') + str(dep),
                        parent=self.wnd,
                        caller=self)
                del i
            except Exception as exc:
                log.log(repr(self),
                        str(exc),
                        level=logging.ERROR)
                utils.showErrorMsgBox("", exc, caller=self)

    def useMasterDark(self, state):
        if state == 2:
            self.wnd.masterDarkGroupBox.setEnabled(True)
            self.wnd.masterDarkGroupBox.show()
            self.wnd.darkFramesGroupBox.setEnabled(False)
            self.wnd.darkFramesGroupBox.hide()
        else:
            self.wnd.masterDarkGroupBox.setEnabled(False)
            self.wnd.masterDarkGroupBox.hide()
            self.wnd.darkFramesGroupBox.setEnabled(True)
            self.wnd.darkFramesGroupBox.show()

    def loadMasterDark(self):

        open_str = tr.tr("All supported images")
        open_str += self.images_extensions+";;"
        open_str += tr.tr("All files *.* (*.*)")

        master_dark_file = str(Qt.QFileDialog.getOpenFileName(
            self.wnd,
            tr.tr("Select master-dark file"),
            self.current_dir,
            open_str,
            None,
            utils.DIALOG_OPTIONS))

        if os.path.isfile(master_dark_file):
            try:
                i = utils.Frame(master_dark_file, **self.frame_open_args)
                if not i.is_good:
                    utils.showErrorMsgBox(tr.tr("Cannot open image") +
                                          " \"" + str(i.url) + "\"",
                                          parent=self.wnd,
                                          caller=self)
                    return False
                imw = i.width
                imh = i.height
                dep = i.getNumberOfComponents()
                if ((self.currentWidth == imw) and
                        (self.currentHeight == imh) and
                        (self.currentDepht == dep)):
                    self.master_dark_file = i.url
                    self.wnd.masterDarkLineEdit.setText(i.url)
                else:
                    utils.showErrorMsgBox(
                        tr.tr("Cannot use this file:") +
                        tr.tr(" size or number of channels does not match!"),
                        tr.tr('current size=') +
                        str(self.currentWidth) + 'x' +
                        str(self.currentHeight) + '\n' +
                        tr.tr('image size=') +
                        str(imw) + 'x' + str(imh) + '\n' +
                        tr.tr('current channels=') +
                        str(self.currentDepht) + '\n' +
                        tr.tr('image channels=') + str(dep),
                        parent=self.wnd,
                        caller=self)
                del i
            except Exception as exc:
                log.log(repr(self),
                        str(exc),
                        level=logging.ERROR)
                utils.showErrorMsgBox("", exc, caller=self)

    def useMasterFlat(self, state):
        if state == 2:
            self.wnd.masterFlatGroupBox.setEnabled(True)
            self.wnd.masterFlatGroupBox.show()
            self.wnd.flatFramesGroupBox.setEnabled(False)
            self.wnd.flatFramesGroupBox.hide()
        else:
            self.wnd.masterFlatGroupBox.setEnabled(False)
            self.wnd.masterFlatGroupBox.hide()
            self.wnd.flatFramesGroupBox.setEnabled(True)
            self.wnd.flatFramesGroupBox.show()

    def loadMasterFlat(self):

        open_str = tr.tr("All supported images")
        open_str += self.images_extensions+";;"
        open_str += tr.tr("All files *.* (*.*)")

        master_flat_file = str(Qt.QFileDialog.getOpenFileName(
            self.wnd,
            tr.tr("Select master-flatfield file"),
            self.current_dir,
            open_str,
            None,
            utils.DIALOG_OPTIONS))
        if os.path.isfile(master_flat_file):
            try:
                i = utils.Frame(master_flat_file, **self.frame_open_args)
                if not i.is_good:
                    utils.showErrorMsgBox(tr.tr("Cannot open image") +
                                          " \"" + str(i.url) + "\"",
                                          parent=self.wnd,
                                          caller=self)
                    return False
                imw = i.width
                imh = i.height
                dep = i.getNumberOfComponents()
                if ((self.currentWidth == imw) and
                        (self.currentHeight == imh) and
                        (self.currentDepht == dep)):
                    self.master_flat_file = i.url
                    self.wnd.masterFlatLineEdit.setText(i.url)
                else:
                    utils.showErrorMsgBox(
                        tr.tr("Cannot use this file:") +
                        tr.tr(" size or number of channels does not match!"),
                        tr.tr('current size=') +
                        str(self.currentWidth) + 'x' +
                        str(self.currentHeight) + '\n' +
                        tr.tr('image size=') +
                        str(imw) + 'x' + str(imh) + '\n' +
                        tr.tr('current channels=') +
                        str(self.currentDepht) + '\n' +
                        tr.tr('image channels=') + str(dep),
                        parent=self.wnd,
                        caller=self)
                del i
            except Exception as exc:
                log.log(repr(self),
                        str(exc),
                        level=logging.ERROR)
                utils.showErrorMsgBox("", exc, caller=self)

    # closeEvent callback
    def mainWindowCloseEvent(self, event):
        if self._fully_loaded:
            val = utils.showYesNoMsgBox(
                tr.tr("Do you really want to quit?"),
                tr.tr("All unsaved changes will be lost!"),
                parent=self.wnd,
                caller=self)

            if val == Qt.QMessageBox.Yes:
                self.stopDirectVideoCapture()
                self.canceled()
                self.saveSettings()
                if os.path.exists(paths.TEMP_PATH):
                    shutil.rmtree(paths.TEMP_PATH)
                return QtGui.QMainWindow.closeEvent(self.wnd, event)
            elif val == Qt.QMessageBox.No:
                event.ignore()
            else:
                return QtGui.QMainWindow.closeEvent(self.wnd, event)
        else:
            event.ignore()

    def saveSettings(self):
        settings = Qt.QSettings()

        settings.beginGroup("mainwindow")
        settings.setValue("geometry",
                          self.wnd.saveGeometry())
        settings.setValue("window_state",
                          self.wnd.saveState())
        settings.endGroup()

        settings.beginGroup("options")
        settings.setValue("autoalign_rectangle",
                          Qt.QPoint(self.aap_rectangle[0],
                                    self.aap_rectangle[1]))
        settings.setValue("autodetect_rectangle",
                          int(self.dlg._dialog.autoSizeCheckBox.checkState()))
        settings.setValue("autodetect_quality",
                          int(self.dlg._dialog.minQualitycheckBox.checkState()))
        settings.setValue("max_align_points",
                          int(self.max_points))
        settings.setValue("min_point_quality",
                          float(self.min_quality))
        settings.setValue("use_whole_image",
                          int(self.dlg._dialog.wholeImageCheckBox.checkState()))
        settings.setValue("current_colormap",
                          int(self.current_colormap))
        settings.setValue("toolbar_locked",
                          bool(self.action_lock_toolbars.isChecked()))
        settings.setValue("auto_rgb_fits",
                          int(self.dlg._dialog.rgbFitsCheckBox.checkState()))
        settings.setValue("auto_convert_cr2",
                          int(self.dlg._dialog.decodeCR2CheckBox.checkState()))
        settings.setValue("auto_search_dark_flat",
                          int(self.dlg._dialog.autoFolderscheckBox.checkState()))
        settings.setValue("sharp1",
                          float(self.wnd.sharp1DoubleSpinBox.value()))
        settings.setValue("sharp2",
                          float(self.wnd.sharp2DoubleSpinBox.value()))
        settings.setValue("phase_image",
                          int(self.dlg._dialog.showPhaseImgCheckBox.checkState()))
        settings.setValue("phase_order",
                          int(self.dlg._dialog.phaseIntOrderSlider.value()))
        settings.setValue("interpolation_order",
                          int(self.dlg._dialog.intOrderSlider.value()))
        settings.endGroup()

        settings.beginGroup("settings")
        if self.dlg._dialog.useCustomLangCheckBox.checkState() == 2:
            self.__current_lang = str(self.dlg._dialog.langFileLineEdit.text())
            settings.setValue("custom_language", 2)
        else:
            idx = self.dlg._dialog.langComboBox.currentIndex()
            settings.setValue("custom_language", 0)
            if idx >= 0:
                lang = self.dlg._dialog.langComboBox.itemData(idx)
                if type(lang) == Qt.QVariant:
                    self.__current_lang = str(lang.toString())
                else:
                    self.__current_lang = str(lang)

        settings.setValue("language_file",
                          self.__current_lang)
        settings.setValue("current_align_method",
                          int(self.current_align_method))
        settings.setValue("float_precision",
                          int(self.ftype_idx))
        settings.setValue("use_custom_temp_path",
                          int(self.checked_custom_temp_dir))
        settings.setValue("custom_temp_path",
                          str(self.custom_temp_path))
        settings.setValue("use_zipped_tempfiles",
                          int(self.checked_compressed_temp))
        current_style_item = self.dlg._dialog.themeListWidget.item(
                self.current_style)
        settings.setValue("current_style_name",
                          str(current_style_item.text()))

        settings.endGroup()

    def loadSettings(self):

        settings = Qt.QSettings()

        settings.beginGroup("mainwindow")
        self.wnd.restoreGeometry(
            settings.value("geometry", None, QtCore.QByteArray))
        self.wnd.restoreState(
            settings.value("window_state", None, QtCore.QByteArray))
        settings.endGroup()

        settings.beginGroup("options")
        point = settings.value("autoalign_rectangle", None, Qt.QPoint)
        self.aap_rectangle = (point.x(), point.y())
        self.checked_autodetect_rectangle_size = settings.value(
            "autodetect_rectangle", None, int)
        self.checked_autodetect_min_quality = settings.value(
            "autodetect_quality", None, int)
        self.aap_wholeimage = settings.value(
            "use_whole_image", None, int)
        self.action_lock_toolbars.setChecked(settings.value(
            "toolbar_locked", None, bool))
        self.dlg._dialog.decodeCR2CheckBox.setCheckState(settings.value(
            "auto_convert_cr2", None, int))
        self.dlg._dialog.rgbFitsCheckBox.setCheckState(settings.value(
            "auto_rgb_fits", None, int))
        self.checked_seach_dark_flat = settings.value(
            "auto_search_dark_flat", None, int)
        self.max_points = int(settings.value(
            "max_align_points", None, int))
        self.min_quality = float(settings.value(
            "min_point_quality", None, float))
        self.wnd.sharp1DoubleSpinBox.setValue(float(settings.value(
            "sharp1", None, float)))
        self.wnd.sharp2DoubleSpinBox.setValue(float(settings.value(
            "sharp1", None, float)))
        self.checked_show_phase_img = int(settings.value(
            "phase_image", None, int))
        self.phase_interpolation_order = int(settings.value(
            "phase_order", None, int))
        self.interpolation_order = int(settings.value(
            "interpolation_order", None, int))
        settings.endGroup()

        settings.beginGroup("settings")
        self.__current_lang = str(settings.value(
            "language_file", None, str))
        self.custom_chkstate = int(settings.value(
            "custom_language", None, int))
        self.current_align_method = int(settings.value(
            "current_align_method", None, int))
        self.ftype_idx = int(settings.value(
            "float_precision", None, int))
        self.checked_custom_temp_dir = int(settings.value(
            "use_custom_temp_path", None, int))
        self.custom_temp_path = str(settings.value(
            "custom_temp_path", None, str))
        self.checked_compressed_temp = int(settings.value(
            "use_zipped_tempfiles", None, int))
        current_style_name = str(settings.value(
            "current_style_name", None, str))
        current_style_item = self.dlg._dialog.themeListWidget.findItems(
            current_style_name,
            QtCore.Qt.MatchExactly)[0]
        self.current_style = self.dlg._dialog.themeListWidget.row(
                current_style_item)
        settings.endGroup()

        self.dlg._dialog.wholeImageCheckBox.setCheckState(
            self.aap_wholeimage)

        self.dlg._dialog.minQualitycheckBox.setCheckState(
            self.checked_autodetect_min_quality)

        self.dlg._dialog.autoFolderscheckBox.setCheckState(
            self.checked_seach_dark_flat)

        self.dlg._dialog.themeListWidget.setCurrentRow(
            self.current_style)

        self.wnd.alignMethodComboBox.setCurrentIndex(
            self.current_align_method)

        self.changeAlignMethod(self.current_align_method)

    def deselectAllListWidgetsItems(self):
        self.wnd.lightListWidget.setCurrentItem(None)
        self.wnd.biasListWidget.setCurrentItem(None)
        self.wnd.darkListWidget.setCurrentItem(None)
        self.wnd.flatListWidget.setCurrentItem(None)

    def showResultImage(self, newtab=True):
        if self._stk is not None:
            self.showImage(self._stk,
                           title="stacking result",
                           newtab=newtab)

    def showImage(self, image, title=None, newtab=False,
                  mdisubwindow=None, activate_sw=True,
                  override_cursor=True, context_subtitle=None):

        if override_cursor:
            qapp = QtGui.QApplication.instance()
            qapp.setOverrideCursor(QtCore.Qt.WaitCursor)

        if title is None:
            try:
                title = image.tool_name
            except:
                title = ""

        original_title = title

        if context_subtitle is not None:
            title = "["+str(context_subtitle)+"] "+title

        if mdisubwindow is None:
            sw = None
            for swnd in self.mdi_windows:
                if swnd.windowTitle() == title:
                    sw = swnd
                    break
        else:
            sw = mdisubwindow
            newtab = False

        if ((sw is None) or (not (sw in self.mdi_windows.keys())) or
                (self.mdi_windows[sw]['type'] != guicontrols.IMAGEVIEWER)):
            newtab = True
        else:
            self.mdi_windows[sw]['status'] = guicontrols.UPDATED

        if newtab:
            existing_titles = []
            for swnd in self.mdi_windows:
                existing_titles.append(swnd.windowTitle())
            sw_title = title
            title_idx = 1
            while sw_title in existing_titles:
                sw_title = title+" <"+str(title_idx)+">"
                title_idx += 1
            sw = self.newMdiImageViewer(sw_title)
            self.mdi_windows[sw]['status'] = guicontrols.READY
        elif activate_sw:
            self.mdi.setActiveSubWindow(sw)

        iv = self.mdi_windows[sw]['widget']

        if type(image) == utils.Frame:
            iv.showImage(self.debayerize(image.getData(asarray=True)))
            self.mdi_windows[sw]['references'] = [image, ]
            iv.image_name = image.name
            iv.image_features = image.getAllFeatures()
            iv.image_properties = image.properties
            image.featuresChanged.connect(iv.setFeatures)
        else:
            iv.showImage(image)

        self.mdi_windows[sw]['widget'] = iv
        self.mdi_windows[sw]['context'] = context_subtitle
        self.mdi_windows[sw]['name'] = original_title

        if override_cursor:
            qapp.restoreOverrideCursor()

        return sw

    def showDifference(self, image=None, reference=None,
                       newtab=False, mdisubwindow=None, reload_images=True):

        QtGui.QApplication.instance().setOverrideCursor(QtCore.Qt.WaitCursor)

        if mdisubwindow is None:
            swlist = self.getMdiWindowsByType(guicontrols.DIFFERENCEVIEWER)
            if swlist:
                sw = swlist[0]
            else:
                sw = self.mdi.activeSubWindow()
        else:
            sw = mdisubwindow
            newtab = False
        if sw is None:
            newtab = True
        else:
            sw_type = self.mdi_windows[sw]['type']
            if ((not (sw in self.mdi_windows.keys())) or
                    (sw_type != guicontrols.DIFFERENCEVIEWER)):
                newtab = True

        if (not newtab) and (sw is not None):
            sw.setWindowTitle("manual alignment")
        else:
            sw = self.newMdiDifferenceViewer("manual alignment")

        iv = self.mdi_windows[sw]['widget']

        if (reference is None):
            reference = self.framelist[self.ref_image_idx]
        if (image is None):
            image = self.framelist[self.dif_image_idx]

        if reload_images:
            iv.setRefImage(self.debayerize(reference.getData(asarray=True)))
            iv.showImage(self.debayerize(image.getData(asarray=True)))

        try:
            iv.setOffset(image.offset[0],
                         image.offset[1],
                         image.angle)
            iv.setRefShift(reference.offset[0],
                           reference.offset[1],
                           reference.angle)
        except Exception as exc:
            log.log(repr(self),
                    "Exception: " + str(exc),
                    level=logging.DEBUG)
            pass

        self.mdi_windows[sw]['widget'] = iv
        self.mdi_windows[sw]['references'] = [image, reference]
        self.mdi_windows[sw]['context'] = None
        self.mdi_windows[sw]['name'] = "manual alignment"

        QtGui.QApplication.instance().restoreOverrideCursor()

    #
    # mdi control functions
    #

    def updateMdiControls(self, mdisw):
        if mdisw is None:
            return

        self.__updating_mdi_ctrls = True
        sw_prop = self.mdi_windows[mdisw]
        sw_type = sw_prop['type']

        log.log(repr(self),
                "Updating mdi subwindow "+str(mdisw)+" type="+str(sw_type),
                level=logging.DEBUG)

        if sw_type == guicontrols.IMAGEVIEWER:
            # iv = sw_prop['widget']

            self.deselectAllListWidgetsItems()

            try:
                refimg = sw_prop['references'][0]
                frametype = refimg.getProperty('frametype')

                if frametype == utils.LIGHT_FRAME_TYPE:
                    listwidget = self.wnd.lightListWidget
                elif frametype == utils.BIAS_FRAME_TYPE:
                    listwidget = self.wnd.biasListWidget
                elif frametype == utils.DARK_FRAME_TYPE:
                    listwidget = self.wnd.darkListWidget
                elif frametype == utils.FLAT_FRAME_TYPE:
                    listwidget = self.wnd.flatListWidget

                try:
                    listitem = refimg.getProperty('listItem')
                    listwidget.setCurrentItem(listitem)
                    self.updateImageFeatures(listwidget, listitem)
                except:
                    listwidget.setCurrentItem(None)
                else:
                    if sw_prop['status'] == guicontrols.NEEDS_IMAGE_UPDATE:
                        self.showImage(image=refimg,
                                       title=sw_prop['name'],
                                       mdisubwindow=mdisw,
                                       context_subtitle=sw_prop['context'])
            except:
                pass
        else:
            self.deselectAllListWidgetsItems()

        self.__updating_mdi_ctrls = False

    def newMdiWindow(self, widget=None, wtype='unknown', title=""):
        sw = self.mdi.addSubWindow(widget)
        sw.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        sw.setWindowTitle(str(title))
        self.mdi_windows[sw] = {}
        self.mdi_windows[sw]['references'] = []
        self.mdi_windows[sw]['widget'] = widget
        self.mdi_windows[sw]['type'] = wtype
        return sw

    def getParentMdiWindow(self, widget):
        for sw in self.mdi_windows.keys():
            if self.mdi_windows[sw]['widget'] == widget:
                return widget
        return None

    def getMdiWindowsByType(self, wtype):
        swlist = []
        for sw in self.mdi_windows.keys():
            if self.mdi_windows[sw]['type'] == wtype:
                swlist.append(sw)
        return swlist

    def showInMdiWindow(self, widget, wtype, title=""):
        existing_titles = []
        for swnd in self.mdi_windows:
            existing_titles.append(swnd.windowTitle())
        sw_title = title
        title_idx = 0
        while sw_title in existing_titles:
            title_idx += 1
            sw_title = title+" <"+str(title_idx)+">"
        sw = self.newMdiWindow(widget, wtype, sw_title)
        sw.destroyed.connect(self.clearGenericMdiWindow)
        sw.show()
        return sw

    def closeAllMdiWindows(self, refwidget=None):
        if refwidget is None:
            self.mdi.closeAllSubWindows()
        else:
            for sw in self.mdi_windows.keys():
                if refwidget in self.mdi_windows[sw]['references']:
                    sw.close()

    def newMdiImageViewer(self, title=""):
        iv = guicontrols.ImageViewer(self.statusLabelMousePos)
        sw = self.newMdiWindow(iv, guicontrols.IMAGEVIEWER, title)
        sw.destroyed.connect(self.clearMdiImageViewer)
        sw.show()
        return sw

    def newMdiDifferenceViewer(self, title=""):
        iv = guicontrols.DifferenceViewer()
        sw = self.newMdiWindow(iv, guicontrols.DIFFERENCEVIEWER, title)
        sw.destroyed.connect(self.clearMdiImageViewer)
        sw.show()
        return sw

    def repaintAllMdiImageViewers(self, *arg, **args):
        for mdisw in self.mdi_windows.keys():
            sw_prop = self.mdi_windows[mdisw]
            sw_type = sw_prop['type']
            if sw_type == guicontrols.IMAGEVIEWER:
                log.log(repr(self),
                        ("Repainting mdi subwindow " +
                         str(mdisw) + " type="+str(sw_type)),
                        level=logging.DEBUG)
                iv = self.mdi_windows[mdisw]['widget']
                iv.imageLabel.repaint()

    def clearGenericMdiWindow(self, swnd):
        self.mdi_windows.pop(swnd)

    def clearMdiImageViewer(self, swnd):
        return self.clearGenericMdiWindow(swnd)

    #
    # END MDI CONTROL FUNCTIONS
    #

    def setUpStatusBar(self):
        log.log(repr(self),
                "Setting up statusbar...",
                level=logging.DEBUG)
        self.progress = Qt.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setMaximumSize(400, 25)
        self.cancelProgress = Qt.QPushButton(tr.tr('cancel'))
        self.cancelProgress.clicked.connect(self.canceled)
        self.statusBar.addPermanentWidget(self.statusLabelMousePos)
        self.statusBar.addPermanentWidget(self.cancelProgress)
        self.statusBar.addPermanentWidget(self.progress)
        self.progress.hide()
        self.cancelProgress.hide()
        self.statusBar.showMessage(tr.tr('Welcome!'))

    def buildMenus(self):

        self.mainMenuBar = self.wnd.menuBar()

        if self.mainMenuBar is None:
            log.log(repr(self),
                    "Creating menu bar...",
                    level=logging.DEBUG)
            self.mainMenuBar = Qt.QMenuBar()
            self.wnd.setMenuBar(self.mainMenuBar)

        log.log(repr(self),
                "Setting up menus...",
                level=logging.DEBUG)

        self.action_exit = QtGui.QAction(
            utils.getQIcon("application-exit"),
            tr.tr('exit'), self)
        self.action_exit.triggered.connect(
            self.wnd.close)

        self.action_load_project = QtGui.QAction(
            utils.getQIcon("document-open"),
            tr.tr('Load project'), self)
        self.action_load_project.triggered.connect(
            self.doLoadProject)

        self.action_new_project = QtGui.QAction(
            utils.getQIcon("document-new"),
            tr.tr('New project'), self)
        self.action_new_project.triggered.connect(
            self.doNewProject)

        self.action_save_project = QtGui.QAction(
            utils.getQIcon("document-save"),
            tr.tr('Save project'), self)
        self.action_save_project.triggered.connect(
            self.doSaveProject)

        self.action_save_project_as = QtGui.QAction(
            utils.getQIcon("document-save-as"),
            tr.tr('Save project as'), self)
        self.action_save_project_as.triggered.connect(
            self.doSaveProjectAs)

        self.action_add_files = QtGui.QAction(
            utils.getQIcon("insert-image"),
            tr.tr('Add images/videos'), self)
        self.action_add_files.triggered.connect(
            self.doLoadFiles)

        self.action_lock_toolbars = QtGui.QAction(
            utils.getQIcon(None),
            tr.tr('Lock tool-bars'), self)
        self.action_lock_toolbars.toggled.connect(
            self.setToolBarsLock)
        self.action_lock_toolbars.setCheckable(True)

        self.action_show_preferences = QtGui.QAction(
            utils.getQIcon(),
            tr.tr('Show preferences'), self)
        self.action_show_preferences.triggered.connect(
            self.doSetPreferences)

        self.action_show_about = QtGui.QAction(
            utils.getQIcon("help-about"),
            tr.tr('About lxnstack'), self)
        self.action_show_about.triggered.connect(
            self.doShowAbout)

        self.action_show_manual = QtGui.QAction(
            utils.getQIcon("help-contents"),
            tr.tr('Show User\'s Manual'), self)
        self.action_show_manual.triggered.connect(
            self.doShowUserMan)

        self.action_align = QtGui.QAction(
            utils.getQIcon("align-images"),
            tr.tr('Align images'), self)
        self.action_align.triggered.connect(
            self.doAlign)

        self.action_stack = QtGui.QAction(
            utils.getQIcon("stack-images"),
            tr.tr('Stack images'), self)
        self.action_stack.triggered.connect(
            self.doStack)

        self.action_save_video = QtGui.QAction(
            utils.getQIcon("video-x-generic"),
            tr.tr('Export images sequence as a video'), self)
        self.action_save_video.triggered.connect(
            self.doSaveVideo)

        self.action_gen_lightcurves = QtGui.QAction(
            utils.getQIcon("generate-lightcurves"),
            tr.tr('Generate lightcurves'), self)
        self.action_gen_lightcurves.triggered.connect(
            self.doGenerateLightCurves)

        self.action_enable_rawmode = QtGui.QAction(
            utils.getQIcon("bayer-mode"),
            tr.tr('Enable raw-mode'), self)
        self.action_enable_rawmode.triggered.connect(
            self.updateBayerMatrix)
        self.action_enable_rawmode.setCheckable(True)

        self.action_enable_video = QtGui.QAction(
            utils.getQIcon(""),
            tr.tr('Enable preview'), self)
        self.action_enable_video.setCheckable(True)
        self.action_enable_video.toggled.connect(
            self.enableVideoPreview)
        self.action_enable_video.setEnabled(False)

        self.action_start_capture = QtGui.QAction(
            utils.getQIcon("video-recording-start"),
            tr.tr('Start capturing'), self)
        self.action_start_capture.triggered.connect(
            self.startDirectVideoCapture)
        self.action_start_capture.setEnabled(False)

        self.action_stop_capture = QtGui.QAction(
            utils.getQIcon("video-recording-stop"),
            tr.tr('Stop capturing'), self)
        self.action_stop_capture.triggered.connect(
            self.stopDirectVideoCapture)
        self.action_stop_capture.setEnabled(False)

        self.action_sched_capture = QtGui.QAction(
            utils.getQIcon("video.scheduler"),
            tr.tr('open scheduler'), self)
        self.action_sched_capture.triggered.connect(
            self.videoCaptureScheduler.show)

        self.action_take_shot = QtGui.QAction(
            utils.getQIcon("video-single-shot"),
            tr.tr('Take single shot'), self)
        self.action_take_shot.triggered.connect(
            self.oneShot)

        log.log(repr(self),
                "Bulding menu trees...",
                level=logging.DEBUG)

        menu_files = self.mainMenuBar.addMenu(tr.tr("Files"))
        menu_video = self.mainMenuBar.addMenu(tr.tr("Video capture"))
        menu_stacking = self.mainMenuBar.addMenu(tr.tr("Stacking"))
        menu_lightcurves = self.mainMenuBar.addMenu(tr.tr("Lightcurves"))
        menu_settings = self.mainMenuBar.addMenu(tr.tr("Settings"))
        menu_about = self.mainMenuBar.addMenu("?")

        # Files menu
        menu_files.addAction(self.action_add_files)
        menu_files.addSeparator()
        menu_files.addAction(self.action_new_project)
        menu_files.addAction(self.action_load_project)
        menu_files.addAction(self.action_save_project)
        menu_files.addAction(self.action_save_project_as)
        menu_files.addSeparator()
        menu_files.addAction(self.action_exit)

        # Video menu
        menu_video.addAction(self.action_enable_video)
        menu_video.addAction(self.action_sched_capture)
        menu_video.addAction(self.action_take_shot)
        menu_video.addAction(self.action_start_capture)
        menu_video.addAction(self.action_stop_capture)
        self.capture_devices_menu = menu_video.addMenu("capture devices")
        self.capture_devices_menu.setIcon(utils.getQIcon("camera"))

        # Stacking menu
        menu_stacking.addAction(self.action_align)
        menu_stacking.addAction(self.action_stack)
        menu_stacking.addAction(self.action_save_video)

        # Ligthcurves menu
        menu_lightcurves.addAction(self.action_gen_lightcurves)

        # Settings menu
        menu_settings.addAction(self.action_show_preferences)
        menu_settings.addAction(self.action_lock_toolbars)

        # About menu
        menu_about.addAction(self.action_show_manual)
        menu_about.addSeparator()
        menu_about.addAction(self.action_show_about)

    def _setUpMainToolBar(self):
        maintoolbar = Qt.QToolBar('Main')
        maintoolbar.setObjectName("Main ToolBar")

        # TODO: complete this seciton

        maintoolbar.addAction(self.action_new_project)
        maintoolbar.addAction(self.action_load_project)
        maintoolbar.addAction(self.action_add_files)
        maintoolbar.addAction(self.action_save_project)
        maintoolbar.addAction(self.action_save_project_as)

        return maintoolbar

    def _setUpStackingToolBar(self):
        toolbar = Qt.QToolBar('Stacking')
        toolbar.setObjectName("Stacking ToolBar")

        # TODO: complete this seciton

        toolbar.addAction(self.action_align)
        toolbar.addAction(self.action_stack)

        return toolbar

    def _setUpPhotometryToolBar(self):
        toolbar = Qt.QToolBar('Photometry')
        toolbar.setObjectName("Photometry ToolBar")

        # TODO: complete this seciton

        toolbar.addAction(self.action_gen_lightcurves)

        return toolbar

    def _setUpMiscToolBar(self):
        toolbar = Qt.QToolBar('Misc')
        toolbar.setObjectName("Misc ToolBar")

        self.bayer_tcb = guicontrols.ToolComboBox(
            tr.tr("matrix type:"),
            tooltip=tr.tr("Specify the type of bayer matrix used"))
        self.bayer_tcb.setEnabled(False)
        self.bayer_tcb.currentIndexChanged.connect(
            self.updateBayerMatrix)

        self.bayer_tcb.addItem(utils.getQIcon("bayer-rggb"), "RGGB")
        self.bayer_tcb.addItem(utils.getQIcon("bayer-grgb"), "GRGB")
        self.bayer_tcb.addItem(utils.getQIcon("bayer-gbrg"), "GBRG")
        self.bayer_tcb.addItem(utils.getQIcon("bayer-bggr"), "BGGR")

        toolbar.addAction(self.action_enable_rawmode)
        self.action_bayer = toolbar.addWidget(self.bayer_tcb)

        self.action_bayer.setVisible(self.action_enable_rawmode.isChecked())

        self.action_enable_rawmode.toggled.connect(
            self.action_bayer.setVisible)

        return toolbar

    def _setUpVideoCaptureToolBar(self):
        toolbar = Qt.QToolBar('Video')

        toolbar.setObjectName("VideoCapture ToolBar")

        devices_button = QtGui.QToolButton()
        devices_button.setMenu(self.capture_devices_menu)
        devices_button.setIcon(utils.getQIcon("camera"))
        devices_button.setPopupMode(QtGui.QToolButton.InstantPopup)

        toolbar.addWidget(devices_button)
        toolbar.addAction(self.action_enable_video)
        toolbar.addAction(self.action_start_capture)
        toolbar.addAction(self.action_stop_capture)

        self.direct_capture_type_tcb = guicontrols.ToolComboBox(
            tr.tr("output:"),
            tooltip=tr.tr("Specify how to save the captured images"))

        self.direct_capture_type_tcb.addItem(
            utils.getQIcon("type-video-file"),
            "video file")

        self.direct_capture_type_tcb.addItem(
            utils.getQIcon("type-frame-sequence"),
            "frame sequence")

        self.direct_capture_type_tcb.setEnabled(False)
        toolbar.addWidget(self.direct_capture_type_tcb)

        return toolbar

    def addToolBar(self, toolbar,
                   area=QtCore.Qt.TopToolBarArea,
                   newline=False):
        self.wnd.addToolBar(area, toolbar)
        self.toolbars.append(toolbar)

        if newline:
            self.wnd.insertToolBarBreak(toolbar)

    def setUpToolBars(self):

        log.log(repr(self),
                "Setting up toolbars...",
                level=logging.DEBUG)

        self.toolbars = []

        self.addToolBar(self._setUpMainToolBar())
        self.addToolBar(self._setUpMiscToolBar())
        self.addToolBar(self._setUpStackingToolBar())
        self.addToolBar(self._setUpPhotometryToolBar(), True)
        self.addToolBar(self._setUpVideoCaptureToolBar())

        self.setToolBarsLock(self.action_lock_toolbars.isChecked())

    def setToolBarsLock(self, locked):
        for tb in self.toolbars:
            tb.setFloatable(False)
            tb.setMovable(not locked)

    def lock(self, show_cancel=True):
        QtGui.QApplication.instance().setOverrideCursor(QtCore.Qt.WaitCursor)
        self.statusLabelMousePos.setText('')
        self.progress.show()

        if show_cancel:
            self.cancelProgress.show()
        else:
            self.cancelProgress.hide()

        self.wnd.toolBox.setEnabled(False)
        for tb in self.toolbars:
            tb.setEnabled(False)
        self.wnd.menubar.setEnabled(False)

    def unlock(self):
        self.statusBar.clearMessage()
        self.progress.hide()
        self.cancelProgress.hide()
        self.progress.reset()
        self.wnd.toolBox.setEnabled(True)
        for tb in self.toolbars:
            tb.setEnabled(True)
        self.wnd.menubar.setEnabled(True)
        QtGui.QApplication.instance().restoreOverrideCursor()

    def canceled(self):
        self.wasCanceled = True

    def loadFiles(self, newlist=None):

        oldlist = self.framelist[:]

        if newlist is None:
            open_str = tr.tr("All supported images")
            open_str += self.images_extensions+";;"
            open_str += tr.tr("All files *.* (*.*)")
            newlist = list(Qt.QFileDialog.getOpenFileNames(
                self.wnd,
                tr.tr("Select one or more files"),
                self.current_dir,
                open_str,
                None,
                utils.DIALOG_OPTIONS))

        self.statusBar.showMessage(tr.tr('Loading files, please wait...'))

        if not newlist:
            return

        if self.framelist:
            imw = self.currentWidth
            imh = self.currentHeight
            dep = self.currentDepht
        else:
            ref = utils.Frame(str(newlist[0]), **self.frame_open_args)
            if not ref.is_good:
                msgBox = Qt.QMessageBox(self.wnd)
                msgBox.setText(tr.tr("Cannot open image") +
                               " \""+str(ref.url)+"\"")
                msgBox.setIcon(Qt.QMessageBox.Critical)
                msgBox.exec_()
                return False
            imw = ref.width
            imh = ref.height
            dep = ref.getNumberOfComponents()

            del ref

            self.currentWidth = imw
            self.currentHeight = imh
            self.currentDepht = dep

            if self.dlg._dialog.autoSizeCheckBox.checkState() == 2:
                r_w = int(self.currentWidth/10)
                r_h = int(self.currentHeight/10)
                r_l = max(r_w, r_h)
                self.aap_rectangle = (r_l, r_h)
                self.dlg._dialog.rWSpinBox.setValue(r_l)
                self.dlg._dialog.rHSpinBox.setValue(r_l)

        self.current_dir = os.path.dirname(str(newlist[0]))
        rejected = ''

        self.progress.setMaximum(len(newlist))
        self.lock()
        self.statusBar.showMessage(tr.tr('Analyzing images, please wait...'))
        count = 0
        warnings = False
        listitemslist = []
        for i in newlist:
            count += 1
            if not (i in self.framelist):
                # TODO:fix here: string must be compared to string
                page = 0
                img = utils.Frame(str(i), page, **self.frame_open_args)
                if not img.is_good:
                    msgBox = Qt.QMessageBox(self.wnd)
                    msgBox.setText(tr.tr("Cannot open image") +
                                   " \""+str(i)+"\"")
                    msgBox.setIcon(Qt.QMessageBox.Critical)
                    msgBox.exec_()
                    continue

                while img.is_good:
                    if (imw, imh) != (img.width, img.height):
                        warnings = True
                        rejected += img.url+' --> '
                        rejected += tr.tr('size does not match')+':\n'
                        rejected += tr.tr('current size')+'='
                        rejected += str(self.currentWidth)+'x'
                        rejected += str(self.currentHeight)+' '
                        rejected += tr.tr('image size')+'='
                        rejected += str(img.width)+'x'+str(img.height)+'\n'
                    elif dep != img.getNumberOfComponents():
                        warnings = True
                        rejected += img.url+' --> '
                        rejected += tr.tr('number of channels does not match')
                        rejected += ':\n'+tr.tr('current channels')+'='
                        rejected += str(self.currentDepht)+' '
                        rejected += tr.tr('image channels')+'='
                        rejected += str(img.getNumberOfComponents())+'\n'
                    else:
                        q = Qt.QListWidgetItem(img.tool_name)
                        q.setCheckState(2)
                        q.exif_properties = img.properties
                        q.setToolTip(img.long_tool_name)
                        listitemslist.append(q)
                        img.addProperty('listItem', q)
                        img.addProperty('frametype', utils.LIGHT_FRAME_TYPE)
                        self.framelist.append(img)
                    page += 1
                    img = utils.Frame(str(i), page, **self.frame_open_args)
                    if self.progressWasCanceled():
                        break

            self.progress.setValue(count)
            if self.progressWasCanceled():
                self.framelist = oldlist
                return False
        self.unlock()

        for item in listitemslist:
            self.wnd.lightListWidget.addItem(item)

        newlist = []

        if warnings:
            msgBox = Qt.QMessageBox(self.wnd)

            msgBox.setText(tr.tr("Some images have different size or number " +
                                 "of channels and will been ignored.\n"))

            msgBox.setInformativeText(tr.tr("All images must have the " +
                                            "same size and number of " +
                                            "channels.\n\n") +
                                      tr.tr("Click the \'Show Details' " +
                                            "button for more information.\n"))

            msgBox.setDetailedText(rejected)
            msgBox.setIcon(Qt.QMessageBox.Warning)
            msgBox.exec_()
            del msgBox

        self.wnd.manualAlignGroupBox.setEnabled(True)

        self.darkframelist = []

        if self.checked_seach_dark_flat == 2:
            self.bias_dir = os.path.join(self.current_dir, 'bias')
            self.statusBar.showMessage(
                tr.tr('Searching for bias frames') + ', ' +
                tr.tr('please wait')+'...')
            if not self.addBiasFilesFiles(self.bias_dir, ignoreErrors=True):
                pass

            self.dark_dir = os.path.join(self.current_dir, 'dark')
            self.statusBar.showMessage(
                tr.tr('Searching for dark frames') + ', ' +
                tr.tr('please wait')+'...')
            if not self.addDarkFiles(self.dark_dir, ignoreErrors=True):
                pass

            self.flat_dir = os.path.join(self.current_dir, 'flat')
            self.statusBar.showMessage(
                tr.tr('Searching for flatfiled frames') + ', ' +
                tr.tr('please wait')+'...')
            if not self.addFlatFiles(self.flat_dir, ignoreErrors=True):
                pass

        self.statusBar.showMessage(tr.tr('DONE'))

        if self.framelist:
            self.unlockSidebar()

        self.statusBar.showMessage(tr.tr('Ready'))

    def doAddBiasFiles(self, clicked):
        self.addBiasFiles()

    def doAddDarkFiles(self, clicked):
        self.addDarkFiles()

    def doAddFlatFiles(self, clicked):
        self.addFlatFiles()

    def addBiasFiles(self, directory=None, ignoreErrors=False):
        self.addFrameFiles(utils.BIAS_FRAME_TYPE,
                           self.wnd.biasListWidget,
                           self.biasframelist,
                           self.wnd.biasClearPushButton,
                           directory=directory,
                           ignoreErrors=ignoreErrors)

    def addDarkFiles(self, directory=None, ignoreErrors=False):
        self.addFrameFiles(utils.DARK_FRAME_TYPE,
                           self.wnd.darkListWidget,
                           self.darkframelist,
                           self.wnd.darkClearPushButton,
                           directory=directory,
                           ignoreErrors=ignoreErrors)

    def addFlatFiles(self, directory=None, ignoreErrors=False):
        self.addFrameFiles(utils.FLAT_FRAME_TYPE,
                           self.wnd.flatListWidget,
                           self.flatframelist,
                           self.wnd.flatClearPushButton,
                           directory=directory,
                           ignoreErrors=ignoreErrors)

    def doClearBiasList(self):
        self.doClearFrameList(self.wnd.biasListWidget,
                              self.biasframelist,
                              self.wnd.biasClearPushButton)

    def doClearDarkList(self):
        self.doClearFrameList(self.wnd.darkListWidget,
                              self.darkframelist,
                              self.wnd.darkClearPushButton)

    def doClearFlatList(self):
        self.doClearFrameList(self.wnd.flatListWidget,
                              self.flatframelist,
                              self.wnd.flatClearPushButton)

    def doClearFrameList(self, listwidget, framelist, clearbutton):
        while listwidget.count() > 0:
            q = listwidget.takeItem(0)
            self.closeAllMdiWindows(framelist.pop(listwidget.currentRow()))
            del q
        framelist = []
        listwidget.clear()
        clearbutton.setEnabled(False)

    def addFrameFiles(self, frametype, framelistwidget, framelist, clearbutton,
                      directory=None, ignoreErrors=False):
        if directory is None:
            open_str = tr.tr("All supported images")
            open_str += self.images_extensions+";;"
            open_str += tr.tr("All files *.* (*.*)")
            files = list(Qt.QFileDialog.getOpenFileNames(
                self.wnd,
                tr.tr("Select one or more files"),
                self.current_dir,
                open_str,
                None,
                utils.DIALOG_OPTIONS))

        elif os.path.exists(directory) and os.path.isdir(directory):
            files = []
            lst = os.listdir(directory)
            for x in lst:
                files.append(os.path.join(directory, x))
        else:
            return False

        self.progress.setMaximum(len(files))
        self.lock()
        count = 0
        warnings = False
        rejected = ""

        for fn in files:

            QtGui.QApplication.instance().processEvents()
            self.progress.setValue(count)

            if (os.path.isfile(str(fn))):  # TODO: check for duplicates
                page = 0
                i = utils.Frame(str(fn), page, **self.frame_open_args)
                if not i.is_good:
                    if not ignoreErrors:
                        msgBox = Qt.QMessageBox(self.wnd)
                        msgBox.setText(tr.tr("Cannot open image") +
                                       " \""+str(fn)+"\"")
                        msgBox.setIcon(Qt.QMessageBox.Critical)
                        msgBox.exec_()
                    continue
                while i.is_good:
                    if ((self.currentWidth == i.width) and
                            (self.currentHeight == i.height) and
                            (self.currentDepht == i.getNumberOfComponents())):
                        framelist.append(i)
                        q = Qt.QListWidgetItem(i.tool_name, framelistwidget)
                        q.setToolTip(i.long_tool_name)
                        q.setCheckState(2)
                        i.addProperty('listItem', q)
                        i.addProperty('frametype', str(frametype))
                    else:
                        warnings = True
                        rejected += i.url+"\n"
                        break
                    page += 1
                    i = utils.Frame(str(fn), page, **self.frame_open_args)

            if self.progressWasCanceled():
                return False
            count += 1

        self.unlock()

        if warnings:
            msgBox = Qt.QMessageBox(self.wnd)
            msgBox.setText(tr.tr("Some images have different size or number " +
                                 "of channels and will been ignored.\n"))
            msgBox.setInformativeText(tr.tr("All images must have the " +
                                            "same size and number of " +
                                            "channels.\n\n") +
                                      tr.tr("Click the \'Show Details' " +
                                            "button for more information.\n"))
            msgBox.setDetailedText(rejected)
            msgBox.setIcon(Qt.QMessageBox.Warning)
            msgBox.exec_()
            del msgBox

        if (len(framelist) == 0):
            return False
        else:
            clearbutton.setEnabled(True)
        return True

    def clearLightList(self):
        for frame in self.framelist:
            self.closeAllMdiWindows(frame)

        self.framelist = []
        self.ref_image_idx = -1
        self.dif_image_idx = -1
        self.wnd.lightListWidget.clear()
        self.clearAlignPoinList()
        self.wnd.manualAlignGroupBox.setEnabled(False)
        self.lockSidebar()

    def removeImage(self, clicked):

        self.clearResult()

        q = self.wnd.lightListWidget.takeItem(
            self.wnd.lightListWidget.currentRow())
        self.closeAllMdiWindows(self.framelist.pop(
            self.wnd.lightListWidget.currentRow()))

        del q

        if (len(self.framelist) == 0):
            self.clearLightList()
        elif self.image_idx >= len(self.framelist):
            self.wnd.lightListWidget.setCurrentRow(len(self.framelist)-1)
            self.listItemChanged(self.wnd.lightListWidget.currentRow())

    def checkAllListItems(self):
        self.setAllListItemsCheckState(2)

    def uncheckAllListItems(self):
        self.setAllListItemsCheckState(0)

    def clearDarkList(self):
        self.darkframelist = []
        self.aligned_dark = []

    def clearAlignPoinList(self):
        for frm in self.framelist:
            while frm.alignpoints:      # flush the list and
                frm.removeAlignPoint()  # force the deletion
        self.wnd.alignPointsListWidget.clear()
        self.wnd.removePointPushButton.setEnabled(False)
        self.wnd.alignDeleteAllPushButton.setEnabled(False)

    def clearStarsList(self):
        for frm in self.framelist:
            while frm.stars:      # flush the list and
                frm.removeStar()  # force the deletion
        self.wnd.starsListWidget.clear()
        self.wnd.removeStarPushButton.setEnabled(False)
        self.wnd.starsDeleteAllPushButton.setEnabled(False)
        self.action_gen_lightcurves.setEnabled(False)

    def setAllListItemsCheckState(self, state):
        for i in range(self.wnd.lightListWidget.count()):
            self.wnd.lightListWidget.item(i).setCheckState(state)

    def isBayerUsed(self):
        if ((self.currentDepht == 1) and
                self.action_enable_rawmode.isChecked()):
            # the image is RAW monocromathic with bayer matrix
            return True
        else:
            return False

    def debayerize(self, data):
        if ((data is not None) and
                (len(data.shape) == 2) and
                self.isBayerUsed()):
            # the image has to be debayerized
            log.log(repr(self),
                    "Debayering raw image",
                    level=logging.INFO)
            bayer = self.bayer_tcb.currentIndex()

            correction_factors = [1.0, 1.0, 1.0]

            # NOTE: Cv2 uses BRG images, so we must use
            #       the complementery bayer matrix type.
            #       For example, if you want to convert
            #       a raw image taken with a RGGB matrix,
            #       the BGGR model (BG2RGB) must be used.

            if bayer == 0:
                mode = cv2.cv.CV_BayerBG2RGB
                log.log(repr(self),
                        "using bayer matrix RGGB",
                        level=logging.DEBUG)
            elif bayer == 1:
                mode = cv2.cv.CV_BayerGB2RGB
                log.log(repr(self),
                        "using bayer matrix GRGB",
                        level=logging.DEBUG)
            elif bayer == 2:
                mode = cv2.cv.CV_BayerRG2RGB
                log.log(repr(self),
                        "using bayer matrix BGGR",
                        level=logging.DEBUG)
            else:  # this shuold be only bayer == 3
                log.log(repr(self),
                        "using bayer matrix GBGR",
                        level=logging.DEBUG)
                mode = cv2.cv.CV_BayerGR2RGB

            # TODO: Create a native debayerizing algorithm

            new_data = cv2.cvtColor((data-data.min()).astype(np.uint16), mode)
            new_data = new_data.astype(self.ftype)*correction_factors

            return new_data
        else:
            log.log(repr(self),
                    "Skipping debayerig",
                    level=logging.DEBUG)
            return data

    def updateBayerMatrix(self, *arg):
        # we are forced to ignore *arg because this
        # function is connected  to multiple signals
        if not self.framelist:
            return

        if self.action_enable_rawmode.isChecked():
            self.bayer_tcb.setEnabled(True)
            log.log(repr(self),
                    "RAW-bayer mode ebabled",
                    level=logging.DEBUG)
        else:
            self.bayer_tcb.setEnabled(False)
            log.log(repr(self),
                    "RAW-bayer mode disabled",
                    level=logging.DEBUG)

        log.log(repr(self),
                "Forcing update of displayed images",
                level=logging.DEBUG)
        for sw in self.mdi_windows:
            self.mdi_windows[sw]['status'] = guicontrols.NEEDS_IMAGE_UPDATE

        # update the current mdi subwindow
        curr_mdsw = self.mdi.activeSubWindow()
        if curr_mdsw is not None:
            self.updateMdiControls(curr_mdsw)

    def updateADUlistItemChanged(self, idx):
        if idx < 0:
            self.wnd.pointsADUComboBox.setEnabled(False)
            self.wnd.lineADUComboBox.setEnabled(False)
            self.wnd.barsADUComboBox.setEnabled(False)
            self.wnd.colorADUComboBox.setEnabled(False)
            self.wnd.smoothingADUDoubleSpinBox.setEnabled(False)
            self.wnd.smoothingADUDoubleSpinBox.setEnabled(False)
            self.wnd.pointSizeADUDoubleSpinBox.setEnabled(False)
            self.wnd.lineWidthADUDoubleSpinBox.setEnabled(False)
            return False
        else:
            self.wnd.pointsADUComboBox.setEnabled(True)
            self.wnd.lineADUComboBox.setEnabled(True)
            self.wnd.barsADUComboBox.setEnabled(True)
            self.wnd.colorADUComboBox.setEnabled(True)
            self.wnd.smoothingADUDoubleSpinBox.setEnabled(True)
            self.wnd.pointSizeADUDoubleSpinBox.setEnabled(True)
            self.wnd.lineWidthADUDoubleSpinBox.setEnabled(True)

        q = self.wnd.aduListWidget.item(idx)
        clr_idx = self.getChartColorIndex(q.chart_properties['color'])
        self.wnd.colorADUComboBox.setCurrentIndex(clr_idx)

        pointstype = q.chart_properties['points']
        linetype = q.chart_properties['line']
        barstype = q.chart_properties['bars']
        smoothing = q.chart_properties['smoothing']
        pointsize = q.chart_properties['point_size']
        linewidth = q.chart_properties['line_width']

        try:
            pnt_index = utils.POINTS_TYPE.index(pointstype)
            self.wnd.pointsADUComboBox.setCurrentIndex(pnt_index)
        except:
            self.wnd.pointsADUComboBox.setCurrentIndex(1)

        try:
            ln_index = utils.LINES_TYPE.index(linetype)
            self.wnd.lineADUComboBox.setCurrentIndex(ln_index)
        except:
            self.wnd.lineADUComboBox.setCurrentIndex(0)

        try:
            bar_index = utils.BARS_TYPE.index(barstype)
            self.wnd.barsADUComboBox.setCurrentIndex(bar_index)
        except:
            self.wnd.barsADUComboBox.setCurrentIndex(1)

        self.wnd.smoothingADUDoubleSpinBox.setValue(smoothing)
        self.wnd.pointSizeADUDoubleSpinBox.setValue(pointsize)
        self.wnd.lineWidthADUDoubleSpinBox.setValue(linewidth)

    def updateMaglistItemChanged(self, idx):
        if idx < 0:
            self.wnd.pointsMagComboBox.setEnabled(False)
            self.wnd.lineMagComboBox.setEnabled(False)
            self.wnd.barsMagComboBox.setEnabled(False)
            self.wnd.colorMagComboBox.setEnabled(False)
            self.wnd.smoothingMagDoubleSpinBox.setEnabled(False)
            self.wnd.pointSizeMagDoubleSpinBox.setEnabled(False)
            self.wnd.lineWidthMagDoubleSpinBox.setEnabled(False)
            return False
        else:
            self.wnd.pointsMagComboBox.setEnabled(True)
            self.wnd.lineMagComboBox.setEnabled(True)
            self.wnd.barsMagComboBox.setEnabled(True)
            self.wnd.colorMagComboBox.setEnabled(True)
            self.wnd.smoothingMagDoubleSpinBox.setEnabled(True)
            self.wnd.pointSizeMagDoubleSpinBox.setEnabled(True)
            self.wnd.lineWidthMagDoubleSpinBox.setEnabled(True)

        q = self.wnd.magListWidget.item(idx)
        clr_idx = self.getChartColorIndex(q.chart_properties['color'])
        self.wnd.colorMagComboBox.setCurrentIndex(clr_idx)

        pointstype = q.chart_properties['points']
        linetype = q.chart_properties['line']
        barstype = q.chart_properties['bars']
        smoothing = q.chart_properties['smoothing']
        pointsize = q.chart_properties['point_size']
        linewidth = q.chart_properties['line_width']

        try:
            pnt_index = utils.POINTS_TYPE.index(pointstype)
            self.wnd.pointsMagComboBox.setCurrentIndex(pnt_index)
        except:
            self.wnd.pointsMagComboBox.setCurrentIndex(1)

        try:
            ln_index = utils.LINES_TYPE.index(linetype)
            self.wnd.lineMagComboBox.setCurrentIndex(ln_index)
        except:
            self.wnd.lineMagComboBox.setCurrentIndex(0)

        try:
            bar_index = utils.BARS_TYPE.index(barstype)
            self.wnd.barsMagComboBox.setCurrentIndex(bar_index)
        except:
            self.wnd.barsMagComboBox.setCurrentIndex(1)

        self.wnd.smoothingMagDoubleSpinBox.setValue(smoothing)
        self.wnd.pointSizeMagDoubleSpinBox.setValue(pointsize)
        self.wnd.lineWidthMagDoubleSpinBox.setValue(linewidth)

    def showFrameItemInNewTab(self, item, *arg):
        return self.showItemInMdiTab(item, self.framelist,
                                     self.wnd.lightListWidget,
                                     True, 'light')

    def showDarkFrameItemInNewTab(self, item, *arg):
        return self.showItemInMdiTab(item, self.darkframelist,
                                     self.wnd.darkListWidget,
                                     True, 'dark')

    def showFlatFrameItemInNewTab(self, item, *arg):
        return self.showItemInMdiTab(item, self.flatframelist,
                                     self.wnd.flatListWidget,
                                     True, 'flat')

    def showBiasFrameItemInNewTab(self, item, *arg):
        return self.showItemInMdiTab(item, self.biasframelist,
                                     self.wnd.biasListWidget,
                                     True, 'bias')

    def showFrameItemInCurrentTab(self, item, *arg):
        return self.showItemInMdiTab(item, self.framelist,
                                     self.wnd.lightListWidget,
                                     False, 'light')

    def showDarkFrameItemInCurrentTab(self, item, *arg):
        return self.showItemInMdiTab(item, self.darkframelist,
                                     self.wnd.darkListWidget,
                                     False, 'dark')

    def showFlatFrameItemInCurrentTab(self, item, *arg):
        return self.showItemInMdiTab(item, self.flatframelist,
                                     self.wnd.flatListWidget,
                                     False, 'flat')

    def showBiasFrameItemInCurrentTab(self, item, *arg):
        return self.showItemInMdiTab(item, self.biasframelist,
                                     self.wnd.biasListWidget,
                                     False, 'bias')

    def showItemInMdiTab(self, item,
                         framelist, listwidget,
                         innewtab, context_label=None):
        if not self.__updating_mdi_ctrls:
            row = listwidget.row(item)
            if (row >= 0) and (len(framelist) > 0):
                mdisw = self.showImage(framelist[row],
                                       newtab=innewtab,
                                       context_subtitle=context_label)
                self.updateMdiControls(mdisw)

    def listItemChanged(self, idx):
        if self.__video_capture_started:
            return

        self.image_idx = self.wnd.lightListWidget.currentRow()

        if idx >= 0:
            self.wnd.alignGroupBox.setEnabled(True)
            self.wnd.starsGroupBox.setEnabled(True)
        else:
            self.wnd.alignGroupBox.setEnabled(False)
            self.wnd.starsGroupBox.setEnabled(False)

    def manualAlignListItemChanged(self, idx):
        self.star_idx = idx
        item = self.wnd.listWidgetManualAlign.item(idx)
        if item is None:
            return
        self.dif_image_idx = item.original_id
        img = self.framelist[item.original_id]
        QtGui.QApplication.instance().setOverrideCursor(QtCore.Qt.WaitCursor)

        self.showDifference()

        self.wnd.doubleSpinBoxOffsetX.setValue(img.offset[0])
        self.wnd.doubleSpinBoxOffsetY.setValue(img.offset[1])
        self.wnd.spinBoxOffsetT.setValue(img.angle)

        QtGui.QApplication.instance().restoreOverrideCursor()

    def currentManualAlignListItemChanged(self, cur_item):
        if cur_item is None:
            return False
        elif cur_item.checkState() == 2:
            if not self.__operating:
                self.__operating = True
                self.ref_image_idx = cur_item.original_id
                for i in range(self.wnd.listWidgetManualAlign.count()):
                    item = self.wnd.listWidgetManualAlign.item(i)
                    if (item != cur_item) and (item.checkState() == 2):
                        item.setCheckState(0)
                self.__operating = False
        elif cur_item.checkState() == 0:
            if not self.__operating:
                cur_item.setCheckState(2)

        if not self.__operating:
            self.showDifference()

    def updateAlignList(self):
        if self.ref_image_idx == -1:
            self.ref_image_idx = 0
        self.wnd.listWidgetManualAlign.clear()
        count = 0
        self.__operating = True
        for i in range(self.wnd.lightListWidget.count()):
            if self.wnd.lightListWidget.item(i).checkState() == 2:
                item = self.wnd.lightListWidget.item(i)
                if item.checkState() == 2:
                    q = Qt.QListWidgetItem(item.text(),
                                           self.wnd.listWidgetManualAlign)
                    q.original_id = i
                    if i == self.ref_image_idx:
                        q.setCheckState(2)
                    else:
                        q.setCheckState(0)
                    count += 1
        self.__operating = False

    def alignListItemChanged(self, idx):
        self.point_idx = idx
        if self._updating_feature:
            return
        self._updating_feature = True
        if idx >= 0:
            pnt = self.framelist[self.image_idx].alignpoints[idx]
            self.wnd.spinBoxXAlign.setEnabled(True)
            self.wnd.spinBoxYAlign.setEnabled(True)
            self.wnd.removePointPushButton.setEnabled(True)
            self.wnd.spinBoxXAlign.setValue(pnt.x)
            self.wnd.spinBoxYAlign.setValue(pnt.y)
        else:
            self.wnd.spinBoxXAlign.setEnabled(False)
            self.wnd.spinBoxYAlign.setEnabled(False)
            self.wnd.removePointPushButton.setEnabled(False)
            self.wnd.spinBoxXAlign.setValue(0)
            self.wnd.spinBoxYAlign.setValue(0)
        QtGui.QApplication.instance().processEvents()
        self._updating_feature = False

    def updateCurrentAlignPoint(self, pid, pname):
        pnt_lw = self.wnd.alignPointsListWidget
        pntitem = pnt_lw.findItems(pname, QtCore.Qt.MatchExactly)[0]
        self.wnd.alignPointsListWidget.setCurrentItem(pntitem)

    def updateAlignPointPosition(self, x, y, pid, pname):
        pnt_lw = self.wnd.alignPointsListWidget
        pntitem = pnt_lw.findItems(pname, QtCore.Qt.MatchExactly)[0]
        self.wnd.alignPointsListWidget.setCurrentItem(pntitem)
        self._updating_feature = True
        self.wnd.spinBoxXAlign.setValue(x)
        self.wnd.spinBoxYAlign.setValue(y)
        self._updating_feature = False

    def updateStarPosition(self, x, y, pid, pname):
        str_lw = self.wnd.starsListWidget
        stritem = str_lw.findItems(pname, QtCore.Qt.MatchExactly)[0]
        self.wnd.starsListWidget.setCurrentItem(stritem)
        self._updating_feature = True
        self.wnd.spinBoxXStar.setValue(x)
        self.wnd.spinBoxYStar.setValue(y)
        cfrm = self.framelist[self.image_idx]
        for frm in self.framelist:
            if frm is not cfrm:
                st = frm.stars[self.star_idx]
                st.setPosition(x, y)
        self._updating_feature = False

    def starsListItemChanged(self, q):
        if self._updating_feature:
            return
        star_idx = self.wnd.starsListWidget.row(q)
        cfrm = self.framelist[self.image_idx]
        pnt = cfrm.stars[star_idx]
        pnt.rename(str(q.text()))
        if q.checkState() == 0:
            pnt.reference = False
            self.wnd.magDoubleSpinBox.setEnabled(False)
        else:
            pnt.reference = True
            self.wnd.magDoubleSpinBox.setEnabled(True)

        for frm in self.framelist:
            if frm is not cfrm:
                st = frm.stars[star_idx]
                if st is not pnt:
                    st.reference = pnt.reference
                    st.rename(str(q.text()))
        self.wnd.starsListWidget.setCurrentRow(star_idx)

    def currentStarsListItemChanged(self, idx):
        self.star_idx = idx
        if self._updating_feature:
            return
        self._updating_feature = True
        if idx >= 0:
            pnt = self.framelist[self.image_idx].stars[idx]

            self.wnd.spinBoxXStar.setValue(pnt.x)
            self.wnd.spinBoxYStar.setValue(pnt.y)
            self.wnd.innerRadiusDoubleSpinBox.setValue(pnt.r1)
            self.wnd.middleRadiusDoubleSpinBox.setValue(pnt.r2)
            self.wnd.outerRadiusDoubleSpinBox.setValue(pnt.r3)
            self.wnd.magDoubleSpinBox.setValue(pnt.magnitude)

            if pnt.reference:
                self.wnd.magDoubleSpinBox.setEnabled(True)
            else:
                self.wnd.magDoubleSpinBox.setEnabled(False)

            self.wnd.spinBoxXStar.setEnabled(True)
            self.wnd.spinBoxYStar.setEnabled(True)
            self.wnd.innerRadiusDoubleSpinBox.setEnabled(True)
            self.wnd.middleRadiusDoubleSpinBox.setEnabled(True)
            self.wnd.outerRadiusDoubleSpinBox.setEnabled(True)
            self.wnd.removeStarPushButton.setEnabled(True)
        else:
            self.wnd.spinBoxXStar.setValue(0)
            self.wnd.spinBoxYStar.setValue(0)
            self.wnd.innerRadiusDoubleSpinBox.setValue(0)
            self.wnd.middleRadiusDoubleSpinBox.setValue(0)
            self.wnd.outerRadiusDoubleSpinBox.setValue(0)
            self.wnd.magDoubleSpinBox.setValue(0)

            self.wnd.spinBoxXStar.setEnabled(False)
            self.wnd.spinBoxYStar.setEnabled(False)
            self.wnd.innerRadiusDoubleSpinBox.setEnabled(False)
            self.wnd.middleRadiusDoubleSpinBox.setEnabled(False)
            self.wnd.outerRadiusDoubleSpinBox.setEnabled(False)
            self.wnd.removeStarPushButton.setEnabled(False)
            self.wnd.magDoubleSpinBox.setEnabled(False)
        QtGui.QApplication.instance().processEvents()
        self._updating_feature = False

    def addFeature(self, ftype, fstr, listwidget, updateFunc):
        if not self.framelist:
            return False

        if issubclass(ftype, imgfeatures.Star):
            refftrlist = self.framelist[0].stars
        elif issubclass(ftype, imgfeatures.AlignmentPoint):
            refftrlist = self.framelist[0].alignpoints

        idx = 1
        for i in range(listwidget.count()):
            pname = fstr.format(i+1)
            if refftrlist[i].name != pname:
                idx = i + 1
                break
            else:
                idx = i + 2

        pname = fstr.format(idx)

        for frm in self.framelist:
            ftr = ftype(0, 0, pname)
            if issubclass(ftype, imgfeatures.Star):
                ftr.moved_rt.connect(updateFunc)
                frm.addStar(ftr, idx-1)
            elif isinstance(ftr, imgfeatures.AlignmentPoint):
                ftr.moved.connect(updateFunc)
                frm.addAlignPoint(ftr, idx-1)

        q = Qt.QListWidgetItem(pname)
        tooltip_text = tr.tr('star')+' '+pname
        q.setToolTip(tooltip_text)
        listwidget.insertItem(idx-1, q)

        if issubclass(ftype, imgfeatures.Star):
            q.setFlags(q.flags() | QtCore.Qt.ItemIsEditable)
            q.setCheckState(0)

        listwidget.setCurrentRow(idx-1)
        return idx - 1

    def addAlignPoint(self):
        if self.dlg._dialog.autoSizeCheckBox.checkState() == 2:
            r_w = int(self.currentWidth/10)
            r_h = int(self.currentHeight/10)
            r_l = max(r_w, r_h)
            self.aap_rectangle = (r_l, r_h)
            self.dlg._dialog.rWSpinBox.setValue(r_l)
            self.dlg._dialog.rHSpinBox.setValue(r_l)

        idx = self.addFeature(imgfeatures.AlignmentPoint,
                              'ap#{0:05d}',
                              self.wnd.alignPointsListWidget,
                              self.updateAlignPointPosition)
        self.wnd.removePointPushButton.setEnabled(True)
        self.wnd.alignDeleteAllPushButton.setEnabled(True)
        return idx

    def addStar(self):
        idx = self.addFeature(imgfeatures.Star,
                              'st#{0:05d}',
                              self.wnd.starsListWidget,
                              self.updateStarPosition)
        self.action_gen_lightcurves.setEnabled(True)
        self.wnd.removeStarPushButton.setEnabled(True)
        self.wnd.starsDeleteAllPushButton.setEnabled(True)
        self.action_gen_lightcurves.setEnabled(True)
        return idx

    def removeAlignPoint(self):
        for frm in self.framelist:
            frm.removeAlignPoint(self.point_idx)

        self.updateAlignPointList(self.image_idx)

        if not self.framelist[self.image_idx].alignpoints:
            self.wnd.removePointPushButton.setEnabled(False)
            self.wnd.alignDeleteAllPushButton.setEnabled(False)

    def removeStar(self):
        for frm in self.framelist:
            frm.removeStar(self.star_idx)
        self._updating_feature = True
        self.updateStarList(self.image_idx)
        if not self.framelist[self.image_idx].stars:
            self.wnd.removeStarPushButton.setEnabled(False)
            self.action_gen_lightcurves.setEnabled(False)
            self.wnd.starsDeleteAllPushButton.setEnabled(False)
        self._updating_feature = False

    def updateImageFeatures(self, listwidget, listitem):
        log.log(repr(self),
                "Updating image features...",
                level=logging.DEBUG)
        if listwidget is self.wnd.lightListWidget:
            image_idx = self.wnd.lightListWidget.row(listitem)
            self._updating_feature = True
            self.updateAlignPointList(image_idx)
            self.updateStarList(image_idx)
            self._updating_feature = False

    def updateAlignPointList(self, image_idx):
        log.log(repr(self),
                "Updating alignment points list...",
                level=logging.DEBUG)
        self.wnd.alignPointsListWidget.clear()

        if image_idx < 0:
            # no item selected!
            return

        frm = self.framelist[image_idx]
        imagename = self.wnd.lightListWidget.item(image_idx).text()
        for pnt in frm.alignpoints:
            q = Qt.QListWidgetItem(pnt.name, self.wnd.alignPointsListWidget)
            tooltip_text = tr.tr('image')+' '+imagename+" \n"
            tooltip_text += tr.tr('alignment-point')+' '+pnt.name
            q.setToolTip(tooltip_text)

    def updateStarList(self, image_idx):
        log.log(repr(self),
                "Updating stars list...",
                level=logging.DEBUG)

        original_star_idx = self.wnd.starsListWidget.currentRow()
        self.wnd.starsListWidget.clear()

        if image_idx < 0:
            # no item selected!
            return

        frm = self.framelist[image_idx]
        imagename = self.wnd.lightListWidget.item(image_idx).text()
        for star in frm.stars:
            q = Qt.QListWidgetItem(star.name, self.wnd.starsListWidget)
            tooltip_text = tr.tr('image')+' '+imagename+" \n"
            tooltip_text += tr.tr('star')+' '+star.name
            q.setToolTip(tooltip_text)
            q.setCheckState(2*int(star.reference))
            q.setFlags(q.flags() | QtCore.Qt.ItemIsEditable)
        self.wnd.starsListWidget.setCurrentRow(original_star_idx)

    def shiftX(self, val):
        if self.point_idx >= 0 and not self._updating_feature:
            pnt = self.framelist[self.image_idx].alignpoints[self.point_idx]
            pnt.x = val
            pnt.aligned = False

    def shiftY(self, val):
        if self.point_idx >= 0 and not self._updating_feature:
            pnt = self.framelist[self.image_idx].alignpoints[self.point_idx]
            pnt.y = val
            pnt.aligned = False

    def shiftStarX(self, val):
        if self.star_idx >= 0 and not self._updating_feature:
            cfrm = self.framelist[self.image_idx]
            pnt = cfrm.stars[self.star_idx]
            pnt.setAbsolutePosition(val, pnt.y)
            x, y = pnt.getRTPosition()
            if pnt.isFixed():
                for frm in self.framelist:
                    st = frm.stars[self.star_idx]
                    if st is not pnt:
                        st.setPosition(x, y)
            self.repaintAllMdiImageViewers()

    def shiftStarY(self, val):
        if self.star_idx >= 0 and not self._updating_feature:
            cfrm = self.framelist[self.image_idx]
            pnt = cfrm.stars[self.star_idx]
            pnt.setAbsolutePosition(pnt.x, val)
            x, y = pnt.getRTPosition()
            if pnt.isFixed():
                for frm in self.framelist:
                    st = frm.stars[self.star_idx]
                    if st is not pnt:
                        st.setPosition(x, y)
            self.repaintAllMdiImageViewers()

    def setStarName(self, name):
        if self.star_idx >= 0 and not self._updating_feature:
            cfrm = self.framelist[self.image_idx]
            pnt = cfrm.stars[self.star_idx]
            if pnt.isFixed():
                for frm in self.framelist:
                    frm.stars[self.star_idx].name = name
            self.repaintAllMdiImageViewers()

    def setInnerRadius(self, val):
        if self.star_idx >= 0 and not self._updating_feature:
            cfrm = self.framelist[self.image_idx]
            pnt = cfrm.stars[self.star_idx]
            if pnt.isFixed():
                for frm in self.framelist:
                    frm.stars[self.star_idx].r1 = val
            if pnt.r2-pnt.r1 < 2:
                self.wnd.middleRadiusDoubleSpinBox.setValue(pnt.r1+2)
            self.repaintAllMdiImageViewers()

    def setMiddleRadius(self, val):
        if self.star_idx >= 0 and not self._updating_feature:
            cfrm = self.framelist[self.image_idx]
            pnt = cfrm.stars[self.star_idx]
            if pnt.isFixed():
                for frm in self.framelist:
                    frm.stars[self.star_idx].r2 = val
            if pnt.r2-pnt.r1 < 2:
                self.wnd.innerRadiusDoubleSpinBox.setValue(pnt.r2-2)
            if pnt.r3-pnt.r2 < 2:
                self.wnd.outerRadiusDoubleSpinBox.setValue(pnt.r2+2)
            self.repaintAllMdiImageViewers()

    def setOuterRadius(self, val):
        if self.star_idx >= 0 and not self._updating_feature:
            cfrm = self.framelist[self.image_idx]
            pnt = cfrm.stars[self.star_idx]
            if pnt.isFixed():
                for frm in self.framelist:
                    frm.stars[self.star_idx].r3 = val
            if pnt.r3-pnt.r2 < 2:
                self.wnd.middleRadiusDoubleSpinBox.setValue(pnt.r3-2)
            self.repaintAllMdiImageViewers()

    def setMagnitude(self, val):
        if self.star_idx >= 0 and not self._updating_feature:
            cfrm = self.framelist[self.image_idx]
            pnt = cfrm.stars[self.star_idx]
            pnt.magnitude = val
            if pnt.isFixed():
                for frm in self.framelist:
                    frm.stars[self.star_idx].magnitude = val
            self.repaintAllMdiImageViewers()

    def shiftOffsetX(self, val):
        if self.dif_image_idx >= 0:
            img = self.framelist[self.dif_image_idx]
            img.offset[0] = val
            self.showDifference(reload_images=False)

    def shiftOffsetY(self, val):
        if self.dif_image_idx >= 0:
            img = self.framelist[self.dif_image_idx]
            img.offset[1] = val
            self.showDifference(reload_images=False)

    def rotateOffsetT(self, val):
        if self.dif_image_idx >= 0:
            img = self.framelist[self.dif_image_idx]
            img.angle = val
            self.showDifference(reload_images=False)

    def updateToolBox(self, idx):
        self.ref_image_idx = -1
        QtGui.QApplication.instance().setOverrideCursor(QtCore.Qt.WaitCursor)

        if idx == 2:
            log.log(repr(self),
                    "Setting up manual alignment controls",
                    level=logging.DEBUG)
            self.manual_align = True

            log.log(repr(self),
                    "Updating list of available images",
                    level=logging.DEBUG)
            self.updateAlignList()

            if self.wnd.listWidgetManualAlign.count() > 0:
                log.log(repr(self),
                        "Selecting reference image",
                        level=logging.DEBUG)
                self.wnd.listWidgetManualAlign.setCurrentRow(0)
                self.showDifference()

        self._old_tab_idx = idx
        QtGui.QApplication.instance().restoreOverrideCursor()

    def newProject(self):
        self.closeAllMdiWindows()

        self.wnd.toolBox.setCurrentIndex(0)
        self.action_enable_video.setChecked(False)
        self.bayer_tcb.setCurrentIndex(0)

        self.wnd.setWindowTitle(str(paths.PROGRAM_NAME)+' [Untitled Project]')

        self.zoom = 1
        self.min_zoom = 0
        self.actual_zoom = 1
        self.exposure = 0

        self.image_idx = -1
        self.ref_image_idx = -1
        self.dif_image_idx = -1
        self.point_idx = -1
        self.star_idx = -1

        self.clearResult()

        self.manual_align = False

        self.currentWidth = 0
        self.currentHeight = 0
        self.currentDepht = 0

        self.result_w = 0
        self.result_h = 0
        self.result_d = 3

        self.current_project_fname = None

        del self.framelist
        del self.biasframelist
        del self.darkframelist
        del self.flatframelist

        del self.master_bias_file
        del self.master_dark_file
        del self.master_flat_file

        self.master_bias_file = None
        self.master_dark_file = None
        self.master_flat_file = None

        self.framelist = []
        self.biasframelist = []
        self.darkframelist = []
        self.flatframelist = []

        self.lockSidebar()

        self.action_align.setEnabled(False)
        self.action_stack.setEnabled(False)
        self.wnd.alignGroupBox.setEnabled(False)
        self.wnd.manualAlignGroupBox.setEnabled(False)
        self.wnd.masterBiasGroupBox.setEnabled(False)
        self.wnd.masterDarkGroupBox.setEnabled(False)
        self.wnd.masterFlatGroupBox.setEnabled(False)
        self.wnd.biasFramesGroupBox.setEnabled(True)
        self.wnd.darkFramesGroupBox.setEnabled(True)
        self.wnd.flatFramesGroupBox.setEnabled(True)
        self.wnd.masterDarkGroupBox.hide()
        self.wnd.masterFlatGroupBox.hide()
        self.wnd.masterBiasGroupBox.hide()
        self.wnd.flatFramesGroupBox.show()
        self.wnd.darkFramesGroupBox.show()
        self.wnd.biasFramesGroupBox.show()
        self.wnd.masterBiasCheckBox.setCheckState(0)
        self.wnd.masterDarkCheckBox.setCheckState(0)
        self.wnd.masterFlatCheckBox.setCheckState(0)
        self.wnd.biasMulDoubleSpinBox.setValue(1.0)
        self.wnd.darkMulDoubleSpinBox.setValue(1.0)
        self.wnd.flatMulDoubleSpinBox.setValue(1.0)
        self.wnd.alignPointsListWidget.clear()
        self.wnd.lightListWidget.clear()
        self.wnd.biasListWidget.clear()
        self.wnd.darkListWidget.clear()
        self.wnd.flatListWidget.clear()
        self.wnd.starsListWidget.clear()
        self.wnd.masterBiasLineEdit.setText('')
        self.wnd.masterDarkLineEdit.setText('')
        self.wnd.masterFlatLineEdit.setText('')
        self.progress.reset()

    def saveProjectAs(self):
        self.current_project_fname = str(Qt.QFileDialog.getSaveFileName(
            self.wnd,
            tr.tr("Save the project"),
            os.path.join(self.current_dir, 'Untitled.lxn'),
            "Project (*.lxn);;All files (*.*)",
            None,
            utils.DIALOG_OPTIONS))

        if not self.current_project_fname.strip():
            self.current_project_fname = None
            return
        self._save_project()

    def saveProject(self):
        if self.current_project_fname is None:
            self.saveProjectAs()
        else:
            self._save_project()

    def corruptedMsgBox(self, info=""):
        utils.showErrorMsgBox(tr.tr("The project is invalid or corrupted!"),
                              info,
                              parent=self.wnd,
                              caller=self)
        return False

    def _save_project(self):
        self.lock(False)
        self.progress.reset()
        log.log(repr(self),
                "Saving project to " + str(self.current_project_fname),
                level=logging.INFO)
        self.statusBar.showMessage(tr.tr('saving project') + ', ' +
                                   tr.tr('please wait...'))

        if self.action_enable_rawmode.isChecked():
            bayer_mode = self.bayer_tcb.currentIndex()
        else:
            bayer_mode = -1

        doc = minidom.Document()

        root = doc.createElement('project')
        doc.appendChild(root)

        information_node = doc.createElement('information')
        bias_frames_node = doc.createElement('bias-frames')
        dark_frames_node = doc.createElement('dark-frames')
        flat_frames_node = doc.createElement('flat-frames')
        pict_frames_node = doc.createElement('frames')
        photometry_node = doc.createElement('photometry')

        root.appendChild(information_node)
        root.appendChild(bias_frames_node)
        root.appendChild(dark_frames_node)
        root.appendChild(flat_frames_node)
        root.appendChild(pict_frames_node)
        root.appendChild(photometry_node)

        # <information> section
        information_node.setAttribute('width', str(int(self.currentWidth)))
        information_node.setAttribute('height', str(int(self.currentHeight)))
        information_node.setAttribute('mode', str(int(self.currentDepht)))
        information_node.setAttribute('bayer-mode', str(int(bayer_mode)))

        current_dir_node = doc.createElement('current-dir')
        current_row_node = doc.createElement('current-row')
        master_bias_node = doc.createElement('master-bias')
        master_dark_node = doc.createElement('master-dark')
        master_flat_node = doc.createElement('master-flat')
        min_quality_node = doc.createElement('min-point-quality')
        max_points_node = doc.createElement('max-align-points')
        align_rect_node = doc.createElement('align-rect')

        information_node.appendChild(current_dir_node)
        information_node.appendChild(current_row_node)
        information_node.appendChild(master_bias_node)
        information_node.appendChild(master_dark_node)
        information_node.appendChild(master_flat_node)
        information_node.appendChild(align_rect_node)
        information_node.appendChild(max_points_node)
        information_node.appendChild(min_quality_node)

        mb_cck_state = self.wnd.masterBiasCheckBox.checkState()
        md_cck_state = self.wnd.masterDarkCheckBox.checkState()
        mf_cck_state = self.wnd.masterFlatCheckBox.checkState()

        current_dir_node.setAttribute('url', str(self.current_dir))
        current_row_node.setAttribute('index', str(self.image_idx))
        master_bias_node.setAttribute('checked', str(mb_cck_state))
        master_bias_node.setAttribute('mul', str(self.master_bias_mul_factor))
        master_dark_node.setAttribute('checked', str(md_cck_state))
        master_dark_node.setAttribute('mul', str(self.master_dark_mul_factor))
        master_flat_node.setAttribute('checked', str(mf_cck_state))
        master_flat_node.setAttribute('mul', str(self.master_flat_mul_factor))
        align_rect_node.setAttribute('width', str(self.aap_rectangle[0]))
        align_rect_node.setAttribute('height', str(self.aap_rectangle[1]))
        align_rect_node.setAttribute('whole-image', str(self.aap_wholeimage))
        max_points_node.setAttribute('value', str(self.max_points))
        min_quality_node.setAttribute('value', str(self.min_quality))

        url = doc.createElement('url')
        url_txt = doc.createTextNode(str(self.wnd.masterBiasLineEdit.text()))
        url.appendChild(url_txt)
        master_bias_node.appendChild(url)

        url = doc.createElement('url')
        url_txt = doc.createTextNode(str(self.wnd.masterDarkLineEdit.text()))
        url.appendChild(url_txt)
        master_dark_node.appendChild(url)

        url = doc.createElement('url')
        url_txt = doc.createTextNode(str(self.wnd.masterFlatLineEdit.text()))
        url.appendChild(url_txt)
        master_flat_node.appendChild(url)

        total_bias = len(self.biasframelist)
        total_dark = len(self.darkframelist)
        total_flat = len(self.flatframelist)
        total_imgs = len(self.framelist)

        progress_max = total_bias
        progress_max += total_dark
        progress_max += total_flat
        progress_max += total_imgs
        self.progress.setMaximum(progress_max)

        count = 0

        # <bias-frams> section
        for i in self.biasframelist:
            self.progress.setValue(count)
            count += 1

            im_bias_used = str(i.isUsed())
            im_bias_name = str(i.tool_name)
            im_bias_page = i.page
            im_bias_url = i.url

            image_node = doc.createElement('image')
            image_node.setAttribute('name', im_bias_name)
            image_node.setAttribute('used', im_bias_used)
            bias_frames_node.appendChild(image_node)

            url = doc.createElement('url')
            url_txt = doc.createTextNode(im_bias_url)
            url.appendChild(url_txt)
            url.setAttribute('page', str(im_bias_page))
            image_node.appendChild(url)

        # <dark-frams> section
        for i in self.darkframelist:
            self.progress.setValue(count)
            count += 1

            im_dark_used = str(i.isUsed())
            im_dark_name = str(i.tool_name)
            im_dark_page = i.page
            im_dark_url = i.url
            image_node = doc.createElement('image')
            image_node.setAttribute('name', im_dark_name)
            image_node.setAttribute('used', im_dark_used)
            dark_frames_node.appendChild(image_node)

            url = doc.createElement('url')
            url_txt = doc.createTextNode(im_dark_url)
            url.appendChild(url_txt)
            url.setAttribute('page', str(im_dark_page))
            image_node.appendChild(url)

        # <flat-frames> section
        for i in self.flatframelist:
            self.progress.setValue(count)
            count += 1

            im_flat_used = str(i.isUsed())
            im_flat_name = str(i.tool_name)
            im_flat_page = i.page
            im_flat_url = i.url
            image_node = doc.createElement('image')
            image_node.setAttribute('name', im_flat_name)
            image_node.setAttribute('used', im_flat_used)
            flat_frames_node.appendChild(image_node)

            url = doc.createElement('url')
            url_txt = doc.createTextNode(im_flat_url)
            url.appendChild(url_txt)
            url.setAttribute('page', str(im_flat_page))
            image_node.appendChild(url)

        # <frames> section
        for img in self.framelist:
            self.progress.setValue(count)
            count += 1

            im_used = str(img.isUsed())
            im_name = str(img.tool_name)
            im_page = img.page
            im_url = img.url
            image_node = doc.createElement('image')
            image_node.setAttribute('name', im_name)
            image_node.setAttribute('used', im_used)

            pict_frames_node.appendChild(image_node)

            for point in img.alignpoints:
                point_node = doc.createElement('align-point')
                point_node.setAttribute('x', str(int(point.x)))
                point_node.setAttribute('y', str(int(point.y)))
                point_node.setAttribute('id', str(point.id))
                point_node.setAttribute('name', str(point.name))
                point_node.setAttribute('aligned', str(point.aligned))
                image_node.appendChild(point_node)

            for s in img.stars:
                star_node = doc.createElement('star')
                star_node.setAttribute('x', str(int(s.x)))
                star_node.setAttribute('y', str(int(s.y)))
                star_node.setAttribute('name', str(s.name))
                star_node.setAttribute('id', str(s.id))
                star_node.setAttribute('inner_radius', str(float(s.r1)))
                star_node.setAttribute('middle_radius', str(float(s.r2)))
                star_node.setAttribute('outer_radius', str(float(s.r3)))
                star_node.setAttribute('reference', str(int(s.reference)))
                star_node.setAttribute('magnitude', str(float(s.magnitude)))
                image_node.appendChild(star_node)

            offset_node = doc.createElement('offset')
            offset_node.setAttribute('x', str(float(img.offset[0])))
            offset_node.setAttribute('y', str(float(img.offset[1])))
            offset_node.setAttribute('theta', str(float(img.angle)))
            image_node.appendChild(offset_node)

            url = doc.createElement('url')
            url_txt = doc.createTextNode(im_url)
            url.appendChild(url_txt)
            url.setAttribute('page', str(im_page))
            image_node.appendChild(url)

        # photometry section
        img_tm = int(self.use_image_time)
        photometry_node.setAttribute('time_type', str(img_tm))

        try:
            f = open(self.current_project_fname, 'w')
            f.write(doc.toprettyxml(' ', '\n'))
            f.close()
        except IOError as err:
            log.log(repr(self),
                    "Cannot save the project: " + str(err),
                    level=logging.ERROR)
            msgBox = Qt.QMessageBox(self.wnd)
            msgBox.setText(tr.tr("Cannot save the project: ")+str(err))
            msgBox.setInformativeText(
                tr.tr("Assure you have the permissions to write the file."))
            msgBox.setIcon(Qt.QMessageBox.Critical)
            msgBox.exec_()
            del msgBox

            self.unlock()
            return

        wnd_title = str(paths.PROGRAM_NAME)
        wnd_title += ' ['+self.current_project_fname+']'
        self.wnd.setWindowTitle(wnd_title)

        self.unlock()

    def loadProject(self, pname=None):
        log.log(repr(self),
                'loading project, please wait...',
                level=logging.INFO)
        old_fname = self.current_project_fname

        if pname is None:
            project_fname = str(Qt.QFileDialog.getOpenFileName(
                self.wnd,
                tr.tr("Open a project"),
                os.path.join(self.current_dir, 'Untitled.lxn'),
                "Project (*.lxn *.prj);;All files (*.*)", None,
                utils.DIALOG_OPTIONS))
        else:
            project_fname = pname

        if not project_fname.strip():
            log.log(repr(self),
                    ' no project selected, retvert to previous state',
                    level=logging.INFO)
            return False
        else:
            log.log(repr(self),
                    ' project name: \''+str(project_fname)+'\'',
                    level=logging.DEBUG)

        proj_path = os.path.dirname(project_fname)

        try:
            dom = minidom.parse(project_fname)
        except Exception as err:
            log.log(repr(self),
                    'failed to parse project, xml formatting error',
                    level=logging.ERROR)
            return self.corruptedMsgBox(err)

        self.statusBar.showMessage(tr.tr('loading project, please wait...'))
        self.lock(False)

        try:
            root = dom.getElementsByTagName('project')[0]
            information_node = root.getElementsByTagName('information')[0]
            dark_frames_node = root.getElementsByTagName('dark-frames')[0]
            flat_frames_node = root.getElementsByTagName('flat-frames')[0]
            pict_frames_node = root.getElementsByTagName('frames')[0]

            try:  # backward compatibility
                bs_node_list = root.getElementsByTagName('bias-frames')
                bias_frames_node = bs_node_list[0]

                bs_frame_list = bias_frames_node.getElementsByTagName('image')
                total_bias = len(bs_frame_list)

                mbs_list = information_node.getElementsByTagName('master-bias')
                master_bias_node = mbs_list[0]

                mbs_ckd = master_bias_node.getAttribute('checked')
                master_bias_checked = int(mbs_ckd)

                mbs_mul = master_bias_node.getAttribute('mul')
                master_bias_mul = float(mbs_mul)
                has_bias_section = True
            except Exception as exc:
                log.log(repr(self),
                        'No bias section',
                        level=logging.DEBUG)
                total_bias = 0
                master_bias_node = None
                has_bias_section = False

            try:  # backward compatibility
                photometry_list = root.getElementsByTagName('photometry')
                photometry_node = photometry_list[0]
                has_photometry_section = True
            except Exception as exc:
                log.log(repr(self),
                        'no fotometric section, skipping star loading',
                        level=logging.DEBUG)
                has_photometry_section = False

            total_dark = len(dark_frames_node.getElementsByTagName('image'))
            total_flat = len(flat_frames_node.getElementsByTagName('image'))
            total_imgs = len(pict_frames_node.getElementsByTagName('image'))

            self.progress.reset()

            progress_max = total_bias
            progress_max += total_dark
            progress_max += total_flat
            progress_max += total_imgs - 1
            self.progress.setMaximum(progress_max)

            count = 0

            log.log(repr(self),
                    'loading project information',
                    level=logging.DEBUG)

            cdir_lst = information_node.getElementsByTagName('current-dir')
            crow_lst = information_node.getElementsByTagName('current-row')
            mdrk_lst = information_node.getElementsByTagName('master-dark')
            mflt_lst = information_node.getElementsByTagName('master-flat')
            arct_lst = information_node.getElementsByTagName('align-rect')
            mp_lst = information_node.getElementsByTagName('max-align-points')
            mq_lst = information_node.getElementsByTagName('min-point-quality')

            current_dir_node = cdir_lst[0]
            current_row_node = crow_lst[0]
            master_dark_node = mdrk_lst[0]
            master_flat_node = mflt_lst[0]
            align_rect_node = arct_lst[0]
            max_points_node = mp_lst[0]
            min_quality_node = mq_lst[0]

            imw = int(information_node.getAttribute('width'))
            imh = int(information_node.getAttribute('height'))
            dep = int(information_node.getAttribute('mode'))

            try:
                bayer_mode = int(information_node.getAttribute('bayer-mode'))
            except:
                bayer_mode = -1

            ar_w = int(align_rect_node.getAttribute('width'))
            ar_h = int(align_rect_node.getAttribute('height'))
            use_whole_image = int(align_rect_node.getAttribute('whole-image'))
            max_points = int(max_points_node.getAttribute('value'))
            min_quality = float(min_quality_node.getAttribute('value'))

            current_dir = current_dir_node.getAttribute('url')
            current_row = int(current_row_node.getAttribute('index'))
            master_dark_checked = int(master_dark_node.getAttribute('checked'))
            master_flat_checked = int(master_flat_node.getAttribute('checked'))
            master_dark_mul = float(master_dark_node.getAttribute('mul'))
            master_flat_mul = float(master_flat_node.getAttribute('mul'))

            try:
                url_node = master_bias_node.getElementsByTagName('url')[0]
                node_url = url_node.childNodes[0].data
                master_bias_url = utils.getProjectAbsURL(proj_path, node_url)
            except:
                master_bias_url = ''

            try:
                url_node = master_dark_node.getElementsByTagName('url')[0]
                node_url = url_node.childNodes[0].data
                master_dark_url = utils.getProjectAbsURL(proj_path, node_url)
            except:
                master_dark_url = ''

            try:
                url_node = master_flat_node.getElementsByTagName('url')[0]
                node_url = url_node.childNodes[0].data
                master_flat_url = utils.getProjectAbsURL(proj_path, node_url)
            except:
                master_flat_url = ''

            biasframelist = []
            biasListWidgetElements = []
            if has_bias_section:
                log.log(repr(self),
                        'reading bias-frames section',
                        level=logging.DEBUG)
                for node in bias_frames_node.getElementsByTagName('image'):
                    if self.progressWasCanceled():
                        return False
                    self.progress.setValue(count)
                    count += 1
                    im_bias_name = node.getAttribute('name')
                    try:
                        im_bias_used = int(node.getAttribute('used'))
                    except Exception as exc:
                        try:
                            st_im_used = str(node.getAttribute('used')).lower()
                            if st_im_used.lower() == 'false':
                                im_bias_used = 0
                            elif st_im_used.lower() == 'true':
                                im_bias_used = 2
                            else:
                                raise exc
                        except:
                            im_bias_used = 2

                    url_bias_node = node.getElementsByTagName('url')[0]
                    _bias_url = url_bias_node.childNodes[0].data
                    im_bias_url = utils.getProjectAbsURL(proj_path, _bias_url)

                    if 'page' in url_bias_node.attributes.keys():
                        im_bias_page = url_bias_node.getAttribute('page')
                        biasfrm = utils.Frame(im_bias_url,
                                              int(im_bias_page),
                                              skip_loading=False,
                                              **self.frame_open_args)
                    else:
                        biasfrm = utils.Frame(im_bias_url,
                                              0,
                                              skip_loading=False,
                                              **self.frame_open_args)

                    biasfrm.tool_name = im_bias_name
                    biasfrm.width = imw
                    biasfrm.height = imh
                    biasfrm.mode = dep
                    biasframelist.append(biasfrm)

                    q = Qt.QListWidgetItem(biasfrm.tool_name, None)
                    q.setToolTip(biasfrm.long_tool_name)
                    q.setCheckState(im_bias_used)

                    biasfrm.addProperty('listItem', q)
                    biasfrm.addProperty('frametype', utils.BIAS_FRAME_TYPE)
                    biasListWidgetElements.append(q)

            log.log(repr(self),
                    'reading dark-frames section',
                    level=logging.DEBUG)

            darkframelist = []
            darkListWidgetElements = []
            for node in dark_frames_node.getElementsByTagName('image'):
                if self.progressWasCanceled():
                    return False
                self.progress.setValue(count)
                count += 1
                im_dark_name = node.getAttribute('name')
                try:
                    im_dark_used = int(node.getAttribute('used'))
                except Exception as exc:
                    try:
                        st_im_used = str(node.getAttribute('used')).lower()
                        if st_im_used.lower() == 'false':
                            im_dark_used = 0
                        elif st_im_used.lower() == 'true':
                            im_dark_used = 2
                        else:
                            raise exc
                    except:
                        im_dark_used = 2

                url_dark_node = node.getElementsByTagName('url')[0]
                _dark_url = url_dark_node.childNodes[0].data
                im_dark_url = utils.getProjectAbsURL(proj_path, _dark_url)

                if 'page' in url_dark_node.attributes.keys():
                    im_dark_page = url_dark_node.getAttribute('page')
                    darkfrm = utils.Frame(im_dark_url,
                                          int(im_dark_page),
                                          skip_loading=False,
                                          **self.frame_open_args)
                else:
                    darkfrm = utils.Frame(im_dark_url,
                                          0,
                                          skip_loading=False,
                                          **self.frame_open_args)
                darkfrm.tool_name = im_dark_name
                darkfrm.width = imw
                darkfrm.height = imh
                darkfrm.mode = dep
                darkframelist.append(darkfrm)

                q = Qt.QListWidgetItem(darkfrm.tool_name, None)
                q.setToolTip(darkfrm.long_tool_name)
                q.setCheckState(im_dark_used)

                darkfrm.addProperty('listItem', q)
                darkfrm.addProperty('frametype', utils.DARK_FRAME_TYPE)
                darkListWidgetElements.append(q)

            log.log(repr(self),
                    'reading flatfield-frames section',
                    level=logging.DEBUG)

            flatframelist = []
            flatListWidgetElements = []
            for node in flat_frames_node.getElementsByTagName('image'):
                if self.progressWasCanceled():
                    return False
                self.progress.setValue(count)
                count += 1
                im_flat_name = node.getAttribute('name')
                try:
                    im_flat_used = int(node.getAttribute('used'))
                except Exception as exc:
                    try:
                        st_im_used = str(node.getAttribute('used')).lower()
                        if st_im_used.lower() == 'false':
                            im_flat_name = 0
                        elif st_im_used.lower() == 'true':
                            im_flat_name = 2
                        else:
                            raise exc
                    except:
                        im_flat_name = 2

                url_flat_node = node.getElementsByTagName('url')[0]
                _flat_url = url_flat_node.childNodes[0].data
                im_flat_url = utils.getProjectAbsURL(proj_path, _flat_url)

                if 'page' in url_flat_node.attributes.keys():
                    im_flat_page = url_flat_node.getAttribute('page')
                    flatfrm = utils.Frame(im_flat_url,
                                          int(im_flat_page),
                                          skip_loading=False,
                                          **self.frame_open_args)
                else:
                    flatfrm = utils.Frame(im_flat_url,
                                          0,
                                          skip_loading=False,
                                          **self.frame_open_args)
                flatfrm.tool_name = im_flat_name
                flatfrm.width = imw
                flatfrm.height = imh
                flatfrm.mode = dep
                flatframelist.append(flatfrm)

                q = Qt.QListWidgetItem(flatfrm.tool_name, None)
                q.setToolTip(flatfrm.long_tool_name)
                q.setCheckState(im_flat_used)

                flatfrm.addProperty('listItem', q)
                flatfrm.addProperty('frametype', utils.FLAT_FRAME_TYPE)
                flatListWidgetElements.append(q)

            log.log(repr(self),
                    'reading light-frames section',
                    level=logging.DEBUG)

            framelist = []
            listWidgetElements = []
            for node in pict_frames_node.getElementsByTagName('image'):
                if self.progressWasCanceled():
                        return False
                self.progress.setValue(count)
                count += 1
                im_name = node.getAttribute('name')
                try:
                    im_used = int(node.getAttribute('used'))
                except Exception as exc:
                    st_im_used = str(node.getAttribute('used')).lower()
                    if st_im_used.lower() == 'false':
                        im_used = 0
                    elif st_im_used.lower() == 'true':
                        im_used = 2
                    else:
                        raise exc

                im_url_node = node.getElementsByTagName('url')[0]
                _url = im_url_node.childNodes[0].data
                im_url = utils.getProjectAbsURL(proj_path, _url)

                if 'page' in im_url_node.attributes.keys():
                    im_page = im_url_node.getAttribute('page')
                    frm = utils.Frame(im_url,
                                      int(im_page),
                                      skip_loading=True,
                                      **self.frame_open_args)
                else:
                    frm = utils.Frame(im_url,
                                      0,
                                      skip_loading=True,
                                      **self.frame_open_args)

                for point in node.getElementsByTagName('align-point'):
                    point_id = point.getAttribute('id')
                    point_al = point.getAttribute('aligned').lower()
                    point_al = bool(point_al == 'True')
                    point_x = int(point.getAttribute('x'))
                    point_y = int(point.getAttribute('y'))
                    pnt = imgfeatures.AlignmentPoint(point_x, point_y,
                                                     point_id, point_id)
                    pnt.aligned = point_al
                    pnt.moved.connect(self.updateAlignPointPosition)
                    frm.addAlignPoint(pnt)

                for s in node.getElementsByTagName('star'):
                    st_x = int(s.getAttribute('x'))
                    st_y = int(s.getAttribute('y'))
                    st_name = s.getAttribute('name')
                    st_id = s.getAttribute('id')
                    st_r1 = float(s.getAttribute('inner_radius'))
                    st_r2 = float(s.getAttribute('middle_radius'))
                    st_r3 = float(s.getAttribute('outer_radius'))
                    st_ref = bool(int(s.getAttribute('reference')))
                    st_mag = float(s.getAttribute('magnitude'))
                    st = imgfeatures.Star(st_x, st_y,
                                          st_name, st_id)
                    st.r1 = st_r1
                    st.r2 = st_r2
                    st.r3 = st_r3
                    st.reference = st_ref
                    st.magnitude = st_mag
                    st.moved_rt.connect(self.updateStarPosition)
                    frm.addStar(st)

                for star in node.getElementsByTagName('align-point'):
                    point_id = point.getAttribute('id')
                    point_al = point.getAttribute('aligned').lower()
                    point_al = bool(point_al == 'True')
                    point_x = int(point.getAttribute('x'))
                    point_y = int(point.getAttribute('y'))
                    pnt = imgfeatures.AlignmentPoint(point_x, point_y,
                                                     point_id, point_id)
                    pnt.aligned = point_al
                    frm.alignpoints.append(pnt)

                offset_node = node.getElementsByTagName('offset')[0]
                offset_x = float(offset_node.getAttribute('x'))
                offset_y = float(offset_node.getAttribute('y'))

                if 'theta' in offset_node.attributes.keys():
                    offset_t = float(offset_node.getAttribute('theta'))
                else:
                    offset_t = 0

                frm.tool_name = im_name
                frm.width = imw
                frm.height = imh
                frm.mode = dep
                frm.setOffset([offset_x, offset_y])
                frm.setAngle(offset_t)

                q = Qt.QListWidgetItem(frm.tool_name, None)
                q.setToolTip(frm.long_tool_name)
                q.setCheckState(im_used)
                q.exif_properties = frm.properties
                listWidgetElements.append(q)

                frm.addProperty('listItem', q)
                frm.addProperty('frametype', utils.LIGHT_FRAME_TYPE)
                framelist.append(frm)

            if has_photometry_section:
                log.log(repr(self),
                        'reading stars section',
                        level=logging.DEBUG)
                time_attr = int(photometry_node.getAttribute('time_type'))
                use_image_time = bool(time_attr)

                # photometry section

                # NOTE: stars now are stored in each image, this
                #       is only for backward compatibility

                sels = photometry_node.getElementsByTagName('star')
                if len(sels) > 0 and len(framelist[0].stars) == 0:
                    for frm in framelist:
                        for snd in sels:
                            if self.progressWasCanceled():
                                return False
                            is_reference = int(snd.getAttribute('reference'))
                            s = imgfeatures.Star()
                            sx = int(snd.getAttribute('x'))
                            sy = int(snd.getAttribute('y'))
                            s.name = str(snd.getAttribute('name'))
                            s.r1 = float(snd.getAttribute('inner_radius'))
                            s.r2 = float(snd.getAttribute('middle_radius'))
                            s.r3 = float(snd.getAttribute('outer_radius'))
                            s.reference = bool(is_reference)
                            s.magnitude = float(snd.getAttribute('magnitude'))
                            frm.addStar(s)
                            s.setPosition(sx, sy)
                            s.moved_rt.connect(self.updateStarPosition)
            else:
                use_image_time = self.use_image_time

        except Exception as exc:
            self.current_project_fname = old_fname
            self.unlock()
            log.log(repr(self),
                    'An error has occurred while reading the project:' +
                    '\"' + str(exc) + '\"',
                    level=logging.ERROR)
            return self.corruptedMsgBox(str(exc))

        self.newProject()

        self.current_project_fname = project_fname

        log.log(repr(self),
                'setting up project environment',
                level=logging.DEBUG)

        for item in biasListWidgetElements:
            self.wnd.biasListWidget.addItem(item)

        for item in flatListWidgetElements:
            self.wnd.flatListWidget.addItem(item)

        for item in darkListWidgetElements:
            self.wnd.darkListWidget.addItem(item)

        for item in listWidgetElements:
            self.wnd.lightListWidget.addItem(item)

        self.currentWidth = imw
        self.currentHeight = imh
        self.currentDepht = dep
        self.framelist = framelist
        self.biasframelist = biasframelist
        self.darkframelist = darkframelist
        self.flatframelist = flatframelist
        self.image_idx = current_row
        self.master_bias_file = master_bias_url
        self.master_dark_file = master_dark_url
        self.master_flat_file = master_flat_url
        self.wnd.lightListWidget.setCurrentRow(current_row)
        self.aap_rectangle = (ar_w, ar_h)
        self.max_points = max_points
        self.min_quality = min_quality
        self.aap_wholeimage = use_whole_image
        self.wnd.imageDateCheckBox.setCheckState(2*use_image_time)
        self.current_dir = current_dir

        if self.framelist:
            self.unlockSidebar()
            self.wnd.manualAlignGroupBox.setEnabled(True)
            if bayer_mode >= 0:
                self.action_enable_rawmode.setChecked(True)
                self.bayer_tcb.setCurrentIndex(bayer_mode)
            else:
                self.action_enable_rawmode.setChecked(False)

        if has_bias_section:
            self.wnd.masterBiasCheckBox.setCheckState(master_bias_checked)
            self.wnd.masterBiasLineEdit.setText(master_bias_url)
            self.wnd.biasMulDoubleSpinBox.setValue(master_bias_mul)
            if self.biasframelist:
                self.wnd.biasClearPushButton.setEnabled(True)

        self.wnd.masterDarkCheckBox.setCheckState(master_dark_checked)
        self.wnd.masterDarkLineEdit.setText(master_dark_url)
        self.wnd.darkMulDoubleSpinBox.setValue(master_dark_mul)
        if self.darkframelist:
            self.wnd.darkClearPushButton.setEnabled(True)

        self.wnd.masterFlatCheckBox.setCheckState(master_flat_checked)
        self.wnd.masterFlatLineEdit.setText(master_flat_url)
        self.wnd.flatMulDoubleSpinBox.setValue(master_flat_mul)
        if self.flatframelist:
            self.wnd.flatClearPushButton.setEnabled(True)

        log.log(repr(self),
                'project fully loaded',
                level=logging.INFO)

        wnd_title = str(paths.PROGRAM_NAME)
        wnd_title += ' ['+self.current_project_fname+']'
        self.wnd.setWindowTitle(wnd_title)
        self.unlock()

    def autoDetectAlignPoints(self):
        i = self.framelist[self.image_idx].getData(asarray=True)
        i = i.astype(np.float32)

        if self.currentDepht > 1:
            i = i.sum(2)/self.currentDepht

        rw = self.aap_rectangle[0]
        rh = self.aap_rectangle[1]

        hh = 2*rh
        ww = 2*rw

        g = i[hh:-hh, ww:-ww]

        del i

        min_dist = int(math.ceil((rw**2 + rh**2)**0.5))

        if self.checked_autodetect_min_quality == 2:
            self.min_quality = 1
            points = []
            max_iteration = 25
            while (len(points) < ((self.max_points/2)+1) and
                   max_iteration > 0):
                points = cv2.goodFeaturesToTrack(g,
                                                 self.max_points,
                                                 self.min_quality,
                                                 min_dist)
                if points is None:
                    points = []
                self.min_quality *= 0.75
                max_iteration -= 1
        else:
            points = cv2.goodFeaturesToTrack(g,
                                             self.max_points,
                                             self.min_quality,
                                             min_dist)
            if points is None:
                points = []

        # ponts here is an numpy array!
        if len(points) > 0:
            for p in points:
                self.point_idx = self.addAlignPoint()
                self.wnd.spinBoxXAlign.setValue(p[0][0]+ww)
                self.wnd.spinBoxYAlign.setValue(p[0][1]+hh)

        elif self.checked_autodetect_min_quality:
            msgBox = Qt.QMessageBox()
            msgBox.setText(tr.tr("No suitable points foud!"))
            msgBox.setInformativeText(tr.tr("Try to add them manually."))
            msgBox.setIcon(Qt.QMessageBox.Warning)
            msgBox.exec_()
        else:
            msgBox = Qt.QMessageBox()
            msgBox.setText(tr.tr("No suitable points foud!"))
            msgBox.setInformativeText(tr.tr("Try to modify the " +
                                            "alignment settings."))
            msgBox.setIcon(Qt.QMessageBox.Warning)
            msgBox.exec_()

    def autoSetAlignPoint(self):
        image_idx = self.wnd.lightListWidget.currentRow()
        current_point = self.wnd.alignPointsListWidget.currentRow()
        self.statusBar.showMessage(tr.tr('detecting points, please wait...'))

        current_frame = self.framelist[image_idx]

        for point_idx in range(len(current_frame.alignpoints)):
            self.point_idx = point_idx
            if not self._autoPointCv(point_idx, image_idx):
                self.wnd.alignPointsListWidget.setCurrentRow(current_point)
                return False
        self.wnd.alignPointsListWidget.setCurrentRow(current_point)
        self.point_idx = current_point

    def _autoPointCv(self, point_idx, image_idx=0):
        point = self.framelist[image_idx].alignpoints[point_idx]

        # if already detected and not moved
        skip = True
        for i in range(len(self.framelist)):
            skip &= self.framelist[i].alignpoints[point_idx].aligned

        # then skip
        if skip:
            return True

        r_w = Int(self.aap_rectangle[0]/2)
        r_h = Int(self.aap_rectangle[1]/2)
        x1 = point.x-r_w
        x2 = point.x+r_w
        y1 = point.y-r_h
        y2 = point.y+r_h

        rawi = self.framelist[image_idx].getData(asarray=True)
        refi = rawi[y1:y2, x1:x2]
        del rawi

        cv_ref = refi.astype(np.float32)
        del refi

        self.progress.setMaximum(len(self.framelist)-1)
        self.lock()

        for i in range(len(self.framelist)):
            self.progress.setValue(i)

            frm = self.framelist[i]

            if self.progressWasCanceled():
                return False

            if i == image_idx:
                continue
            msg = tr.tr('detecting point')+' '+str(point_idx+1)+' '
            msg += tr.tr('of')+' '
            msg += str(len(self.framelist[image_idx].alignpoints))
            msg += tr.tr(' ')+tr.tr('on image')+tr.tr(' ')+str(i)
            msg += tr.tr(' ')+tr.tr('of')+tr.tr(' ')+str(len(self.framelist)-1)
            self.statusBar.showMessage(msg)

            if self.aap_wholeimage == 2:
                rawi = frm.getData(asarray=True)
            else:
                rawi = frm.getData(asarray=True)[y1-r_h:y2+r_h, x1-r_w:x2+r_w]

            cv_im = rawi.astype(np.float32)

            del rawi

            # TODO: fix error occurring when
            #       align-rectangle is outside the image
            res = cv2.matchTemplate(cv_im, cv_ref, self.current_match_mode)
            minmax = cv2.minMaxLoc(res)
            del res
            if self.aap_wholeimage == 2:
                frm.alignpoints[point_idx].x = minmax[2][0]+r_w
                frm.alignpoints[point_idx].y = minmax[2][1]+r_h
            else:
                frm.alignpoints[point_idx].x = minmax[2][0]+x1
                frm.alignpoints[point_idx].y = minmax[2][1]+y1

        self.unlock()

        return True

    def doAlign(self, clicked):
        return self.align()

    def align(self, do_reset=None, do_align=None, do_derot=None):
        result = None

        if (do_reset is not None or
                do_align is not None or
                do_derot is not None):
            align = bool(do_align)
            derotate = bool(do_derot)
            reset = bool(do_reset)
        elif self.align_dlg.exec_():
            align = self.align_dlg.getAlign()
            derotate = self.align_dlg.getDerotate()
            reset = self.align_dlg.getReset()
        else:
            return False

        if reset:
            log.log(repr(self),
                    'Resetting alignment...',
                    level=logging.DEBUG)
            self.progress.setMaximum(len(self.framelist))
            self.lock()
            count = 0
            for i in self.framelist:
                count += 1
                self.progress.setValue(count)
                if i.isUsed():
                    log.log(repr(self),
                            'Image ' + i.name +
                            ' -> shift = (0.0, 0.0)  angle=0.0',
                            level=logging.INFO)
                    msg = tr.tr('Resetting alignment for image')+' '+i.name
                    self.statusBar.showMessage(msg)
                    i.setAngle(0)
                    i.setOffset((0, 0))
                else:
                    log.log(repr(self),
                            ' Skipping image ' + i.name,
                            level=logging.INFO)
            self.unlock()
        else:
            self.is_aligning = True
            log.log(repr(self),
                    'Beginning alignment process...',
                    level=logging.INFO)
            if self.current_align_method == 0:
                result = self._alignPhaseCorrelation(align, derotate)
            elif self.current_align_method == 1:
                result = self._alignAlignPoints(align, derotate)
            self.is_aligning = False

        return result

    def _derotateAlignPoints(self, var_matrix):
        vecslist = []

        for i in self.framelist:
            _tmp = []

            for p in i.alignpoints:
                _tmp.append(np.array([p.x, p.y])-i.offset[0:2])

            vecslist.append(_tmp)

        del _tmp

        refs = vecslist[0]
        nvecs = len(vecslist[0])
        angles = [0]

        for vecs in vecslist[1:]:
            angle = 0
            for i in range(nvecs):

                x1 = refs[i][0]
                y1 = refs[i][1]
                x2 = vecs[i][0]
                y2 = vecs[i][1]

                vmod = (vecs[i][0]**2 + vecs[i][1]**2)**0.5
                rmod = (refs[i][0]**2 + refs[i][1]**2)**0.5

                if (vmod == 0) or (rmod == 0):
                    continue

                cosa = ((x1*x2 + y1*y2)/(vmod*rmod))
                sina = ((x2*y1 - x1*y2)/(vmod*rmod))

                if cosa > 1:
                    # this should never never never occur
                    cosa = 1.0

                if sina > 1:
                    # this should never never never occur
                    sina = 1.0

                angle += (math.atan2(sina, cosa)*180.0/math.pi)*var_matrix[i]

            angle /= var_matrix.sum()

            angles.append(angle)

        for i in range(len(self.framelist)):
            self.framelist[i].angle = -angles[i]

    def _alignAlignPoints(self, align, derotate):
        if not self.framelist:
            return False

        total_points = len(self.framelist[0].alignpoints)
        total_images = len(self.framelist)

        if self.framelist and total_points > 0:
            self.statusBar.showMessage(tr.tr('Calculating image shift') +
                                       ', '+tr.tr('please wait...'))

            self.progress.setMaximum(total_images-1)
            self.lock()

            mat = np.zeros((total_images, total_points, 2))

            for i in range(total_images):
                for j in range(total_points):
                    p = self.framelist[i].alignpoints[j]
                    mat[i, j, 0] = p.x
                    mat[i, j, 1] = p.y

            x_stk = mat[..., 0].mean()
            y_stk = mat[..., 1].mean()

            mat2 = mat-[x_stk, y_stk]

            var = np.empty((len(mat[0])))

            for i in range(len(mat[0])):
                dist = (mat2[..., i, 0]**2 + mat2[..., i, 1]**2)
                var[i] = dist.var()

            del mat2

            # Added 0.00000001 to avoid division by zero
            w = 1/(var+0.00000001)
            del var

            if align:
                for img in self.framelist:
                    x = 0
                    y = 0
                    for j in range(len(img.alignpoints)):
                        x += img.alignpoints[j].x*w[j]
                        y += img.alignpoints[j].y*w[j]

                    img.offset[0] = x/w.sum()
                    img.offset[1] = y/w.sum()

                    self.progress.setValue(i)
                    if ((i % 25) == 0) and self.progressWasCanceled():
                        return False
            else:
                for img in self.framelist:
                    img.offset[0] = 0
                    img.offset[1] = 0

            self.unlock()
            self.statusBar.showMessage(tr.tr('DONE'))

            if (total_points > 1) and derotate:
                self._derotateAlignPoints(w)

                rotation_center = (self.currentWidth/2, self.currentHeight/2)

                # compesate shift for rotation
                for img in self.framelist:
                    x = img.offset[0]-rotation_center[0]
                    y = img.offset[1]-rotation_center[1]
                    alpha = math.pi*img.angle/180.0

                    cosa = math.cos(alpha)
                    sina = math.sin(alpha)

                    # new shift
                    img.offset[0] = self.currentWidth/2 + (x*cosa + y*sina)
                    img.offset[1] = self.currentWidth/2 + (y*cosa - x*sina)
            else:
                for img in self.framelist:
                    img.angle = 0

            self.progress.setMaximum(3*len(self.framelist))

            if align:
                self.lock()
                msg = tr.tr('Calculating references, please wait...')
                self.statusBar.showMessage(msg)
                count = 0
                ref_set = False

                for img in self.framelist:
                    self.progress.setValue(count)
                    count += 1
                    if self.progressWasCanceled():
                        return False

                    if img.isUsed():
                        if not ref_set:
                            ref_x = img.offset[0]
                            ref_y = img.offset[1]
                            ref_set = True
                        else:
                            ref_x = min(ref_x, img.offset[0])
                            ref_y = min(ref_y, img.offset[1])

                for img in self.framelist:
                    self.progress.setValue(count)
                    count += 1

                    if self.progressWasCanceled():
                        return False

                    if img.isUsed():
                        img.offset[0] = float(img.offset[0]-ref_x)
                        img.offset[1] = float(img.offset[1]-ref_y)

                self.progress.reset()

                self.unlock()
            else:
                for img in self.framelist:
                    img.setOffset([0, 0])

    def _alignPhaseCorrelation(self, align, derotate):
        self.statusBar.showMessage(tr.tr('Computing phase correlation') +
                                   ', '+tr.tr('please wait...'))

        sw = self.newMdiImageViewer("Phase correlation")
        iv = self.mdi_windows[sw]['widget']
        iv.setColorMap(cmaps.jet)
        iv.forceDisplayLevelsFitMode(1)

        self.lock()
        self.progress.setMaximum(len(self.framelist))

        ref = None
        mask = utils.generateCosBell(self.currentWidth, self.currentHeight)

        sharp1 = self.wnd.sharp1DoubleSpinBox.value()
        sharp2 = self.wnd.sharp2DoubleSpinBox.value()

        count = 0
        for img in self.framelist:
            self.progress.setValue(count)
            count += 1
            if self.progressWasCanceled():
                self.unlock()
                self.statusBar.showMessage(tr.tr('canceled by the user'))
                return False

            if img.isUsed():
                QtGui.QApplication.instance().processEvents()
                if ref is None:
                    ref = img
                    log.log(repr(self),
                            'using image '+img.name+' as reference',
                            level=logging.INFO)
                    ref_data = ref.getData(asarray=True)
                    if len(ref_data.shape) == 3:
                        ref_data = ref_data.sum(2)
                    ref_data *= mask
                    ref.setOffset([0, 0])
                else:
                    log.log(repr(self),
                            'registering image '+img.name,
                            level=logging.INFO)

                    img_data = img.getData(asarray=True)
                    if len(img_data.shape) == 3:
                        img_data = img_data.sum(2)
                    img_data *= mask

                    data = utils.register_image(
                        ref_data, img_data,
                        sharp1, sharp2,
                        align, derotate,
                        self.phase_interpolation_order)

                    self._phase_align_data = (data[1], data[2], data[0])
                    self.statusBar.showMessage(tr.tr('shift: ') +
                                               str(data[1]) + ', ' +
                                               tr.tr('rotation: ') +
                                               str(data[2]))
                    del img_data
                    if (data[0] is not None and
                            self.checked_show_phase_img == 2):
                        iv.showImage(data[0])
                    img.setOffset(data[1])
                    img.setAngle(data[2])
        del mask
        self._phase_align_data = None
        sw.close()
        self.unlock()
        self.statusBar.showMessage(tr.tr('DONE'))

    def getStackingMethod(self, method, framelist, bias_image,
                          dark_image, flat_image, **args):
        """
        available stacking methods:
         _______________________
        |   method   |   name   |
        |____________|__________|
        |     0      |  average |
        |____________|__________|
        |     1      |  median  |
        |____________|__________|
        |     2      |  k-sigma |
        |____________|__________|
        |     3      | std.dev. |
        |____________|__________|
        |     4      | variance |
        |____________|__________|
        |     5      |  maximum |
        |____________|__________|
        |     6      |  minimum |
        |____________|__________|
        |     7      |  product |
        |____________|__________|

        """
        if method == 0:
            return self.average(framelist, bias_image,
                                dark_image, flat_image,
                                **args)
        elif method == 1:
            return self.median(framelist, bias_image,
                               dark_image, flat_image,
                               **args)
        elif method == 2:
            return self.sigmaclip(framelist, bias_image,
                                  dark_image, flat_image,
                                  **args)
        elif method == 3:
            return self.stddev(framelist, bias_image,
                               dark_image, flat_image,
                               **args)
        elif method == 4:
            return self.variance(framelist, bias_image,
                                 dark_image, flat_image,
                                 **args)
        elif method == 5:
            return self.maximum(framelist, bias_image,
                                dark_image, flat_image,
                                **args)
        elif method == 6:
            return self.minimum(framelist, bias_image,
                                dark_image, flat_image,
                                **args)
        elif method == 7:
            return self.product(framelist, bias_image,
                                dark_image, flat_image,
                                **args)
        else:
            # this should never happen
            log.log(repr(self),
                    "Something that sould never happen has just happened: " +
                    "An unknonw stacking method has been selected!",
                    level=logging.ERROR)
            return None

    def doStack(self, clicked):
        self.stack()

    def stack(self, method=None, skip_light=False):
        self.clearResult()

        # selecting method and setting options
        # before stacking

        self.stack_dlg.setSectionDisabled(
            self.stack_dlg.section_light,
            skip_light)

        # self.stack_dlg.setSectionDisabled(
        #     self.stack_dlg.section_bias,
        #     self.wnd.masterBiasCheckBox.checkState())

        # self.stack_dlg.setSectionDisabled(
        #     self.stack_dlg.section_dark,
        #     self.wnd.masterDarkCheckBox.checkState())

        # self.stack_dlg.setSectionDisabled(
        #     self.stack_dlg.section_flat,
        #     self.wnd.masterFlatCheckBox.checkState())

        if method is not None:
            bias_method = method
            dark_method = method
            flat_method = method
            lght_method = method

        elif self.stack_dlg.exec_():
            methods = self.stack_dlg.getStackingMethods()

            lght_method = methods[self.stack_dlg.section_light]
            bias_method = methods[self.stack_dlg.section_bias]
            dark_method = methods[self.stack_dlg.section_dark]
            flat_method = methods[self.stack_dlg.section_flat]
        else:
            return False

        stacking_params = self.stack_dlg.getStackingParameters()

        bias_args = stacking_params[self.stack_dlg.section_bias]
        dark_args = stacking_params[self.stack_dlg.section_dark]
        flat_args = stacking_params[self.stack_dlg.section_flat]
        lght_args = stacking_params[self.stack_dlg.section_light]
        hotp_args = self.stack_dlg.getHPCorrectionParameters()

        self.lock()

        self.master_bias_file = str(self.wnd.masterBiasLineEdit.text())
        self.master_dark_file = str(self.wnd.masterDarkLineEdit.text())
        self.master_flat_file = str(self.wnd.masterFlatLineEdit.text())

        if (self.wnd.masterBiasCheckBox.checkState() == 2):
            if os.path.isfile(self.master_bias_file):
                bas = utils.Frame(self.master_bias_file,
                                  **self.frame_open_args)
                self._bas = bas.getData(asarray=True, ftype=self.ftype)
            elif not self.master_bias_file.strip():
                pass  # ignore
            else:
                msgBox = Qt.QMessageBox()
                msgBox.setText(tr.tr("Cannot open") + " \'" +
                               self.master_bias_file + "\':")
                msgBox.setInformativeText(tr.tr("the file does not exist."))
                msgBox.setIcon(Qt.QMessageBox.Critical)
                msgBox.exec_()
                return False
        elif self.biasframelist:
            self.statusBar.showMessage(tr.tr('Creating master-bias') +
                                       ', '+tr.tr('please wait...'))
            _bas = self.getStackingMethod(bias_method,
                                          self.biasframelist,
                                          None, None, None,
                                          **bias_args)
            if _bas is None:
                return False
            else:
                self._bas = _bas

        if self.wnd.masterDarkCheckBox.checkState() == 2:
            if os.path.isfile(self.master_dark_file):
                drk = utils.Frame(self.master_dark_file,
                                  **self.frame_open_args)
                self._drk = drk.getData(asarray=True, ftype=self.ftype)
            elif not self.master_dark_file.strip():
                pass  # ignore
            else:
                msgBox = Qt.QMessageBox()
                msgBox.setText(tr.tr("Cannot open") + " \'" +
                               self.master_dark_file+"\':")
                msgBox.setInformativeText(tr.tr("the file does not exist."))
                msgBox.setIcon(Qt.QMessageBox.Critical)
                msgBox.exec_()
                return False
        elif self.darkframelist:
            self.statusBar.showMessage(tr.tr('Creating master-dark') +
                                       ', '+tr.tr('please wait...'))
            _drk = self.getStackingMethod(dark_method,
                                          self.darkframelist,
                                          None, None, None,
                                          **dark_args)
            if _drk is None:
                return False
            else:
                self._drk = _drk

        if self.wnd.masterFlatCheckBox.checkState() == 2:
            if os.path.isfile(self.master_flat_file):
                flt = utils.Frame(self.master_flat_file,
                                  **self.frame_open_args)
                self._flt = flt.getData(asarray=True, ftype=self.ftype)
            elif not self.master_flat_file.strip():
                pass  # ignore
            else:
                msgBox = Qt.QMessageBox()
                msgBox.setText(tr.tr("Cannot open")+" \'" +
                               self.master_dark_file+"\':")
                msgBox.setInformativeText(tr.tr("the file does not exist."))
                msgBox.setIcon(Qt.QMessageBox.Critical)
                msgBox.exec_()
                return False
        elif self.flatframelist:
            self.statusBar.showMessage(tr.tr('Creating master-flat') +
                                       ', '+tr.tr('please wait...'))
            _flt = self.getStackingMethod(flat_method,
                                          self.flatframelist,
                                          None, None, None,
                                          **flat_args)
            if _flt is None:
                return False
            else:
                self._flt = _flt

        if skip_light:
            self.statusBar.clearMessage()
        else:
            self.statusBar.showMessage(tr.tr('Stacking images')+', ' +
                                       tr.tr('please wait...'))

            _stk = self.getStackingMethod(lght_method,
                                          self.framelist,
                                          self._bas,
                                          self._drk,
                                          self._flt,
                                          hotpixel_options=hotp_args,
                                          **lght_args)
            if _stk is None:
                self.unlock()
                return False
            else:
                self._stk = _stk - _stk.min()
                QtGui.QApplication.instance().processEvents()

                del _stk

                self.showResultImage(newtab=True)
                self.statusBar.showMessage(tr.tr('DONE'))

        self.unlock()

        self.wnd.toolBox.setCurrentIndex(7)

        return ((lght_method, lght_args),
                (bias_method, bias_args),
                (dark_method, dark_args),
                (flat_method, flat_args),
                hotp_args)

    def generateMasters(self, bias_image=None, dark_image=None,
                        flat_image=None, hot_pixels_options=None):
        log.log(repr(self),
                "generating master frames",
                level=logging.INFO)

        if (bias_image is not None):
            log.log(repr(self),
                    "generating master bias-frame",
                    level=logging.DEBUG)
            master_bias = bias_image*self.master_bias_mul_factor
        else:
            master_bias = None

        if dark_image is not None:
            log.log(repr(self),
                    "generating master dark-frame",
                    level=logging.DEBUG)
            if master_bias is not None:
                master_dark = dark_image - master_bias
                master_dark *= self.master_dark_mul_factor
            else:
                master_dark = dark_image * self.master_dark_mul_factor

            log.log(repr(self),
                    "generating hot-pixels map",
                    level=logging.DEBUG)

            if hot_pixels_options is not None:
                try:
                    trashold = hot_pixels_options['hp_trashold']
                except KeyError:
                    hot_pixels = None
                else:
                    if (len(master_dark.shape) == 2 or
                            hot_pixels_options['hp_global']):
                        mean_dark = master_dark.mean()
                        ddev_dark = master_dark.std()
                        diff_dark = abs(master_dark-mean_dark)
                        clip_datk = trashold*ddev_dark

                        hp_list = np.argwhere(diff_dark >= clip_datk)
                        hot_pixels = {'global': True,
                                      'data': hp_list}
                        hp_count = len(hot_pixels['data'])

                        log.log(repr(self),
                                "Found " + str(hp_count) + " hot pixels",
                                level=logging.INFO)

                    elif len(master_dark.shape) == 3:
                        hot_pixels = {'global': False,
                                      'data': []}
                        hp_count = 0

                        for c in range(master_dark.shape[2]):
                            mean_dark = master_dark[..., c].mean()
                            ddev_dark = master_dark[..., c].std()
                            diff_dark = abs(master_dark[..., c]-mean_dark)
                            clip_datk = trashold*ddev_dark

                            hp_list = np.argwhere(diff_dark >= clip_datk)
                            hp_count += len(hp_list)
                            hot_pixels['data'].append(hp_list)

                        log.log(repr(self),
                                "Found "+str(hp_count)+" hot pixels",
                                level=logging.INFO)
            else:
                hot_pixels = None
        else:
            master_dark = None
            hot_pixels = None

        if flat_image is not None:
            log.log(repr(self),
                    "generating master flatfield",
                    level=logging.DEBUG)
            # this should avoid division by zero
            zero_mask = ((flat_image == 0).astype(self.ftype))*flat_image.max()
            corrected = flat_image + zero_mask
            del zero_mask

            normalizer = corrected.min()
            master_flat = ((corrected/normalizer)*self.master_flat_mul_factor)
            del corrected
        else:
            master_flat = None

        return (master_bias, master_dark, master_flat, hot_pixels)

    def calibrate(self, image, master_bias=None,
                  master_dark=None, master_flat=None,
                  hot_pixels=None, debayerize_result=False,
                  **args):

        if (master_bias is None and
                master_dark is None and
                master_flat is None):
            log.log(repr(self),
                    "skipping image calibration",
                    level=logging.INFO)
        else:
            log.log(repr(self),
                    "calibrating image...",
                    level=logging.INFO)

            if master_bias is not None:
                log.log(repr(self),
                        "calibrating image: subtracting bias",
                        level=logging.DEBUG)
                image -= master_bias

            if master_dark is not None:
                log.log(repr(self),
                        "calibrating image: subtracting master dark",
                        level=logging.DEBUG)
                image -= master_dark

            if hot_pixels is not None:
                log.log(repr(self),
                        "calibrating image: correcting for hot pixels",
                        level=logging.DEBUG)
                """
        The HOT pixels will be replaced by the mean value of its neighbours X

                                NORMAL IMAGE
                            +---+---+---+---+---+
                            |RGB|RGB|RGB|RGB|RGB|
                            +---+---+---+---+---+
                            |RGB|RGB| X |RGB|RGB|
                            +---+---+---+---+---+
                            |RGB| X |HOT| X |RGB|
                            +---+---+---+---+---+
                            |RGB|RGB| X |RGB|RGB|
                            +---+---+---+---+---+
                            |RGB|RGB|RGB|RGB|RGB|
                            +---+---+---+---+---+

                                  RAW IAMGE
                            +---+---+---+---+---+
                            | R | G | X | G | R |
                            +---+---+---+---+---+
                            | G | B | G | B | G |
                            +---+---+---+---+---+
                            | X | G |HOT| G | X |
                            +---+---+---+---+---+
                            | G | B | G | B | G |
                            +---+---+---+---+---+
                            | R | G | X | G | R |
                            +---+---+---+---+---+

        This is better than simply assign to it a ZERO value.
                """

                cnt = 0
                if hot_pixels['global']:
                    msg = tr.tr("Correcting for hotpixels...")
                    self.progress_dialog.setLabelText(msg)
                    self.progress_dialog.setValue(0)
                    self.progress_dialog.setMaximum(len(hot_pixels['data']))
                    self.progress_dialog.show()
                    for hotp in hot_pixels['data']:
                        cnt += 1
                        if cnt % 100 == 0:  # do not overload main application
                            self.progress_dialog.setValue(cnt)
                            QtGui.QApplication.instance().processEvents()
                        hotp_x = hotp[1]
                        hotp_y = hotp[0]

                        navg = utils.getNeighboursAverage(image,
                                                          hotp_x,
                                                          hotp_y,
                                                          self.isBayerUsed())
                        image[hotp_y, hotp_x] = navg
                else:
                    total_progress = 0
                    for c in range(len(hot_pixels['data'])):
                        total_progress += len(hot_pixels['data'][c])
                    self.progress_dialog.setValue(0)
                    self.progress_dialog.setMaximum(total_progress)
                    self.progress_dialog.show()
                    for c in range(len(hot_pixels['data'])):
                        msg = tr.tr("Correcting for hotpixels in component")
                        msg += " "+str(c)+"..."
                        self.progress_dialog.setLabelText(msg)
                        for hotp in hot_pixels['data'][c]:
                            cnt += 1
                            if cnt % 100 == 0:
                                # do not overload main application
                                self.progress_dialog.setValue(cnt)
                                QtGui.QApplication.instance().processEvents()
                            hotp_x = hotp[1]
                            hotp_y = hotp[0]
                            navg = utils.getNeighboursAverage(
                                image[..., c],
                                hotp_x,
                                hotp_y,
                                self.isBayerUsed())
                            image[hotp_y, hotp_x, c] = navg
                self.progress_dialog.hide()
            if master_flat is not None:
                log.log(repr(self),
                        "calibrating image: dividing by master flat",
                        level=logging.DEBUG)
                image /= master_flat

        if debayerize_result:
            debay = self.debayerize(image)
            return debay
        else:
            return image

    def registerImages(self, img, img_data):
        if img.angle != 0:
            log.log(repr(self),
                    "rotating of "+str(img.angle)+" degrees",
                    level=logging.INFO)
            img_data = sp.ndimage.interpolation.rotate(
                img_data, img.angle, order=self.interpolation_order,
                reshape=False, mode='constant', cval=0.0)
        else:
            log.log(repr(self),
                    "skipping rotation",
                    level=logging.INFO)
        shift = np.zeros([len(img_data.shape)])
        shift[0] = -img.offset[1]
        shift[1] = -img.offset[0]

        if (shift[0] != 0) or (shift[1] != 0):
            log.log(repr(self),
                    "shifting of "+str(shift[0:2])+" pixels",
                    level=logging.INFO)
            img_data = sp.ndimage.interpolation.shift(
                img_data, shift, order=self.interpolation_order,
                mode='constant', cval=0.0)
        else:
            log.log(repr(self),
                    "skipping shift",
                    level=logging.INFO)
        del shift
        return img_data

    def nativeOperationOnImages(self, operation, name, framelist,
                                bias_image=None, dark_image=None,
                                flat_image=None, post_operation=None,
                                **args):
        result = None

        if 'hotpixel_options' in args:
            hotp_args = args['hotpixel_options']
        else:
            hotp_args = None

        masters = self.generateMasters(bias_image,
                                       dark_image,
                                       flat_image,
                                       hotp_args)
        master_bias = masters[0]
        master_dark = masters[1]
        master_flat = masters[2]
        hot_pixels = masters[3]

        total = len(framelist)

        log.log(repr(self),
                'Computing '+str(name)+', please wait...',
                level=logging.INFO)

        self.progress.reset()
        self.progress.setMaximum(4*(total-1))

        count = 0
        progress_count = 0

        if 'chunks_size' in args and args['chunks_size'] > 1:
            chunks = []
            chunks_size = int(args['chunks_size'])
        else:
            chunks_size = 1

        for img in framelist:
            self.progress.setValue(progress_count)
            progress_count += 1

            if self.progressWasCanceled():
                return None

            if img.isUsed():
                count += 1
                log.log(repr(self),
                        'Using image '+img.name,
                        level=logging.INFO)
            else:
                progress_count += 3
                log.log(repr(self),
                        'Skipping image '+img.name,
                        level=logging.INFO)
                continue

            r = img.getData(asarray=True, ftype=self.ftype)

            if self.progressWasCanceled():
                return None

            self.progress.setValue(progress_count)
            progress_count += 1

            if img.isRGB() and r.shape[2] > 3:
                r = r[..., 0:3]

            r = self.calibrate(r,
                               master_bias,
                               master_dark,
                               master_flat,
                               hot_pixels,
                               **args)

            if self.progressWasCanceled():
                return None

            self.progress.setValue(progress_count)
            progress_count += 1

            r = self.registerImages(img, r)

            if self.progressWasCanceled():
                return None

            self.progress.setValue(progress_count)
            progress_count += 1

            if chunks_size > 1:
                if len(chunks) <= chunks_size:
                    chunks.append(r)
                else:
                    if 'numpy_like' in args and args['numpy_like'] is True:
                        result = operation(chunks, axis=0)
                    else:
                        result = operation(chunks)
                    chunks = [result, ]
            else:
                if result is None:
                    result = r.copy()
                else:
                    if 'numpy_like' in args and args['numpy_like'] is True:
                        result = operation((result, r), axis=0)
                    else:
                        result = operation(result, r)
            del r

        self.progress.setValue(4*(total-1))

        if result is not None:
            if chunks_size > 1 and len(chunks) > 1:
                if 'numpy_like' in args and args['numpy_like'] is True:
                    result = operation(chunks, axis=0)
                else:
                    result = operation(chunks)
            self.statusBar.showMessage(tr.tr('Computing final image...'))
            if post_operation is not None:
                result = post_operation(result, count)

        self.statusBar.clearMessage()

        return result

    # TODO: make option to change subw and subh
    def _operationOnSubregions(self, operation, filelist, shape,
                               title="", subw=256, subh=256, **args):
        """
        Executes the 'operation' on each subregion of size 'subw'x'subh'
        of images stored in temporary files listed in filelist.
        the original shape of the images must be passed as 'shape'
        """

        if not filelist:
            return None

        n_y_subs = shape[0]/subh
        n_x_subs = shape[1]/subw

        total_subs = (n_x_subs+1) * (n_y_subs+1)

        log.log(repr(self),
                "Executing "+str(title) +
                ": splitting images in " +
                str(total_subs)+" sub-regions",
                level=logging.DEBUG)

        self.statusBar.showMessage(tr.tr('Computing') + ' ' +
                                   str(title) + ', ' +
                                   tr.tr('please wait...'))
        self.progress.reset
        self.progress.setMaximum(total_subs*(len(filelist)+1))
        progress_count = 0

        x = 0
        y = 0
        result = np.zeros(shape)
        mmaps = []

        if self.checked_compressed_temp == 0:
            for fl in filelist:
                progress_count += 1
                self.progress.setValue(progress_count)
                if self.progressWasCanceled():
                    return None
                mmaps.append(utils.loadTmpArray(fl))
        count = 0
        while y <= n_y_subs:
            x = 0
            while x <= n_x_subs:
                xst = x*subw
                xnd = (x+1) * subw
                yst = y*subh
                ynd = (y+1) * subh

                lst = []

                if self.checked_compressed_temp == 2:
                    for fl in filelist:
                        progress_count += 1
                        self.progress.setValue(progress_count)
                        if self.progressWasCanceled():
                            return None
                        n = utils.loadTmpArray(fl)
                        sub = n[yst:ynd, xst:xnd].copy()
                        lst.append(sub)
                else:
                    for n in mmaps:
                        progress_count += 1
                        self.progress.setValue(progress_count)
                        if self.progressWasCanceled():
                            return None
                        sub = n[yst:ynd, xst:xnd].copy()
                        lst.append(sub)
                count += 1

                log.log(repr(self),
                        'Computing '+str(title) +
                        ' on subregion '+str(count) +
                        ' of '+str(total_subs),
                        level=logging.INFO)

                self.statusBar.showMessage(tr.tr('Computing') +
                                           ' '+str(title)+' ' +
                                           tr.tr('on subregion') +
                                           ' '+str(count)+' ' +
                                           tr.tr('of')+' ' +
                                           str(total_subs))
                QtGui.QApplication.instance().processEvents()

                if args:
                    try:
                        operation(lst,
                                  axis=0,
                                  out=result[yst:ynd, xst:xnd],
                                  **args)
                    except:
                        operation(lst, axis=0, out=result[yst:ynd, xst:xnd])
                else:
                    operation(lst, axis=0, out=result[yst:ynd, xst:xnd])
                del lst
                x += 1
            y += 1
        del mmaps
        return result

    def sigmaClipping(self, array, axis=-1, out=None, **args):
        lkappa = args['lk']
        hkappa = args['hk']
        itr = args['iterations']

        clipped = np.ma.masked_array(array)

        for i in range(itr):
            sigma = np.std(array, axis=axis)
            mean = np.mean(array, axis=axis)

            min_clip = mean - lkappa*sigma
            max_clip = mean + hkappa*sigma

            del sigma
            del mean

            clipped = np.ma.masked_less(clipped, min_clip)
            clipped = np.ma.masked_greater(clipped, max_clip)

            del min_clip
            del max_clip

        if out is None:
            return np.ma.average(clipped, axis=axis)
        else:
            out[...] = np.ma.average(clipped, axis=axis)

    def medianSigmaClipping(self, array, axis=-1, out=None, **args):
        # TODO: check -> validate -> add functionality

        lkappa = args['lmk']
        hkappa = args['hmk']
        itr = args['miterations']

        clipped = np.ma.masked_array(array)

        for i in range(itr):
            sigma = np.std(array, axis=axis)
            mean = np.median(array, axis=axis)
            min_clip = mean - lkappa*sigma
            max_clip = mean + hkappa*sigma

            del sigma
            del mean

            clipped = np.ma.masked_less(clipped, min_clip)
            clipped = np.ma.masked_greater(clipped, max_clip)

            del min_clip
            del max_clip

        if out is None:
            return np.ma.median(clipped, axis=axis)
        else:
            out[...] = np.ma.median(clipped, axis=axis)

    def average(self, framelist, bias_image=None,
                dark_image=None, flat_image=None,
                **args):
        return self.nativeOperationOnImages(
            np.add, tr.tr('average'), framelist,
            bias_image, dark_image, flat_image,
            post_operation=np.divide, **args)

    def stddev(self, framelist, bias_image=None,
               dark_image=None, flat_image=None,
               **args):
        avg = self.average(framelist,  bias_image, dark_image, flat_image)
        return self.nativeOperationOnImages(
            lambda a1, a2: (a2-avg)**2,
            tr.tr('standard deviation'),
            framelist,
            dark_image,
            flat_image,
            post_operation=lambda x, n: np.sqrt(x/(n-1)),
            **args)

    def variance(self, framelist, bias_image=None,
                 dark_image=None, flat_image=None,
                 **args):
        avg = self.average(framelist, bias_image, dark_image, flat_image)
        return self.nativeOperationOnImages(
            lambda a1, a2: (a2-avg)**2,
            tr.tr('variance'),
            framelist,
            dark_image,
            flat_image,
            post_operation=lambda x, n: x/(n-1),
            **args)

    # TODO: try to make a native function
    def sigmaclip(self, framelist, bias_image=None,
                  dark_image=None, flat_image=None,
                  **args):
        return self.operationOnImages(self.sigmaClipping,
                                      tr.tr('sigma clipping'),
                                      framelist,
                                      bias_image,
                                      dark_image,
                                      flat_image,
                                      **args)

    # TODO: try to make a native function
    def median(self, framelist, bias_image=None,
               dark_image=None, flat_image=None,
               **args):
        return self.operationOnImages(np.median,
                                      tr.tr('median'),
                                      framelist,
                                      bias_image,
                                      dark_image,
                                      flat_image,
                                      **args)

    def maximum(self, framelist, bias_image=None,
                dark_image=None, flat_image=None,
                **args):
        return self.nativeOperationOnImages(np.max,
                                            tr.tr('maximum'),
                                            framelist,
                                            bias_image,
                                            dark_image,
                                            flat_image,
                                            numpy_like=True,
                                            **args)

    def minimum(self, framelist, bias_image=None,
                dark_image=None, flat_image=None,
                **args):
        return self.nativeOperationOnImages(np.min,
                                            tr.tr('minimum'),
                                            framelist,
                                            bias_image,
                                            dark_image,
                                            flat_image,
                                            numpy_like=True,
                                            **args)

    def product(self, framelist, bias_image=None,
                dark_image=None, flat_image=None,
                **args):
        return self.nativeOperationOnImages(np.prod,
                                            tr.tr('product'),
                                            framelist,
                                            bias_image,
                                            dark_image,
                                            flat_image,
                                            numpy_like=True,
                                            **args)

    def operationOnImages(self, operation, name, framelist,
                          bias_image=None, dark_image=None,
                          flat_image=None, **args):

        if 'hotpixel_options' in args:
            hotp_args = args['hotpixel_options']
        else:
            hotp_args = None

        masters = self.generateMasters(bias_image,
                                       dark_image,
                                       flat_image,
                                       hotp_args)
        master_bias = masters[0]
        master_dark = masters[1]
        master_flat = masters[2]
        hot_pixels = masters[3]

        total = len(framelist)

        self.statusBar.showMessage(tr.tr('Registering images') +
                                   ', '+tr.tr('please wait...'))
        self.progress.reset()
        self.progress.setMaximum(4*(total-1))

        count = 0
        progress_count = 0
        original_shape = None
        tmpfilelist = []

        for img in framelist:
            if self.progressWasCanceled():
                return False

            self.progress.setValue(progress_count)
            progress_count += 1

            if img.isUsed():
                count += 1
            else:
                progress_count += 3
                continue

            r = img.getData(asarray=True, ftype=self.ftype)

            self.progress.setValue(progress_count)
            progress_count += 1

            if self.progressWasCanceled():
                return False

            if img.isRGB() and (r.shape[2] > 3):
                r = r[..., 0:3]

            r = self.calibrate(r,
                               master_bias,
                               master_dark,
                               master_flat,
                               hot_pixels,
                               **args)

            if original_shape is None:
                original_shape = r.shape

            if self.progressWasCanceled():
                return False
            self.progress.setValue(progress_count)
            progress_count += 1

            r = self.registerImages(img, r)

            if self.progressWasCanceled():
                return False
            self.progress.setValue(progress_count)
            progress_count += 1

            use_compression = bool(self.checked_compressed_temp == 2)
            tmpfile = utils.storeTmpArray(r, self.temp_path, use_compression)
            tmpfilelist.append(tmpfile)

        mdn = self._operationOnSubregions(operation,
                                          tmpfilelist,
                                          original_shape,
                                          name, 256, 256,
                                          **args)
        del tmpfilelist

        self.statusBar.clearMessage()

        return mdn

    def getNumberOfComponents(self):
        if self.isBayerUsed():
            return 3
        else:
            return self.currentDepht

    def doGenerateLightCurves(self):
        return self.generateLightCurves()

    def generateLightCurves(self, method=None, **args):
        del self._bas
        del self._drk
        del self._flt

        self._drk = None
        self._flt = None
        self._bas = None

        log.log(repr(self),
                'generating light curves, please wait...',
                level=logging.INFO)

        args = self.stack(skip_light=True, method=method)

        QtGui.QApplication.instance().processEvents()

        self.lock()

        if 'hotpixel_options' in args:
            hotp_args = args['hotpixel_options']
        else:
            hotp_args = args[4]

        masters = self.generateMasters(self._bas,
                                       self._drk,
                                       self._flt,
                                       hotp_args)
        master_bias = masters[0]
        master_dark = masters[1]
        master_flat = masters[2]
        hot_pixels = masters[3]

        nframes = len(self.framelist)
        nstars = len(self.framelist[0].stars)

        self.progress.show()
        self.progress.setMaximum(nframes*nstars - 1)

        count = 0
        img_idx = 0
        self.progress.show()

        # building a temporary dictionary to
        # hold photometric data
        adu_plots = {}
        for star in self.framelist[0].stars:
            st_name = str(star.getName())
            adu_plots[st_name] = {}
            for cn in range(self.getNumberOfComponents()):
                # NOTE:
                # adu_plt = lcurves.LightCurvePlot() may be used in conjunction
                # to adu_plt.append(...) in order to fill the plot. However,
                # we know that there will be one point for each frame and this
                # makes a total of len(self.framelist) points
                adu_plt = lcurves.LightCurvePlot(len(self.framelist))
                adu_plt.setName(st_name + "C"+str(cn))
                adu_plots[st_name][cn] = adu_plt

        pv_adu = guicontrols.LightCurveViewer()
        pv_adu.setAxisName('time', 'ADU')
        for plots in adu_plots.values():
            pv_adu.addPlots(tuple(plots.values()))
        self.showInMdiWindow(pv_adu, guicontrols.PLOTVIEWER, "ADU Lightcurves")

        allstars = {}

        for img in self.framelist:
            if not img.isUsed():
                log.log(repr(self),
                        'skipping image '+str(img.name),
                        level=logging.INFO)
                continue
            else:
                log.log(repr(self),
                        'using image '+str(img.name),
                        level=logging.INFO)

            self.progress.setValue(count)
            r = img.getData(asarray=True, ftype=self.ftype)
            r = self.calibrate(r,
                               master_bias,
                               master_dark,
                               master_flat,
                               hot_pixels,
                               debayerize_result=True)

            if self.use_image_time:
                frm_time = img.getProperty('UTCEPOCH')
            else:
                frm_time = img_idx

            for st in img.stars:
                count += 1
                st_name = str(st.getName())
                log.log(repr(self),
                        'computing adu value for star '+st_name,
                        level=logging.INFO)
                allstars[st_name] = (bool(st.reference), st.magnitude)

                if self.progressWasCanceled():
                    self.unlock()
                    self.progress.hide()
                    self.progress.reset()
                    return False

                try:
                    adu_val, adu_delta = lcurves.getInstMagnitudeADU(st, r)
                except Exception as exc:
                    exc_msg = str(exc) + "\n"
                    exc_msg += "Image: " + img.name + "\n"
                    exc_msg += "Star: " + st_name
                    utils.showErrorMsgBox(exc_msg, caller=self)

                    # removing curve points form this image
                    for plt_st_name in adu_plots.keys():
                        for plt_comp_name in adu_plots[st_name].keys():
                            pass
                            # adu_plots[plt_st_name][plt_comp_name][img_idx]

                    # break
                    # skipping image
                    # self.unlock()
                    # return False

                for cn in range(len(adu_val)):
                    val = (frm_time, adu_val[cn], 0, np.float(adu_delta[cn]))
                    adu_plots[st_name][cn][img_idx] = val
                    # NOTE:
                    # if adu_plt = lcurves.LightCurvePlot() was used above then
                    # you should replace the above line with:
                    #
                    # adu_plots[st_name][cn].append(*val)
                    #
                pv_adu.repaint()
            img_idx += 1

        # checking for reference stars:

        ref_stars = []
        var_stars = []

        for stname in allstars.keys():
            if allstars[stname][0]:
                # this is a reference star and we assume
                # ist brightness is fixed over the time
                ref_stars.append(stname)
            else:
                # this is a star for which we want to
                # compute the magnitude lightcurve
                var_stars.append(stname)

        instr_clr_corr = 0.1
        airmas_corr = 0.0  # TODO: improve airmass correction
        airmas_err = 0.0

        # NOTE: for now we assume the reference star is near the
        #       variable star so there is a null airmass correction

        LOGE10 = utils.LOGE10
        mag_plots = []
        for st_name in var_stars:
            subplots = adu_plots[st_name]
            pltncomp = len(subplots)
            if pltncomp > 1:
                # computing star color

                b_comp = 2
                v_comp = 1

                bb = subplots[b_comp]
                vv = subplots[v_comp]

                star_bv_index = -2.5 * np.log10(bb.getYData()/vv.getYData())

                # A simple error propagation (see below)

                bb_rer = (bb.getYError()/(bb.getYData()*LOGE10))**2
                vv_rer = (vv.getYError()/(vv.getYData()*LOGE10))**2

                star_bv_error2 = 6.25 * (bb_rer+vv_rer)
                star_bv_error2 = np.array(star_bv_error2)

            abs_mag_data = ([], [], [], [])
            for rf_name in ref_stars:
                # Here we compute absolute magnitude using each reference star
                refplots = adu_plots[rf_name]
                refncomp = len(refplots)
                ref_mag = allstars[rf_name][1]
                if refncomp > 1 and pltncomp > 1:
                    # Just an extra check as refplots subplots should have
                    # always the same size

                    rbb = refplots[b_comp]
                    rvv = refplots[v_comp]

                    rbv_frac = rbb.getYData()/rvv.getYData()
                    ref_bv_index = -2.5 * np.log10(rbv_frac)

                    # A simple error propagation (see below)

                    rbb_rer = (rbb.getYError()/(rbb.getYData()*LOGE10))**2
                    rvv_rer = (rvv.getYError()/(rvv.getYData()*LOGE10))**2
                    ref_bv_error2 = 6.25 * (rbb_rer+rvv_rer)

                    color_dif = instr_clr_corr * (star_bv_index-ref_bv_index)
                    color_err = instr_clr_corr
                    color_err *= np.sqrt(star_bv_error2 + ref_bv_error2)

                    # We shall use the total flux of the star, but we only
                    # have measures of the flux (measured as ADU) in different
                    # spectral bands, however we can approximate the tototal
                    # flux to the sum of each measures flux in all the
                    # available spectral bands.
                    #
                    # NOTE: We assume here that the corresponding values of
                    #       the flux in different bands are measured about at
                    #       the same time!

                    bol_str_ydat = sum(map(lcurves.LightCurvePlot.getYData,
                                           subplots.values()))
                    bol_str_xdat = sum(map(lcurves.LightCurvePlot.getXData,
                                           subplots.values()))/pltncomp
                    bol_str_yerr = sum(map(lcurves.LightCurvePlot.getYError,
                                           subplots.values()))
                    bol_str_xerr = sum(map(lcurves.LightCurvePlot.getXError,
                                           subplots.values()))/pltncomp

                    bol_ref_ydat = sum(map(lcurves.LightCurvePlot.getYData,
                                           refplots.values()))
                    bol_ref_yerr = sum(map(lcurves.LightCurvePlot.getYError,
                                           refplots.values()))
                    #
                    # A simple error propagation:
                    #
                    #  if V = f(A,B) then the error for V is
                    #
                    #  DV = sqrt(|DA*df(A,B)/dA|**2 + |DB*df(A,B)/dB|**2)
                    #
                    #  for this reason the, since bol_mag is

                    bol_mag = 2.5 * np.log10(bol_str_ydat/bol_ref_ydat)

                    #   A = bol_str_ydat DA = bol_str_yerr
                    #   B = bol_ref_ydat DB = bol_ref_yerr
                    #   f = log10
                    #
                    # the error on bol_mag is:
                    #
                    #  bol_err=2.5*sqrt(|DA*df(A,B)/dA|^2 + |DB*df(A,B)/dB|^2)
                    #  = 2.5*sqrt(|DA*1/[A*ln(10)]|^2 + |DB * -1/[B*ln(10)|^2)
                    #  = 2.5*sqrt(|DA/[A*ln(10)]|^2 + |DB/[B*ln(10)]|^2)

                    bol_erra = (bol_str_yerr/(bol_str_ydat*LOGE10))**2
                    bol_errb = (bol_ref_yerr/(bol_ref_ydat*LOGE10))**2
                    bol_err = 2.5 * np.sqrt(bol_erra + bol_errb)

                    # Transformation Equation
                    abs_mag = ref_mag - bol_mag - color_dif + airmas_corr
                    abs_mag_err = bol_err + color_err + airmas_err
                    abs_tme = bol_str_xdat
                    abs_tme_err = bol_str_xerr

                    abs_mag_data[0].append(abs_tme)
                    abs_mag_data[1].append(abs_mag)
                    abs_mag_data[2].append(abs_tme_err)
                    abs_mag_data[3].append(abs_mag_err)
                else:

                    bol_str_ydat = subplots[0].getYData()
                    bol_str_xdat = subplots[0].getXData()
                    bol_str_yerr = subplots[0].getYError()
                    bol_str_xerr = subplots[0].getXError()

                    bol_ref_ydat = refplots[0].getYData()
                    bol_ref_yerr = refplots[0].getYError()

                    bol_mag = 2.5 * np.log10(bol_str_ydat/bol_ref_ydat)

                    # A simple error propagation (see above)

                    bol_erra = (bol_str_yerr/(bol_str_ydat*LOGE10))**2
                    bol_errb = (bol_ref_yerr/(bol_ref_ydat*LOGE10))**2
                    bol_err = 2.5 * np.sqrt(bol_erra + bol_errb)

                    # NOTE: We have no color correction here because we have
                    #       only one spectral band

                    abs_mag = ref_mag - bol_mag + airmas_corr
                    abs_mag_err = bol_err + airmas_err
                    abs_tme = bol_str_xdat
                    abs_tme_err = bol_str_xerr

                    abs_mag_data[0].append(abs_tme)
                    abs_mag_data[1].append(abs_mag)
                    abs_mag_data[2].append(abs_tme_err)
                    abs_mag_data[3].append(abs_mag_err)

            # Finally we compute the mean value for the absolute magnitude...
            if ref_stars:
                mean_abs_tme = np.mean(abs_mag_data[0], 0)
                mean_abs_mag = np.mean(abs_mag_data[1], 0)
                mean_tme_err = np.mean(abs_mag_data[2], 0)
                mean_mag_err = np.mean(abs_mag_data[3], 0)
                del abs_mag_data

                # ...and build a LightCurvePlot
                plt = lcurves.LightCurvePlot()
                plt.setName(st_name)
                plt.setData(
                    mean_abs_tme, mean_abs_mag,
                    mean_tme_err, mean_mag_err)
                mag_plots.append(plt)

        # Show the mag plot only if there is nomething to plot!
        if ref_stars:
            pv_mag = guicontrols.LightCurveViewer(inverted_y=True)
            pv_mag.setAxisName('time', 'Mag')
            self.showInMdiWindow(pv_mag, guicontrols.PLOTVIEWER, "Mag Lightcurves")
            pv_mag.addPlots(mag_plots)
            pv_mag.repaint()

        self.unlock()
        self.progress.hide()
        self.progress.reset()

    def progressWasCanceled(self):
        QtGui.QApplication.instance().processEvents()
        if self.wasCanceled:
            self.wasCanceled = False
            self.progress.hide()
            self.progress.reset()
            self.cancelProgress.hide()
            self.statusBar.showMessage(tr.tr('Operation canceled by user'))
            self.unlock()
            return True
        else:
            return False

    def saveVideo(self):
        file_name = str(Qt.QFileDialog.getSaveFileName(
            self.wnd, tr.tr("Save the project"),
            os.path.join(self.current_dir, 'Untitled.avi'),
            "Video *.avi (*.avi);;All files (*.*)",
            None,
            utils.DIALOG_OPTIONS))

        if not file_name.strip():
            log.log(repr(self),
                    'no video file selected for output',
                    level=logging.ERROR)
            return False

        self.video_dlg.exec_()

        fps = self.video_dlg.getFps()
        fitlvl = self.video_dlg.getFitLevels()
        fcc_str = self.video_dlg.getCodecFCC()
        size, fzoom = self.video_dlg.getFrameSize(
            self.currentWidth,
            self.currentHeight)

        try:
            vw = cv2.VideoWriter(file_name,
                                 cv2.cv.CV_FOURCC(*fcc_str),
                                 fps,
                                 size)
        except Exception as exc:
            estr = str(exc)
            if ('doesn\'t support this codec' in estr):
                utils.showErrorMsgBox(
                    tr.tr("Cannot create the video file."),
                    tr.tr("Try to use a lower resolution and assure " +
                          "you\nhave the permissions to write the file."),
                    caller=self)

        log.log(repr(self),
                'writing video to: \"'+file_name+'\"',
                level=logging.INFO)

        log.log(repr(self),
                'FPS : ' + str(fps),
                level=logging.DEBUG)

        log.log(repr(self),
                'FOURCC : '+fcc_str,
                level=logging.DEBUG)

        log.log(repr(self),
                'FRAME SIZE : '+str(size),
                level=logging.DEBUG)

        if vw.isOpened():
            self.lock(False)
            self.progress.setMaximum(len(self.framelist))
            count = 0

            args = self.stack(skip_light=True)

            QtGui.QApplication.instance().processEvents()

            self.lock()

            masters = self.generateMasters(self._bas,
                                           self._drk,
                                           self._flt,
                                           args[4])
            master_bias = masters[0]
            master_dark = masters[1]
            master_flat = masters[2]
            hot_pixels = masters[3]


            self.statusBar.showMessage(tr.tr('Writing video, please wait...'))

            for frm in self.framelist:
                count += 1
                QtGui.QApplication.instance().processEvents()
                self.progress.setValue(count)

                if frm.isUsed():

                    log.log(repr(self),
                            'using frame '+str(frm.name),
                            level=logging.INFO)

                    log.log(repr(self),
                            'loading data...',
                            level=logging.DEBUG)

                    img = self.calibrate(
                        frm.getData(asarray=True, ftype=self.ftype),
                        master_bias,
                        master_dark,
                        master_flat,
                        hot_pixels,
                        debayerize_result=False)

                    img = self.debayerize(img)
                    img = utils.normToUint8(img, fitlvl).astype(np.uint8)

                    _rgb = (len(img.shape) == 3)

                    if self.video_dlg.useAligedImages():
                        img = self.registerImages(frm, img)

                    if self.video_dlg.useCustomSize():
                        log.log(repr(self),
                                'resizing image to ' + str(size),
                                level=logging.DEBUG)
                        if _rgb:
                            img = sp.ndimage.interpolation.zoom(
                                img,
                                (fzoom, fzoom, 1),
                                order=self.interpolation_order)
                        else:
                            img = sp.ndimage.interpolation.zoom(
                                img,
                                (fzoom, fzoom),
                                order=self.interpolation_order)
                    if _rgb:
                        cv2img = np.empty_like(img)
                        log.log(repr(self),
                                'converting to BRG format...',
                                level=logging.DEBUG)
                        cv2img[..., 0] = img[..., 2]
                        cv2img[..., 1] = img[..., 1]
                        cv2img[..., 2] = img[..., 0]
                    else:
                        log.log(repr(self),
                                'converting to BRG format...',
                                level=logging.DEBUG)

                        img = cmaps.getColormappedImage(img,
                                                        self.current_colormap,
                                                        fitlvl)

                        cv2img = np.empty((size[1], size[0], 3),
                                          dtype=np.uint8)
                        cv2img[..., 0] = img[2]
                        cv2img[..., 1] = img[1]
                        cv2img[..., 2] = img[0]

                    log.log(repr(self),
                            'pushing frame...',
                            level=logging.DEBUG)

                    vw.write(cv2img)

                    del cv2img

                else:
                    log.log(repr(self),
                            'skipping frame '+str(frm.name),
                            level=logging.INFO)

            vw.release()
            self.unlock()
            self.statusBar.showMessage(tr.tr('DONE'))
            log.log(repr(self),
                    'DONE',
                    level=logging.INFO)

        else:
            utils.showErrorMsgBox('Cannot open destination file',
                                  caller=self)
