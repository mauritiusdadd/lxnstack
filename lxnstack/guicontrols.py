# lxnstack is a program to align and stack atronomical images
# Copyright (C) 2013-2015  Maurizio D'Addona <mauritiusdadd@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import math
import os
import paths
import logging

from PyQt4 import Qt, QtCore, QtGui

import translation as tr
import plotting
import utils
import colormaps as cmaps
import mappedimage
import numpy as np
import log

IMAGEVIEWER = "imageviewer"
DIFFERENCEVIEWER = "diffviewer"
PLOTVIEWER = "plotviewer"

READY = 0x0001
UPDATED = 0x0002
NEEDS_IMAGE_UPDATE = 0x0004
NEEDS_FEATURES_UPDATE = 0x0004


class SplashScreen(Qt.QObject):

    def __init__(self):

        Qt.QObject.__init__(self)

        splashfile = os.path.join(paths.DATA_PATH, "splashscreen.jpg")
        self._pxm = Qt.QPixmap(splashfile)
        self._qss = Qt.QSplashScreen(self._pxm,
                                     QtCore.Qt.WindowStaysOnTopHint |
                                     QtCore.Qt.X11BypassWindowManagerHint)

        self._msg = ''
        self._maxv = 100.0
        self._minv = 0.0
        self._cval = 0.0

        self._qss.drawContents = self._drawContents

        self._qss.show()

        self.processEvents()

    def close(self):
        self.update()
        self._qss.close()

    def setMaximum(self, val):
        self._maxv = val
        self.update()

    def setMinimum(self, val):
        self._minv = val
        self.update()

    def setValue(self, val):
        for i in np.arange(self._cval, val, (self._maxv - self._minv) / 100.0):
            self._cval = i
            self.update()

    def maximum(self):
        return self._maxv

    def minimum(self):
        return self._minv

    def value(self):
        return self._cval

    def message(self):
        return self._msg

    def showMessage(self, msg):
        self._msg = msg
        self.update()

    def update(self):
        self._qss.update()
        self.processEvents()

    def _drawContents(self, painter):

        view_port = painter.viewport()

        w = view_port.right()
        h = view_port.bottom()

        painter.setPen(Qt.QColor(55, 55, 55, 255))
        painter.setBrush(Qt.QColor(0, 0, 0, 255))
        painter.drawRect(10, h-25, w-20, 15)

        redlg = Qt.QLinearGradient(0, 0, w, 0)
        redlg.setColorAt(0, Qt.QColor(10, 10, 155))
        redlg.setColorAt(0.8, Qt.QColor(10, 10, 255))

        alg = Qt.QLinearGradient(0, h-25, 0, h)
        alg.setColorAt(0, Qt.QColor(0, 0, 0, 150))
        alg.setColorAt(0.5, Qt.QColor(0, 0, 0, 0))

        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(redlg)
        painter.drawRect(11, h-24, (w-21) * self._cval / self._maxv, 14)

        painter.setBrush(alg)
        painter.drawRect(11, h-24, (w-21) * self._cval / self._maxv, 14)

        painter.setPen(QtCore.Qt.white)
        rect = Qt.QRectF(10, h-23, w-20, 15)
        painter.drawText(rect, QtCore.Qt.AlignCenter, str(self._msg))

        return QtGui.QSplashScreen.drawContents(self._qss, painter)

    def finish(self, qwid):
        self._qss.finish(qwid)

    def processEvents(self):
        qapp = QtGui.QApplication.instance()
        if qapp is not None:
            qapp.processEvents()


class TaggedLineEdit(QtGui.QLineEdit):

    def __init__(self):
        QtGui.QLineEdit.__init__(self)
        self.textcolor = QtGui.QColor(67, 172, 232)
        self.boxcolor = QtGui.QColor(175, 210, 255)
        self.setReadOnly(True)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        surface_window = painter.window()
        font = self.font()
        font.setBold(True)
        # pal = self.palette()
        opt = QtGui.QStyleOptionFrame()
        style = self.style()

        opt.init(self)
        painter.setFont(font)
        style.drawPrimitive(
            QtGui.QStyle.PE_FrameLineEdit,
            opt,
            painter,
            self)

        painter.setClipRect(surface_window)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRect(surface_window)

        painter.setPen(self.textcolor)
        painter.setBrush(self.boxcolor)
        fm = painter.fontMetrics()

        spacing = fm.width(' ')
        xoff = spacing
        for element in str(self.text()).split(','):
            if not element.strip():
                continue
            etxt = "+"+element
            w = fm.width(etxt)+2*spacing
            rect = QtCore.QRectF(xoff, 3, w, surface_window.height()-6)
            painter.drawRect(rect)
            painter.drawText(rect,
                             QtCore.Qt.AlignCenter |
                             QtCore.Qt.AlignVCenter,
                             etxt)
            xoff += w+3*spacing


class CCBStyledItemDelegate (QtGui.QStyledItemDelegate):

    def paint(self, painter, options, index):
        newopts = QtGui.QStyleOptionViewItem(options)
        # Disabling decoration for selected items
        # and for items under mouse cursor
        newopts.showDecorationSelected = False
        newopts.state &= ~QtGui.QStyle.State_HasFocus
        newopts.state &= ~QtGui.QStyle.State_MouseOver
        # proced with object drawing
        QtGui.QStyledItemDelegate.paint(self, painter, newopts, index)


class ComboCheckBox(QtGui.QComboBox):

    itemChanged = QtCore.pyqtSignal(QtGui.QStandardItem)
    checkStateChanged = QtCore.pyqtSignal()

    def __init__(self, *arg, **args):
        QtGui.QComboBox.__init__(self, *arg, **args)
        model = QtGui.QStandardItemModel(0, 1)
        self.setModel(model)
        self.setItemDelegate(CCBStyledItemDelegate(self))
        self.setMinimumHeight(30)
        self.setLineEdit(TaggedLineEdit())
        self.setEditable(True)
        self.setInsertPolicy(QtGui.QComboBox.NoInsert)
        self.setEditText("")

        self.setSizePolicy(
            QtGui.QSizePolicy(QtGui.QSizePolicy.Minimum,
                              QtGui.QSizePolicy.Minimum))

        model.itemChanged.connect(self.itemChanged.emit)
        model.itemChanged.connect(self._emitCheckStateChanged)
        self.checkStateChanged.connect(self._updateEditText)
        self.editTextChanged.connect(self._test)

    def _test(self, txt):
        self._updateEditText()

    def _updateEditText(self):
        txt = ""
        model = self.model()
        total = model.rowCount()*model.columnCount()
        count = 0
        for row in xrange(model.rowCount()):
            for col in xrange(model.columnCount()):
                item = model.item(row, col)
                if item.checkState():
                    count += 1
                    txt += item.text() + ", "
        if count == total:
            txt = tr.tr('All')
        elif not txt:
            txt = tr.tr('None')
        self.setEditText(txt)

    def addItem(self, *arg, **args):
        """
            arg:
                see QtGui.QStandardItem for

            args:
                checked (bool)
        """
        item = QtGui.QStandardItem(*arg)

        item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
        item.setData(QtCore.Qt.Unchecked, QtCore.Qt.CheckStateRole)

        if "checked" in args and args["checked"]:
            item.setCheckState(2)
        else:
            item.setCheckState(0)

        self.model().appendRow(item)
        self._updateEditText()
        return item

    def addItems(self, strlist):
        for txt in strlist:
            self.addItem(txt)

    def _emitCheckStateChanged(self):
        self.checkStateChanged.emit()


class ToolComboBox(Qt.QFrame):

    _selector = QtGui.QComboBox

    def __init__(self, title="", tooltip="", useframe=True):

        Qt.QFrame.__init__(self)

        self.setFrameStyle(Qt.QFrame.Plain)
        self.setToolTip(tooltip)
        self._label = Qt.QLabel(title)
        self._selector = self._selector()

        vLayout = Qt.QHBoxLayout(self)
        vLayout.addWidget(self._label)
        vLayout.addWidget(self._selector)

        self.setLabel = self._label.setText
        self.addItem = self._selector.addItem
        self.addItems = self._selector.addItems
        self.count = self._selector.count
        self.currentIndexChanged = self._selector.currentIndexChanged
        self.currentIndex = self._selector.currentIndex
        self.setCurrentIndex = self._selector.setCurrentIndex
        self.currentText = self._selector.currentText
        self.duplicatesEnabled = self._selector.duplicatesEnabled
        self.setFrame = self._selector.setFrame
        self.hasFrame = self._selector.hasFrame
        self.clear = self._selector.clear

        self.setFrame(useframe)


class ToolComboCheckBox(ToolComboBox):

    _selector = ComboCheckBox

    def __init__(self, title="", tooltip="", useframe=True):
        ToolComboBox.__init__(self, title, tooltip, useframe)
        self._selector.setMinimumWidth(200)

        self.itemChanged = self._selector.itemChanged


class ImageViewer(QtGui.QWidget):

    # titleChanged = QtCore.pyqtSignal(str)

    def __init__(self, infolabel=None):

        QtGui.QWidget.__init__(self)

        self.zoom = 1
        self.min_zoom = 0
        self.actual_zoom = 1
        self.exposure = 0
        self.zoom_enabled = False
        self.zoom_fit = False
        self.mapped_image = mappedimage.MappedImage(name='image')
        self.fit_levels = False
        self.panning = False
        self.feature_moveing = False
        self.selected_feature = None
        self.colorbarmap = mappedimage.MappedImage(name='colorbar')
        self.user_cursor = QtCore.Qt.OpenHandCursor
        self.levels_range = [0, 100]
        self.image_features = []
        self.statusLabelMousePos = infolabel

        toolbar = Qt.QToolBar('ImageViewerToolBar')

        # ToolBar actions
        save_action = QtGui.QAction(
            utils.getQIcon("save-image"),
            tr.tr('Save the displayed image to a file'),
            self)

        action_edit_levels = QtGui.QAction(
            utils.getQIcon("edit-levels"),
            tr.tr('Edit input levels'),
            self)

        action_edit_levels.setCheckable(True)

        # colormap controls
        self.colormap_selector = ToolComboBox(
            tr.tr("colormap:"),
            tooltip=tr.tr("Image color-map"))

        data = np.meshgrid(np.arange(64), np.arange(64))[0]

        keys = cmaps.COLORMAPS.keys()
        keys.sort()

        for ccmap in keys:
            cmap = cmaps.COLORMAPS[ccmap]
            icon = Qt.QPixmap.fromImage(
                mappedimage.arrayToQImage(data, cmap=cmap, fit_levels=True))
            self.colormap_selector.addItem(QtGui.QIcon(icon), cmap.name)

        self.colormap_selector.setEnabled(True)

        # zoom controls
        self.zoomCheckBox = QtGui.QCheckBox(tr.tr("zoom: none"))
        self.zoomSlider = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.zoomDoubleSpinBox = QtGui.QDoubleSpinBox()

        # image viewer controls
        self.imageLabel = QtGui.QLabel()
        self.scrollArea = QtGui.QScrollArea()
        self.viewHScrollBar = self.scrollArea.horizontalScrollBar()
        self.viewVScrollBar = self.scrollArea.verticalScrollBar()

        # colorbar controls
        self.colorBar = QtGui.QLabel()
        self.fitMinMaxCheckBox = QtGui.QCheckBox(tr.tr("contrast: none"))
        self.minLevelDoubleSpinBox = QtGui.QDoubleSpinBox()
        self.maxLevelDoubleSpinBox = QtGui.QDoubleSpinBox()

        self.colorBar.current_val = None
        self.colorBar.max_val = 1.0
        self.colorBar.min_val = 0.0
        self.colorBar._is_rgb = False

        self.zoomSlider.setMinimum(0)
        self.zoomSlider.setMaximum(1000)
        self.zoomSlider.setSingleStep(1)

        self.zoomDoubleSpinBox.setDecimals(3)
        self.zoomDoubleSpinBox.setMinimum(0.01)
        self.zoomDoubleSpinBox.setMaximum(10.0)
        self.zoomSlider.setSingleStep(0.05)

        self.imageLabel.setMouseTracking(True)

        self.scrollArea.setMouseTracking(False)
        self.scrollArea.setFrameShape(QtGui.QFrame.StyledPanel)
        self.scrollArea.setFrameShadow(QtGui.QFrame.Sunken)
        self.scrollArea.setLineWidth(1)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setWidget(self.imageLabel)
        self.scrollArea.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.scrollArea.setFrameShape(QtGui.QFrame.StyledPanel)
        self.scrollArea.setFrameShadow(QtGui.QFrame.Sunken)

        self.scrollArea.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarAsNeeded)

        self.scrollArea.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAsNeeded)

        self.scrollArea.setSizePolicy(
            QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding,
                              QtGui.QSizePolicy.Expanding))

        self.colorBar.setSizePolicy(
            QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding,
                              QtGui.QSizePolicy.Fixed))

        self.colorBar.setMinimumSize(QtCore.QSize(0, 25))
        self.colorBar.setFrameShape(QtGui.QFrame.StyledPanel)
        self.colorBar.setFrameShadow(QtGui.QFrame.Sunken)

        self.fitMinMaxCheckBox.setTristate(True)

        self.minLevelDoubleSpinBox.setMinimum(0.0)
        self.minLevelDoubleSpinBox.setMaximum(100.0)

        self.maxLevelDoubleSpinBox.setMinimum(0.0)
        self.maxLevelDoubleSpinBox.setMaximum(100.0)

        mainlayout = QtGui.QVBoxLayout()
        self.viewlayout = QtGui.QHBoxLayout()
        cbarlayout = QtGui.QHBoxLayout()

        self.setLayout(mainlayout)

        cbarlayout.addWidget(self.fitMinMaxCheckBox)
        cbarlayout.addWidget(self.minLevelDoubleSpinBox)
        cbarlayout.addWidget(self.colorBar)
        cbarlayout.addWidget(self.maxLevelDoubleSpinBox)

        toolbar.addAction(save_action)
        toolbar.addAction(action_edit_levels)
        toolbar.addWidget(self.colormap_selector)
        toolbar.addWidget(self.zoomCheckBox)
        toolbar.addWidget(self.zoomSlider)
        toolbar.addWidget(self.zoomDoubleSpinBox)

        self.viewlayout.addWidget(self.scrollArea)
        self.viewlayout.addWidget(self.mapped_image.getLevelsDialog())
        self.mapped_image.getLevelsDialog().hide()

        mainlayout.addWidget(toolbar)
        mainlayout.addLayout(self.viewlayout)
        mainlayout.addLayout(cbarlayout)

        # mousemove callback
        self.imageLabel.mouseMoveEvent = self.imageLabelMouseMoveEvent
        self.imageLabel.mousePressEvent = self.imageLabelMousePressEvent
        self.imageLabel.mouseReleaseEvent = self.imageLabelMouseReleaseEvent

        # mouse wheel scroll callback
        self.scrollArea.wheelEvent = self.scrollAreaWheelEvent

        # resize callback
        self.scrollArea.resizeEvent = self.scrollAreaResizeEvent

        # paint callback
        self.imageLabel.paintEvent = self.imageLabelPaintEvent

        # paint callback for colorBar
        self.colorBar.paintEvent = self.colorBarPaintEvent

        save_action.triggered.connect(self.doSaveImage)
        action_edit_levels.triggered.connect(self.doEditLevels)

        self.mapped_image.remapped.connect(self.updateImage)
        self.zoomCheckBox.stateChanged.connect(self.setZoomMode)
        self.zoomSlider.valueChanged.connect(self.signalSliderZoom)
        self.zoomDoubleSpinBox.valueChanged.connect(self.signalSpinZoom)
        self.fitMinMaxCheckBox.stateChanged.connect(self.setLevelsFitMode)
        self.minLevelDoubleSpinBox.valueChanged.connect(self.setMinLevel)
        self.maxLevelDoubleSpinBox.valueChanged.connect(self.setMaxLevel)
        self.colormap_selector.currentIndexChanged.connect(self.setColorMapID)

        self.setZoomMode(1, True)
        self.setOutputLevelsRange((0, 100))
        self.setLevelsFitMode(0)

    def setFeatures(self, flist):
        self.image_features = flist

    def doSaveImage(self):
        if self.mapped_image is not None:
            frm = utils.Frame()
            frm.saveData(data=self.mapped_image.getMappedData())

    def setColorMapID(self, cmapid):
        self.setColorMap(cmaps.COLORMAPS[cmapid])

    def setColorMap(self, cmap):
        log.log(repr(self), "Setting new colormap", level=logging.DEBUG)
        if self.mapped_image is not None:
            self.mapped_image.setColormap(cmap, update=False)
            self.generateScaleMaps(remap=False)
            self.mapped_image.remap()

    def getColorMap(self):
        return self.mapped_image.getColormap()

    def updateColorMap(self, val):
        self.colormap_selector.setCurrentIndex(val)

    def generateScaleMaps(self, remap=True):

        if self.mapped_image is None:
            return

        ncomponents = self.mapped_image.componentsCount()

        if ncomponents < 1:
            return

        elif ncomponents == 1:
            log.log(repr(self),
                    "Generating ColorBar scalemaps...",
                    level=logging.DEBUG)
            h_mul = int(self.colorBar.height()-8)
            data1 = np.arange(0, self.colorBar.width())
            data1 = data1*255.0 / self.colorBar.width()
            data2 = np.array([data1]*h_mul)
            data3 = data2

        else:
            log.log(repr(self),
                    "Generating ColorBar RGB scalemaps...",
                    level=logging.DEBUG)
            h_mul = int((self.colorBar.height()-8) / float(ncomponents))
            data1 = np.arange(0, self.colorBar.width())
            data1 = data1*255.0 / self.colorBar.width()
            data2 = np.array([data1]*h_mul)
            hh = len(data2)
            data3 = np.zeros((ncomponents*hh, len(data1), ncomponents))

            for i in xrange(ncomponents):
                data3[i*hh:(i+1)*hh, 0:, i] = data2

        if isinstance(self.colorbarmap, mappedimage.MappedImage):
            self.colorbarmap.setColormap(self.mapped_image.getColormap(),
                                         update=False)
            self.colorbarmap.setOutputLevels(lrange=self.levels_range,
                                             lfitting=self.fit_levels,
                                             update=False)
            self.colorbarmap.setData(data3, update=remap)
        else:
            self.colorbarmap = mappedimage.MappedImage(
                data3,
                self.mapped_image.getColormap(),
                fit_levels=self.fit_levels,
                levels_range=self.levels_range,
                name='colorbar',
                update=remap)

    # resizeEvent callback
    def scrollAreaResizeEvent(self, event):
        if self.zoom_fit:
            self.updateImage()
        self.generateScaleMaps()
        return QtGui.QScrollArea.resizeEvent(self.scrollArea, event)

    # mouseMoveEvent callback
    def imageLabelMouseMoveEvent(self, event):
        mx = event.x()
        my = event.y()
        x = utils.Int(mx/self.actual_zoom)
        y = utils.Int(my/self.actual_zoom)

        if (self.mapped_image is not None):
            if self.mapped_image.getOriginalData() is not None:
                imshape = self.mapped_image.getOriginalData().shape
                ymax = imshape[0]
                xmax = imshape[1]
                if ((y >= 0) and (y < ymax) and (x >= 0) and (x < xmax)):
                    # the mouse cursor is over the image area
                    pix_val = self.mapped_image.getOriginalData()[y, x]
                    self.current_pixel = (x, y)
                    try:
                        self.colorBar.current_val = tuple(pix_val)
                    except:
                        try:
                            self.colorBar.current_val = (int(pix_val),)
                        except:
                            comp_count = self.mapped_image.componentsCount()
                            self.colorBar.current_val = (0,)*comp_count
                    self.colorBar.repaint()
            else:
                pix_val = None

        if self.panning:
            sx = mx-self.movement_start[0]
            sy = my-self.movement_start[1]

            self.viewHScrollBar.setValue(self.viewHScrollBar.value()-sx)
            self.viewVScrollBar.setValue(self.viewVScrollBar.value()-sy)

        elif self.feature_moveing:
            self.selected_feature.move(x, y)
            self.repaint()
        else:
            for feature in self.image_features:
                if ((x-feature.x)**2 + (y-feature.y)**2) < feature.r**2:
                    self.scrollArea.setCursor(QtCore.Qt.SizeAllCursor)
                    self.imageLabel.setCursor(QtCore.Qt.SizeAllCursor)
                    feature.mouse_over = True
                    self.selected_feature = feature
                    break
                else:
                    self.imageLabel.setCursor(self.user_cursor)
                    feature.mouse_over = False
                    self.selected_feature = None
            self.repaint()
        return QtGui.QLabel.mouseMoveEvent(self.imageLabel, event)

    def scrollAreaWheelEvent(self, event):
        if self.zoom_enabled:
            delta = np.sign(event.delta())*math.log10(self.zoom+1)/2.5
            mx = event.x()
            my = event.y()
            cx = self.scrollArea.width()/2.0
            cy = self.scrollArea.height()/2.0
            sx = (cx - mx)/2
            sy = (cy - my)/2
            self.viewHScrollBar.setValue(self.viewHScrollBar.value()-sx)
            self.viewVScrollBar.setValue(self.viewVScrollBar.value()-sy)

            self.setZoom(self.zoom+delta)

        return Qt.QWheelEvent.accept(event)

    def imageLabelMousePressEvent(self, event):

        btn = event.button()
        if btn == 1:
            self.movement_start = (event.x(), event.y())
            if self.selected_feature is None:
                self.scrollArea.setCursor(QtCore.Qt.ClosedHandCursor)
                self.imageLabel.setCursor(QtCore.Qt.ClosedHandCursor)
                self.panning = True
                self.feature_moveing = False
            else:
                self.panning = False
                self.scrollArea.setCursor(QtCore.Qt.BlankCursor)
                self.imageLabel.setCursor(QtCore.Qt.BlankCursor)
                self.feature_moveing = True
                self.selected_feature.mouse_grabbed = True

        return QtGui.QLabel.mousePressEvent(self.imageLabel, event)

    def imageLabelMouseReleaseEvent(self, event):

        btn = event.button()
        if btn == 1:
            self.panning = False
            self.feature_moveing = False
            self.scrollArea.setCursor(self.user_cursor)
            self.imageLabel.setCursor(self.user_cursor)

            if not (self.selected_feature is None):
                self.selected_feature.mouse_grabbed = False

        return QtGui.QLabel.mouseReleaseEvent(self.imageLabel, event)

    # paintEvent callback for imageLabel
    def imageLabelPaintEvent(self, obj):

        painter = Qt.QPainter(self.imageLabel)

        if self.mapped_image is not None:
            qimg = self.mapped_image.getQImage()
            if qimg is not None:
                painter.scale(self.actual_zoom, self.actual_zoom)
                painter.drawImage(0, 0, self.mapped_image.getQImage())

        for feature in self.image_features:
            feature.draw(painter)

        del painter
        return QtGui.QLabel.paintEvent(self.imageLabel, obj)

    # paintEvent callback for colorBar
    def colorBarPaintEvent(self, obj):

        cb = self.colorBar
        if self.mapped_image is None:
            return QtGui.QLabel.paintEvent(cb, obj)

        if self.colorBar.current_val is not None:
            painter = Qt.QPainter(self.colorBar)

            _gpo = 2  # geometric corrections
            _gno = 5  # geometric corrections
            _gpv = 4  # geometric corrections

            dw = painter.device().width() - _gno
            dh = painter.device().height() - _gpv*2

            devicerect = QtCore.QRect(_gpo, _gpv, dw, dh)

            fnt_size = 10
            painter.setFont(Qt.QFont("Arial", fnt_size))
            y = (cb.height() + fnt_size/2)/2 + 2
            max_txt = str(cb.max_val)
            txt_x = cb.width() - (fnt_size-2)*len(max_txt)
            txt_y = y

            if self.statusLabelMousePos is not None:
                try:
                    self.statusLabelMousePos.setText(
                        'position=' + str(self.current_pixel) +
                        ' value=' + str(cb.current_val))
                except:
                    pass

            qimg = self.colorbarmap.getQImage()
            if qimg is not None:
                painter.drawImage(devicerect, qimg)

            ncomp = len(cb.current_val)
            hh = dh/ncomp

            painter.setCompositionMode(22)

            for i in xrange(ncomp):
                try:
                    v1 = float(cb.current_val[i]-cb.min_val)
                    v2 = float(cb.max_val-cb.min_val)
                    x = int((v1/v2) * (cb.width()-_gno)) + _gpo
                except Exception:
                    x = -1
                painter.setPen(QtCore.Qt.white)
                painter.drawLine(x, _gpv + i*hh, x, _gpv + (i+1)*hh)

            painter.setCompositionMode(0)
            painter.setPen(QtCore.Qt.white)
            painter.drawText(fnt_size-4, y, str(cb.min_val))
            painter.setPen(QtCore.Qt.black)
            painter.drawText(txt_x, txt_y, max_txt)

            del painter

        return QtGui.QLabel.paintEvent(cb, obj)

    def setZoomMode(self, val, check=False):

        if check:
            self.zoomCheckBox.setCheckState(val)

        if val is 0:
            self.zoomCheckBox.setText(tr.tr('zoom: none'))
            self.zoomSlider.setEnabled(False)
            self.zoomDoubleSpinBox.setEnabled(False)
            self.zoom_enabled = False
            self.zoom_fit = False
        elif val is 1:
            self.zoomCheckBox.setText(tr.tr('zoom: fit'))
            self.zoomSlider.setEnabled(False)
            self.zoomDoubleSpinBox.setEnabled(False)
            self.zoom_enabled = False
            self.zoom_fit = True
        else:
            self.zoomCheckBox.setText(tr.tr('zoom: full'))
            self.zoomSlider.setEnabled(True)
            self.zoomDoubleSpinBox.setEnabled(True)
            self.zoom_enabled = True
            self.zoom_fit = False
        self.updateImage()

    def setZoom(self, zoom):

        if zoom <= self.zoomDoubleSpinBox.maximum():
            self.zoom = zoom
        else:
            self.zoom = self.zoomDoubleSpinBox.maximum()

        self.zoomDoubleSpinBox.setValue(self.zoom)
        self.zoomSlider.setValue(utils.Int(self.zoom*100))

    def signalSliderZoom(self, value, update=False):
        self.zoom = value/100.0
        vp = self.getViewport()
        self.zoomDoubleSpinBox.setValue(self.zoom)
        if update:
            self.updateImage()

        self.setViewport(vp)

    def signalSpinZoom(self, value, update=True):
        self.zoom = value
        vp = self.getViewport()
        self.zoomSlider.setValue(utils.Int(self.zoom*100))
        if update:
            self.updateImage()
        self.setViewport(vp)

    def getViewport(self):
        try:
            hs_val = float(self.viewHScrollBar.value())
            hs_max = float(self.viewHScrollBar.maximum())
            x = hs_val/hs_max
        except ZeroDivisionError:
            x = 0.5
        try:
            vs_val = float(self.viewVScrollBar.value())
            vs_max = float(self.viewVScrollBar.maximum())
            y = vs_val/vs_max
        except ZeroDivisionError:
            y = 0.5

        return (x, y)

    def setViewport(self, viewPoint):
        hs_max = self.viewHScrollBar.maximum()
        vs_max = self.viewVScrollBar.maximum()
        self.viewHScrollBar.setValue(viewPoint[0]*hs_max)
        self.viewVScrollBar.setValue(viewPoint[1]*vs_max)

    def showImage(self, image):
        if isinstance(image, mappedimage.MappedImage):
            log.log(repr(self),
                    "Displaying new mappedimage",
                    level=logging.DEBUG)
            del self.mapped_image
            self.mapped_image.remapped.disconnect(self.updateImage)
            self.mapped_image.mappingChanged.disconnect(self.updateImage)
            self.viewlayout.removeWidget(self.mapped_image.getLevelsDialog())
            self.mapped_image = image
            self.viewlayout.addWidget(self.mapped_image.getLevelsDialog())
            self.mapped_image.getLevelsDialog().hide()
            self.mapped_image.mappingChanged.disconnect(self.updateImage)
            self.mapped_image.remapped.connect(self.updateImage)
            self.updateImage()
        else:
            log.log(repr(self),
                    "Displaying new image",
                    level=logging.DEBUG)
            self.mapped_image.setData(image)

    def clearImage(self):
        self.mapped_image.setData(None)
        self.imageLabel.setPixmap(Qt.QPixmap())

    def updateImage(self, paint=True, overridden_image=None):

        log.log(repr(self),
                "Updating the displayed image",
                level=logging.DEBUG)

        if overridden_image is not None:
            if isinstance(overridden_image, mappedimage.MappedImage):
                current_image = overridden_image
            else:
                return False
        elif self.mapped_image is not None:
            current_image = self.mapped_image
        else:
            return False

        qimg = current_image.getQImage()
        if qimg is None:
            return False

        imh = qimg.height()
        imw = qimg.width()
        if imw*imh <= 0:
            return False

        self.colorbarmap.setCurve(
            *current_image.getCurve(),
            update=False)

        self.colorbarmap.setMWBCorrectionFactors(
            *current_image.getMWBCorrectionFactors(),
            update=False)

        self.colorbarmap.setOutputLevels(
            lrange=self.levels_range,
            lfitting=self.fit_levels,
            update=False)

        self.colorbarmap.setMapping(
            *current_image.getMapping(),
            update=False)

        colormap_comp_count = self.colorbarmap.getNumberOfComponents()
        curr_image_comp_count = current_image.getNumberOfComponents()
        components_match = colormap_comp_count == curr_image_comp_count

        if (self.colorbarmap.getQImage() is None or not components_match):
            self.generateScaleMaps()
        else:
            self.colorbarmap.remap()

        try:
            pix_x = self.current_pixel[0]
            pix_y = self.current_pixel[1]
            pix_val = current_image.getOriginalData()[pix_y, pix_x]
            try:
                self.colorBar.current_val = tuple(pix_val)
            except:
                try:
                    self.colorBar.current_val = (int(pix_val),)
                except:
                    self.colorBar.current_val = (0,)*curr_image_comp_count
            self.colorBar.repaint()
        except Exception:
            self.current_pixel = (0, 0)

        if self.zoom_enabled:
            self.actual_zoom = self.zoom
        elif self.zoom_fit:
            self.actual_zoom = min(float(self.scrollArea.width()-10)/imw,
                                   float(self.scrollArea.height()-10)/imh)
            self.zoomDoubleSpinBox.setValue(self.zoom)
        else:
            self.actual_zoom = 1

        if paint:
            imh += 1
            imw += 1
            self.imageLabel.setMaximumSize(imw*self.actual_zoom,
                                           imh*self.actual_zoom)
            self.imageLabel.setMinimumSize(imw*self.actual_zoom,
                                           imh*self.actual_zoom)
            self.imageLabel.resize(imw*self.actual_zoom,
                                   imh*self.actual_zoom)
            self.imageLabel.update()

            if current_image._original_data is not None:
                self.colorBar.max_val = current_image._original_data.max()
                self.colorBar.min_val = current_image._original_data.min()

                if (self.colorBar.max_val <= 1) or self.fit_levels:
                    pass
                elif self.colorBar.max_val <= 255:
                    self.colorBar.max_val *= 255.0/self.colorBar.max_val
                elif self.colorBar.max_val <= 65536:
                    self.colorBar.max_val *= 65536.0/self.colorBar.max_val

                if self.fit_levels:
                    pass
                elif self.colorBar.min_val > 0:
                    self.colorBar.min_val *= 0

                if not self.colorBar.isVisible():
                    self.colorBar.show()
            else:
                self.colorBar.max_val = 1
                self.colorBar.max_val = 0
                if self.colorBar.isVisible():
                    self.colorBar.hide()

            # this shuold avoid division by zero
            if self.colorBar.max_val == self.colorBar.min_val:
                self.colorBar.max_val = self.colorBar.max_val+1
                self.colorBar.min_val = self.colorBar.min_val-1

        return True

    def setOutputLevelsRange(self, lrange):
        self.minLevelDoubleSpinBox.setValue(np.min(lrange))
        self.maxLevelDoubleSpinBox.setValue(np.max(lrange))

    def setMinLevel(self, val):
        self.levels_range[0] = val
        if val <= self.levels_range[1]-1:
            self.setLevelsFitMode(self.fit_levels)
        else:
            self.maxLevelDoubleSpinBox.setValue(val+1)

    def setMaxLevel(self, val):
        self.levels_range[1] = val
        if val >= self.levels_range[0]+1:
            self.setLevelsFitMode(self.fit_levels)
        else:
            self.minLevelDoubleSpinBox.setValue(val-1)

    def forceDisplayLevelsFitMode(self, state):
        self.setLevelsFitMode(state)
        self.fitMinMaxCheckBox.hide()

    def setLevelsFitMode(self, state):

        log.log(repr(self),
                "Updating output levels",
                level=logging.DEBUG)

        if state == 0:
            self.minLevelDoubleSpinBox.hide()
            self.maxLevelDoubleSpinBox.hide()
            self.fitMinMaxCheckBox.setText(tr.tr('contrast')+': ' +
                                           tr.tr('none'))
        elif state == 1:
            self.minLevelDoubleSpinBox.hide()
            self.maxLevelDoubleSpinBox.hide()
            self.fitMinMaxCheckBox.setText(tr.tr('contrast')+': ' +
                                           tr.tr('full'))
        else:
            self.minLevelDoubleSpinBox.show()
            self.maxLevelDoubleSpinBox.show()
            self.fitMinMaxCheckBox.setText(tr.tr('contrast')+': ' +
                                           tr.tr('yes'))
        self.fit_levels = state

        Qt.QApplication.instance().processEvents()

        if self.mapped_image is not None:
            self.setOutputLevelsRange(self.levels_range)
            self.mapped_image.setOutputLevels(self.levels_range,
                                              self.fit_levels,
                                              update=True)
            self.updateImage()
        else:
            self.generateScaleMaps()

        self.colorBar.repaint()

    def doEditLevels(self, clicked):
        return self.mapped_image.editLevels(clicked)


class DifferenceViewer(ImageViewer):

    def __init__(self, reference=None):

        ImageViewer.__init__(self)
        self.offset = (0, 0, 0)
        self.ref_shift = (0, 0, 0)
        self.reference_image = mappedimage.MappedImage(reference)

    def setOffset(self, dx, dy, theta):
        self.offset = (dx, dy, theta)
        self.repaint()

    def setRefShift(self, dx, dy, theta):
        self.ref_shift = (dx, dy, theta)
        self.repaint()

    def setRefImage(self, image):
        if isinstance(image, mappedimage.MappedImage):
            del self.mapped_image
            self.reference_image = image
        else:
            self.reference_image.setData(image)
        self.updateImage()

    # paintEvent callback
    def imageLabelPaintEvent(self, obj):
        painter = Qt.QPainter(self.imageLabel)

        if ((self.mapped_image is not None) and
                (self.reference_image is not None)):
            # then we can draw the difference

            ref = self.reference_image.getQImage()
            img = self.mapped_image.getQImage()

            if (img is None) or (ref is None):
                return

            rot_center = (img.width()/2.0, img.height()/2.0)
            mainframe_angle = -self.ref_shift[2]

            painter.scale(self.actual_zoom, self.actual_zoom)
            painter.translate(rot_center[0], rot_center[1])
            painter.rotate(mainframe_angle)
            painter.drawImage(-int(rot_center[0]),
                              -int(rot_center[1]),
                              ref)
            painter.drawLine(rot_center[0], rot_center[1],
                             rot_center[0]+50, rot_center[1])
            painter.setCompositionMode(22)

            x = self.offset[0] - self.ref_shift[0]
            y = self.offset[1] - self.ref_shift[1]

            cosa = math.cos(np.deg2rad(-self.ref_shift[2]))
            sina = math.sin(np.deg2rad(-self.ref_shift[2]))

            xi = x*cosa + y*sina
            yi = y*cosa - x*sina

            painter.translate(-xi, -yi)
            painter.rotate(-self.offset[2]+self.ref_shift[2])

            painter.drawImage(-int(rot_center[0]),
                              -int(rot_center[1]),
                              img)
            painter.setCompositionMode(0)

            # drawing mainframe
            painter.resetTransform()
            painter.translate(15, 15)
            painter.rotate(mainframe_angle)

            # x axis
            painter.setPen(QtCore.Qt.red)
            painter.drawLine(0, 0, 50, 0)
            painter.drawLine(40, 3, 50, 0)
            painter.drawLine(40, -3, 50, 0)

            # y axis
            painter.setPen(QtCore.Qt.green)
            painter.drawLine(0, 0, 0, 50)
            painter.drawLine(-3, 40, 0, 50)
            painter.drawLine(3, 40, 0, 50)
        del painter


class DropDownWidget(QtGui.QWidget):

    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)

    def paintEvent(self, event):
        opt = QtGui.QStyleOption()
        opt.init(self)
        painter = QtGui.QPainter(self)
        self.style().drawPrimitive(QtGui.QStyle.PE_Widget,
                                   opt,
                                   painter,
                                   self)


class PlotSubWidget(QtGui.QWidget):

    def __init__(self, parent=None):
        assert isinstance(parent, PlotWidget), "parent is not a PlotWidget"
        QtGui.QWidget.__init__(self, parent)
        gboxlayout = Qt.QGridLayout()

        self._click_offset = QtCore.QPoint()
        self.padding = (10, 10)
        self.resize(150, 100)
        self._grip_size = 6
        self._gripes = {
            (0.0, 0.0): QtCore.Qt.SizeFDiagCursor,
            (0.5, 0.0): QtCore.Qt.SizeVerCursor,
            (1.0, 0.0): QtCore.Qt.SizeBDiagCursor,
            (0.0, 0.5): QtCore.Qt.SizeHorCursor,
            (1.0, 0.5): QtCore.Qt.SizeHorCursor,
            (0.0, 1.0): QtCore.Qt.SizeBDiagCursor,
            (0.5, 1.0): QtCore.Qt.SizeVerCursor,
            (1.0, 1.0): QtCore.Qt.SizeFDiagCursor
        }
        self._resizing = False
        self._tlt_lbl = QtGui.QLabel()
        self.close_button = QtGui.QPushButton('x', self._tlt_lbl)

        self._tlt_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self._tlt_lbl.setObjectName("Title")

        self.close_button.setObjectName("Close")
        self.close_button.setMaximumSize(25, 25)
        self.close_button.resize(15, 15)
        self.close_button.move(0, 0)
        self.close_button.setCursor(QtCore.Qt.PointingHandCursor)

        self.setCursor(QtCore.Qt.SizeAllCursor)
        self.setMouseTracking(True)

        self.setFocusPolicy(QtCore.Qt.ClickFocus)

        self.setMinimumSize(100, 50)

        gboxlayout.setContentsMargins(self._grip_size, self._grip_size,
                                      self._grip_size, self._grip_size)
        gboxlayout.addWidget(self._tlt_lbl, 0, 0, 1, 2)

        self.setLayout(gboxlayout)
        self.setEnabled(True)
        self.close_button.clicked.connect(self.hide)

    def setWindowTitle(self, title):
        self._tlt_lbl.setText(str(title))

    def _mouseOverGrip(self, pos):
        x = pos.x()
        y = pos.y()

        for grip in self._gripes.keys():
            grip_x = (self.width()-self._grip_size)*grip[0]
            grip_y = (self.height()-self._grip_size)*grip[1]
            if (x > grip_x and y > grip_y and
                    x < grip_x + self._grip_size and
                    y < grip_y + self._grip_size):
                return self._gripes[grip]
        return False

    def mousePressEvent(self, event):
        self._click_offset = event.pos()
        # is cursor over a grip?
        self._resizing = self._mouseOverGrip(self._click_offset)

    def mouseReleaseEvent(self, event):
        self._resizing = False
        self.setCursor(QtCore.Qt.SizeAllCursor)

    def mouseMoveEvent(self, event):
        if not self.hasFocus():
            self.setCursor(QtCore.Qt.PointingHandCursor)
            return

        x = event.x()
        y = event.y()

        cx = self.width()/2
        cy = self.height()/2

        if self._resizing == QtCore.Qt.SizeVerCursor:
            self.setCursor(self._resizing)
            if y < cy:
                self.move(self.x(), self.mapToParent(event.pos()).y())
                self.resize(self.width(), self.height() - y)
            else:
                self.resize(self.width(), y)
        elif self._resizing == QtCore.Qt.SizeHorCursor:
            self.setCursor(self._resizing)
            if x < cx:
                self.move(self.mapToParent(event.pos()).x(), self.y())
                self.resize(self.width() - x, self.height())
            else:
                self.resize(x, self.height())
        elif self._resizing == QtCore.Qt.SizeBDiagCursor:
            self.setCursor(self._resizing)
            if x < cx:
                self.move(self.mapToParent(event.pos()).x(), self.y())
                self.resize(self.width() - x, y)
            else:
                self.move(self.x(), self.mapToParent(event.pos()).y())
                self.resize(x, self.height() - y)
        elif self._resizing == QtCore.Qt.SizeFDiagCursor:
            self.setCursor(self._resizing)
            if x < cx:
                self.move(self.mapToParent(event.pos()))
                self.resize(self.width() - x, self.height() - y)
            else:
                self.resize(x, y)
        else:
            cursor = self._mouseOverGrip(event.pos())
            if cursor:
                self.setCursor(cursor)
            else:
                self.setCursor(QtCore.Qt.SizeAllCursor)
            if event.buttons() & QtCore.Qt.LeftButton:
                self.move(self.mapToParent(event.pos() - self._click_offset))

    def draw(self, painter):
        opt = QtGui.QStyleOption()
        opt.init(self)
        style = self.style()
        style.drawPrimitive(QtGui.QStyle.PE_Widget, opt, painter, self)

    def _paintGripes(self, painter):
        oldbrush = painter.brush()
        oldpen = painter.pen()
        painter.setPen(QtCore.Qt.gray)
        painter.setBrush(QtCore.Qt.green)
        for grip in self._gripes.keys():
            x = (self.width()-self._grip_size)*grip[0]
            y = (self.height()-self._grip_size)*grip[1]
            painter.drawRect(x, y, self._grip_size, self._grip_size)
        painter.setBrush(oldbrush)
        painter.setPen(oldpen)
        pass

    def paintEvent(self, event):
        painter = Qt.QPainter(self)
        painter.setRenderHint(painter.Antialiasing)
        surface_window = painter.window()

        w = surface_window.width()
        h = surface_window.height()
        f = painter.font()

        rect1 = QtCore.QRectF(0, 0, w, h)
        rect2 = QtCore.QRectF(self.padding[0],
                              self.padding[1],
                              w - 2*self.padding[0],
                              h - 2*self.padding[1])

        painter.setPen(QtCore.Qt.black)
        painter.setBrush(QtCore.Qt.white)
        painter.drawRect(rect1)

        f.setBold(True)
        painter.setFont(f)
        painter.drawText(rect2,
                         QtCore.Qt.AlignHCenter |
                         QtCore.Qt.AlignTop,
                         self.windowTitle())
        f.setBold(False)
        painter.setFont(f)

        self.draw(painter)
        if self.hasFocus():
            self._paintGripes(painter)


class PlotLegendWidget(PlotSubWidget):

    def __init__(self, parent=None):
        PlotSubWidget.__init__(self, parent)
        self.setWindowTitle(tr.tr("Legend"))
        self.setStyleSheet(
            """
            QLabel#Title
            {
                background-color: none;
                font: bold;
            }
            """)
        self.close_button.hide()
        self.close_button.deleteLater()
        self.close_button.setParent(None)
        del self.close_button
        gboxlayout = self.layout()
        gboxlayout.setRowStretch(1, 1)

    def draw(self, painter):
        if self.parent()._backend is None:
            count = 0
            y_off = painter.fontMetrics().xHeight()
            for plot in self.parent().plots:
                if plot.isVisible():
                    elx = self.padding[0]
                    ely = 3*self.padding[1] + y_off + 20*count
                    plot.drawQtLegendElement(painter, elx, ely)
                    count += 1


class PlotPropertyDialogWidget(PlotSubWidget):

    def __init__(self, parent=None):
        PlotSubWidget.__init__(self, parent)
        self.setWindowTitle(tr.tr("Plot properties"))
        self._selected_plot_idx = -1
        self.resize(250, 225)
        self.move(32, 32)
        gboxlayout = self.layout()

        if gboxlayout is None:
            gboxlayout = QtGui.QGridLayout()
            self.setLayout(gboxlayout)

        self._cur_plt_qcb = QtGui.QComboBox()
        self._int_ord_dsp = QtGui.QDoubleSpinBox()
        self._lne_wdt_dsp = QtGui.QDoubleSpinBox()
        self._mrk_sze_dsp = QtGui.QDoubleSpinBox()
        self._mrk_tpe_qcb = QtGui.QComboBox()
        self._lne_tpe_qcb = QtGui.QComboBox()
        self._bar_tpe_qcb = QtGui.QComboBox()
        self._plt_clr_qcb = QtGui.QComboBox()

        for i in plotting.MARKER_TYPES:
            self._mrk_tpe_qcb.addItem(i[1])

        for i in plotting.LINE_TYPES:
            self._lne_tpe_qcb.addItem(i[1])

        for i in plotting.BAR_TYPES:
            self._bar_tpe_qcb.addItem(i[1])

        for i in plotting.COLORS:
            self._plt_clr_qcb.addItem(i[1])

        self.setStyleSheet(
            """
            QLabel#Title
            {
                background-color: lightgray;
            }

            QPushButton#Close
            {
                background-color: transparent;
                color: black;
                border: none;
                font: bold;
            }

            QPushButton#Close:hover:!pressed
            {
                background-color: black;
                color: white;
            }

            QPushButton#Close:pressed
            {
                background-color: red;
                color: white;
            }
            """)

        self._int_ord_dsp.setSingleStep(0.1)
        self._lne_wdt_dsp.setSingleStep(0.1)
        self._mrk_sze_dsp.setSingleStep(0.5)

        gboxlayout.addWidget(self._cur_plt_qcb, 1, 0, 1, 2)

        gboxlayout.addWidget(QtGui.QLabel(tr.tr("line color")), 2, 0)
        gboxlayout.addWidget(self._plt_clr_qcb, 2, 1)

        gboxlayout.addWidget(QtGui.QLabel(tr.tr("line type")), 3, 0)
        gboxlayout.addWidget(self._lne_tpe_qcb, 3, 1)

        gboxlayout.addWidget(QtGui.QLabel(tr.tr("marker type")), 4, 0)
        gboxlayout.addWidget(self._mrk_tpe_qcb, 4, 1)

        gboxlayout.addWidget(QtGui.QLabel(tr.tr("errorbars type")), 5, 0)
        gboxlayout.addWidget(self._bar_tpe_qcb, 5, 1)

        gboxlayout.addWidget(QtGui.QLabel(tr.tr("line width")), 6, 0)
        gboxlayout.addWidget(self._lne_wdt_dsp, 6, 1)

        gboxlayout.addWidget(QtGui.QLabel(tr.tr("marker size")), 7, 0)
        gboxlayout.addWidget(self._mrk_sze_dsp, 7, 1)

        gboxlayout.addWidget(QtGui.QLabel(tr.tr("interpolation")), 8, 0)
        gboxlayout.addWidget(self._int_ord_dsp, 8, 1)

        self.setEnabled(True)

        self._cur_plt_qcb.currentIndexChanged.connect(self.currentPlotChanged)
        self._int_ord_dsp.valueChanged.connect(self.setInterpolationOrder)
        self._mrk_sze_dsp.valueChanged.connect(self.setMarkerSize)
        self._lne_wdt_dsp.valueChanged.connect(self.setLineWidth)
        self._mrk_tpe_qcb.currentIndexChanged.connect(self.setMarkerType)
        self._plt_clr_qcb.currentIndexChanged.connect(self.setColor)
        self._lne_tpe_qcb.currentIndexChanged.connect(self.setLineType)
        self._bar_tpe_qcb.currentIndexChanged.connect(self.setBarType)

    def setPlots(self, plots):
        self._cur_plt_qcb.clear()
        for plot in plots:
            self._cur_plt_qcb.addItem(plot.getName())

    def setInterpolationOrder(self, val):
        self.getSelectedPlot().setIterpolationOrder(val)
        self.parent().repaint()

    def setMarkerSize(self, val):
        self.getSelectedPlot().setMarkerSize(val)
        self.parent().repaint()

    def setLineWidth(self, val):
        self.getSelectedPlot().setLineWidth(val)
        self.parent().repaint()

    def setColor(self, idx):
        self.getSelectedPlot().setColorIndex(idx)
        self.parent().repaint()

    def setMarkerType(self, idx):
        self.getSelectedPlot().setMarkerTypeIndex(idx)
        self.parent().repaint()

    def setLineType(self, idx):
        self.getSelectedPlot().setLineTypeIndex(idx)
        self.parent().repaint()

    def setBarType(self, idx):
        self.getSelectedPlot().setBarTypeIndex(idx)
        self.parent().repaint()

    def updatePlotControls(self):
        plot = self.getSelectedPlot()
        if plot is None:
            return

        int_ord = float(plot.getIterpolationOrder())
        mrk_sze = float(plot.getMarkerSize())
        lne_wdt = float(plot.getLineWidth())

        mrk_tpe_idx = plotting.getMarkerTypeIndex(plot.getMarkerType())
        lne_tpe_idx = plotting.getLineTypeIndex(plot.getLineType())
        bar_tpe_idx = plotting.getBarTypeIndex(plot.getBarType())
        plt_clr_idc = plotting.getColorIndex(plot.getColor())

        self._int_ord_dsp.setValue(int_ord)
        self._mrk_sze_dsp.setValue(mrk_sze)
        self._lne_wdt_dsp.setValue(lne_wdt)
        self._mrk_tpe_qcb.setCurrentIndex(mrk_tpe_idx)
        self._lne_tpe_qcb.setCurrentIndex(lne_tpe_idx)
        self._bar_tpe_qcb.setCurrentIndex(bar_tpe_idx)
        self._plt_clr_qcb.setCurrentIndex(plt_clr_idc)

    def currentPlotChanged(self, plot_idx):
        self._selected_plot_idx = plot_idx
        self.updatePlotControls()

    def getSelectedPlot(self):
        if self._selected_plot_idx < 0:
            self._int_ord_dsp.setEnabled(False)
            self._lne_wdt_dsp.setEnabled(False)
            self._mrk_sze_dsp.setEnabled(False)
            self._mrk_tpe_qcb.setEnabled(False)
            self._lne_tpe_qcb.setEnabled(False)
            self._plt_clr_qcb.setEnabled(False)
            return None
        else:
            self._int_ord_dsp.setEnabled(True)
            self._lne_wdt_dsp.setEnabled(True)
            self._mrk_sze_dsp.setEnabled(True)
            self._mrk_tpe_qcb.setEnabled(True)
            self._lne_tpe_qcb.setEnabled(True)
            self._plt_clr_qcb.setEnabled(True)
            return self.parent().plots[self._selected_plot_idx]


class PlotWidget(QtGui.QWidget):

    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)

        self.plots = []
        self._backend = None
        self.axis_name = ('x', 'y')
        self._inverted_y = False
        self._x_offset = 60.0
        self._y_offset = 60.0
        self._x_fmt_func = utils.getTimeStr
        self._x_legend = -1
        self._y_legend = -1
        self._legend = PlotLegendWidget(self)
        self._dialog = PlotPropertyDialogWidget(self)
        self._prop_qpb = Qt.QPushButton(self)
        self._legend.setWindowTitle(tr.tr("Legend"))

        self._prop_qpb.setIcon(utils.getQIcon("gear"))
        self._prop_qpb.setIconSize(QtCore.QSize(16, 16))
        self._prop_qpb.move(2, 2)
        self._prop_qpb.setFlat(True)

        self._dialog.hide()

        self._prop_qpb.clicked.connect(self._dialog.show)

        _init_legend_x = 0
        _init_legend_y = self._y_offset
        self._legend.move(_init_legend_x, _init_legend_y)
        self.setFocusPolicy(QtCore.Qt.ClickFocus)

    def showLegend(self):
        self._legend.show()
        self.repaint()

    def hideLegend(self):
        self._legend.hide()
        self.repaint()

    def setLegendVisible(self, val):
        if val:
            self.showLegend()
        else:
            self.hideLegend()

    def addPlot(self, plt):
        self.plots.append(plt)
        self._dialog.setPlots(self.plots)
        plt.setInvertedY(self._inverted_y)

    def setInvertedY(self, inverted=True):
        self._inverted_y = bool(inverted)
        for plt in self.plots:
            plt.setInvertedY(inverted)
        newy = self.height() - self._legend.y() - self._legend.height()
        self._legend.move(self._legend.x(), newy)
        self.repaint()

    def resizeEvent(self, event):
        oldx = self._legend.x()
        oldy = self._legend.y()

        lwdt = self._legend.width()
        lght = self._legend.height()

        oldw = event.oldSize().width()
        oldh = event.oldSize().height()

        neww = event.size().width()
        newh = event.size().height()

        if oldw < 0:
            # This is probably the first resize
            # executed when the widget is created
            newx = neww - self._x_offset - lwdt
            if self._inverted_y:
                newy = newh - self._y_offset - lght
            else:
                newy = self._y_offset
        else:
            xcorr = lwdt/2.0
            ycorr = lght/2.0

            xperc = float(oldx + xcorr)/float(oldw)
            yperc = float(oldy + ycorr)/float(oldh)

            newx = xperc*neww - xcorr
            newy = yperc*newh - ycorr

        self._legend.move(newx, newy)

    def paintEvent(self, event):
        painter = Qt.QPainter(self)
        painter.setRenderHint(painter.Antialiasing)
        surface_window = painter.window()

        painter.setBrush(QtCore.Qt.white)
        painter.drawRect(surface_window)

        if not self.plots:
            # no plots to draw
            return

        # computing plot range
        there_is_a_plot = False
        for plot in self.plots:
            if plot.isHidden():
                continue
            elif not there_is_a_plot:
                there_is_a_plot = True
                vmin, vmax = plot.getYMinMax()
                hmin, hmax = plot.getXMinMax()
                continue
            pvmin, pvmax = plot.getYMinMax()
            phmin, phmax = plot.getXMinMax()
            vmin = min(vmin, pvmin)
            vmax = max(vmax, pvmax)
            hmin = min(hmin, phmin)
            hmax = max(hmax, phmax)

        if not there_is_a_plot:
            vmin = 0
            vmax = 1
            hmin = 0
            hmax = 1

        vmval, vmexp = utils.getSciVal(vmax)
        vmax = (vmval+0.5)*(10**vmexp)

        if hmin == hmax:
            hmax = hmin + 1
        if vmin == vmax:
            hmax = hmin + 1

        # drawing axis
        plotting.drawAxis(
            painter,
            data_x=(hmin, hmax),
            data_y=(vmin, vmax),
            inverted_y = self._inverted_y,
            axis_name=self.axis_name,
            x_str_func = self._x_fmt_func)

        # drawing plots
        painter.setBrush(QtCore.Qt.white)
        for plot in self.plots:
            if self._backend is None:
                plot.drawQt(painter,
                            (vmin, vmax),
                            (self._x_offset, self._y_offset))


class PlotViewer(QtGui.QWidget):

    def __init__(self, parent=None, inverted_y=False):
        QtGui.QWidget.__init__(self, parent)

        self._pv = PlotWidget(parent=self)

        self._plt_lst_qlw = ToolComboCheckBox(
            tr.tr("lightcurves:"),
            tr.tr("Select the lightcurves to show"))
        self._plt_lst_qlw.itemChanged.connect(self._ccbItemChanged)

        toolbar = Qt.QToolBar('PlotViewerToolBar')

        save_plot_action = QtGui.QAction(
            utils.getQIcon("save-plot"),
            tr.tr('Save the displayed plot to a file'),
            self)

        export_cvs_action = QtGui.QAction(
            utils.getQIcon("text-csv"),
            tr.tr('Export plot data to a cvs file'),
            self)

        invert_y_action = QtGui.QAction(
            utils.getQIcon("invert-y-axis"),
            tr.tr('Invert the Y axis'),
            self)
        invert_y_action.setCheckable(True)

        show_legend_action = QtGui.QAction(
            utils.getQIcon("legend"),
            tr.tr('Show plot legend'),
            self)
        show_legend_action.setCheckable(True)

        toolbar.addAction(save_plot_action)
        toolbar.addAction(export_cvs_action)
        toolbar.addAction(invert_y_action)
        toolbar.addAction(show_legend_action)
        toolbar.addWidget(self._plt_lst_qlw)

        self._pv.setSizePolicy(
            QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding,
                              QtGui.QSizePolicy.Expanding))

        mainlayout = Qt.QVBoxLayout(self)

        mainlayout.addWidget(toolbar)
        mainlayout.addWidget(self._pv)

        self.setLayout(mainlayout)

        export_cvs_action.triggered.connect(self.exportNumericDataCSV)
        show_legend_action.toggled.connect(self._pv.setLegendVisible)
        invert_y_action.toggled.connect(self._pv.setInvertedY)

        show_legend_action.setChecked(True)
        invert_y_action.setChecked(inverted_y)

    def setAxisName(self, xname, yname):
        self._pv.axis_name = (str(xname), str(yname))

    def _ccbItemChanged(self, item):
        plot = self._pv.plots[item.index().row()]
        plot.setVisible(item.checkState())
        self.repaint()

    def addPlots(self, plots):
        idx = len(self._pv.plots)
        for plot in plots:
            if plot not in self._pv.plots:
                plot.setColor(plotting.getColor(idx))
                self._plt_lst_qlw.addItem(plot.name, checked=plot.isVisible())
                self._pv.addPlot(plot)
                idx += 1

    def exportNumericDataCSV(self):
        file_name = str(Qt.QFileDialog.getSaveFileName(
            None,
            tr.tr("Export data to CSV file"),
            os.path.join('lightcurves.csv'),
            "CSV *.csv (*.csv);;All files (*.*)",
            None,
            utils.DIALOG_OPTIONS))

        csvtable = {}

        for plot in self._pv.plots:
            csvtable[plot.getName()] = [
                plot.getXData(),
                plot.getYData(),
                plot.getXError(),
                plot.getYError(),
            ]

        csvdata = ""
        csvsep = ","
        padding = csvsep*5

        # Header
        header = []
        for plotname in csvtable.keys():
            header.append(plotname)
            csvdata += str(plotname) + padding
        csvdata += '\n'

        for head in header:
            csvdata += "time" + csvsep
            csvdata += "value" + csvsep
            csvdata += "time error" + csvsep
            csvdata += "value error" + csvsep
            csvdata += csvsep
        csvdata += '\n'

        # Curve data
        i = 0
        notcompleted = True
        while notcompleted:
            notcompleted = False
            s = ""
            for head in header:
                plotdata = csvtable[head]
                try:
                    s += str(plotdata[0][i]) + csvsep
                    s += str(plotdata[1][i]) + csvsep
                    s += str(plotdata[2][i]) + csvsep
                    s += str(plotdata[3][i]) + csvsep
                    s += csvsep
                except IndexError:
                    s += padding
                else:
                    notcompleted = True
            csvdata += s+'\n'
            i += 1

        try:
            f = open(file_name, 'w')
        except Exception as exc:
            msgBox = Qt.QMessageBox()
            msgBox.setText(tr.tr("Cannot create the data file: ")+str(exc))
            msgBox.setInformativeText(
                tr.tr("Assure you have the authorization to write the file."))
            msgBox.setIcon(Qt.QMessageBox.Critical)
            msgBox.exec_()
        else:
            f.write(csvdata)

    def exportNumericDataODS(self):
        raise NotImplementedError()


class LightCurveViewer(PlotViewer):

    _pltprp_grb_txt = tr.tr("Lightcurve properties")
