#lxnstack is a program to align and stack atronomical images
#Copyright (C) 2013-2014  Maurizio D'Addona <mauritiusdadd@gmail.com>

#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.
import math
import utils
from PyQt4 import Qt, QtCore, QtGui, uic
import colormaps as cmaps
import mappedimage
import numpy as np
import os
import paths
import logging
import log

IMAGEVIEWER = "imageviewer"
DIFFERENCEVIEWER = "diffviewer"

READY        = 0x0001
UPDATED      = 0x0002
NEEDSUPDATE  = 0x0004


class SplashScreen(Qt.QObject):
    
    def __init__(self):
        Qt.QObject.__init__(self)
        self._pxm = Qt.QPixmap(os.path.join(paths.DATA_PATH,"splashscreen.jpg"))
        self._qss = Qt.QSplashScreen(self._pxm, 
                                     (QtCore.Qt.WindowStaysOnTopHint |
                                      QtCore.Qt.X11BypassWindowManagerHint))
        
        self._msg=''
        self._maxv=100.0
        self._minv=0.0
        self._cval=0.0
                
        self._qss.__drawContents__=self._qss.drawContents
        self._qss.drawContents=self._drawContents
        
        self._qss.show()
        
        self.processEvents()
        
    def close(self):
        self.update()
        self._qss.close()
    
    def setMaximum(self,val):
        self._maxv=val
        self.update()
    
    def setMinimum(self,val):
        self._minv=val
        self.update()
    
    def setValue(self,val):        
        for i in np.arange(self._cval,val,(self._maxv-self._minv)/100.0):
            self._cval=i
            self.update()
    
    def maximum(self):
        return self._maxv
    
    def minimum(self):
        return self._minv
    
    def value(self):
        return self._cval
    
    def message(self):
        return self._msg
    
    def showMessage(self,msg):
        self._msg=msg
        #self._qss.showMessage(msg,QtCore.Qt.AlignBottom|QtCore.Qt.AlignLeft,QtCore.Qt.white)
        self.update()
    
    def update(self):
        self._qss.update()
        self.processEvents()
        
    def _drawContents(self,painter):
        #self._qss.__drawContents__(painter)
        
        view_port=painter.viewport()
        
        w=view_port.right()
        h=view_port.bottom()
        
        
        
        painter.setPen(Qt.QColor(55,55,55,255))
        painter.setBrush(Qt.QColor(0,0,0,255))
        painter.drawRect(10,h-25,w-20,15)
        
        redlg = Qt.QLinearGradient(0,0,w,0)
        redlg.setColorAt(0, Qt.QColor(10,10,155))
        redlg.setColorAt(0.8, Qt.QColor(10,10,255))
        
        alg = Qt.QLinearGradient(0,h-25,0,h)
        alg.setColorAt(0, Qt.QColor(0,0,0,150))
        alg.setColorAt(0.5, Qt.QColor(0,0,0,0))
        
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(redlg)
        painter.drawRect(11,h-24,(w-21)*self._cval/self._maxv,14)
        
        painter.setBrush(alg)
        painter.drawRect(11,h-24,(w-21)*self._cval/self._maxv,14)
        
        painter.setPen(QtCore.Qt.white)
        
        rect=Qt.QRectF(10,h-23,w-20,15)
        painter.drawText(rect, QtCore.Qt.AlignCenter, str(self._msg))
        
    def finish(self,qwid):
        self._qss.finish(qwid)
    
    def processEvents(self):
        qapp=QtGui.QApplication.instance()
        if qapp is not None:
            qapp.processEvents()


class ToolComboBox(Qt.QFrame):
    
    def __init__(self,title="",tooltip="",useframe=True):
        Qt.QFrame.__init__(self)
        self.setFrameStyle(Qt.QFrame.Plain)
        self._label=Qt.QLabel(title)
        self._selector = Qt.QComboBox()
        
        vLayout = Qt.QHBoxLayout(self)

        vLayout.addWidget(self._label)
        vLayout.addWidget(self._selector)
        
        self.setLabel=self._label.setText
        self.addItem=self._selector.addItem
        self.addItems=self._selector.addItems        
        self.count = self._selector.count
        self.currentIndexChanged=self._selector.currentIndexChanged
        self.currentIndex=self._selector.currentIndex
        self.setCurrentIndex=self._selector.setCurrentIndex
        self.currentText = self._selector.currentText
        self.duplicatesEnabled = self._selector.duplicatesEnabled
        self.setFrame=self._selector.setFrame
        self.hasFrame=self._selector.hasFrame    
        self.clear=self._selector.clear
        
        self.setFrame(useframe)
        
class ImageViewer(QtGui.QWidget):
    
    #titleChanged = QtCore.pyqtSignal(str)
    
    def __init__(self, infolabel=None):
        QtGui.QWidget.__init__(self)
        
        self.zoom = 1
        self.min_zoom = 0
        self.actual_zoom=1
        self.exposure=0
        self.zoom_enabled=False
        self.zoom_fit=False
        self.mapped_image = mappedimage.MappedImage()
        self.fit_levels=False
        self.panning = False
        self.feature_moveing = False
        self.selected_feature=None
        self.colorbarmap = mappedimage.MappedImage(name='colorbar')
                
        self.user_cursor = QtCore.Qt.OpenHandCursor
        
        self.levels_range=[0,100]
        self.image_features=[]
        
        self.statusLabelMousePos = infolabel
        
        toolbar = Qt.QToolBar('ImageViewerToolBar')
        
        # ToolBar actions
        save_action=QtGui.QAction(utils.getQIcon("save-image"), utils.tr('Save the displayed image to a file'), self)
        action_edit_levels = QtGui.QAction(utils.getQIcon("edit-levels"), utils.tr('Edit input levels'), self)
        action_edit_levels.setCheckable(True)
        
        # colormap controls
        self.colormap_selector=ToolComboBox(utils.tr("colormap:"),tooltip=utils.tr("Image color-map"))
        data = np.meshgrid(np.arange(64),np.arange(64))[0]
        
        keys=cmaps.COLORMAPS.keys()
        keys.sort()
        
        for ccmap in keys:
            cmap=cmaps.COLORMAPS[ccmap]
            icon=Qt.QPixmap.fromImage(mappedimage.arrayToQImage(data,cmap=cmap,fit_levels=True))
            self.colormap_selector.addItem(QtGui.QIcon(icon),cmap.name)
        
        self.colormap_selector.setEnabled(True)        
        
        # zoom controls
        self.zoomCheckBox = QtGui.QCheckBox(utils.tr("zoom: none"))
        self.zoomSlider = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.zoomDoubleSpinBox = QtGui.QDoubleSpinBox()
        
        # image viewer controls
        self.imageLabel=QtGui.QLabel()
        self.scrollArea = QtGui.QScrollArea()
        self.viewHScrollBar =  self.scrollArea.horizontalScrollBar()
        self.viewVScrollBar =  self.scrollArea.verticalScrollBar()
        
        # colorbar controls
        self.colorBar = QtGui.QLabel()
        self.fitMinMaxCheckBox = QtGui.QCheckBox(utils.tr("contrast: none"))
        self.minLevelDoubleSpinBox = QtGui.QDoubleSpinBox()
        self.maxLevelDoubleSpinBox = QtGui.QDoubleSpinBox()
                
        self.colorBar.current_val=None
        self.colorBar.max_val=1.0
        self.colorBar.min_val=0.0
        self.colorBar._is_rgb=False
        
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
        self.scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setWidget(self.imageLabel)
        self.scrollArea.setAlignment(QtCore.Qt.AlignLeft|QtCore.Qt.AlignTop)
        
        self.scrollArea.setSizePolicy(QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding))
        self.scrollArea.setFrameShape(QtGui.QFrame.StyledPanel)
        self.scrollArea.setFrameShadow(QtGui.QFrame.Sunken)
        
        self.colorBar.setSizePolicy(QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed))
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
        maplayout = QtGui.QHBoxLayout()
        
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
        self.imageLabel.__mouseMoveEvent__= self.imageLabel.mouseMoveEvent #base implementation
        self.imageLabel.mouseMoveEvent = self.imageLabelMouseMoveEvent #new callback
        
        self.imageLabel.__mousePressEvent__ = self.imageLabel.mousePressEvent
        self.imageLabel.mousePressEvent = self.imageLabelMousePressEvent
        
        self.imageLabel.__mouseReleaseEvent__ = self.imageLabel.mouseReleaseEvent
        self.imageLabel.mouseReleaseEvent = self.imageLabelMouseReleaseEvent
        
        self.scrollArea.__wheelEvent__ = self.scrollArea.wheelEvent
        self.scrollArea.wheelEvent = self.scrollAreaWheelEvent
        
        # resize callback
        self.__resizeEvent__= self.scrollArea.resizeEvent #base implementation
        self.scrollArea.resizeEvent = self.scrollAreaResizeEvent #new callback
        
        
        # paint callback
        self.imageLabel.__paintEvent__= self.imageLabel.paintEvent #base implementation
        self.imageLabel.paintEvent = self.imageLabelPaintEvent #new callback        
        
        # paint callback for colorBar
        self.colorBar.__paintEvent__= self.colorBar.paintEvent #base implementation
        self.colorBar.paintEvent = self.colorBarPaintEvent #new callback        

        save_action.triggered.connect(self.doSaveImage)
        action_edit_levels.triggered.connect(self.doEditLevels)
        
        self.mapped_image.remapped.connect(self.updateImage)
        
        self.zoomCheckBox.stateChanged.connect(self.setZoomMode)
        self.zoomSlider.valueChanged.connect(self.signalSliderZoom)
        self.zoomDoubleSpinBox.valueChanged.connect(self.signalSpinZoom)
        self.fitMinMaxCheckBox.stateChanged.connect(self.setDisplayLevelsFitMode)
        self.minLevelDoubleSpinBox.valueChanged.connect(self.setMinLevel)
        self.maxLevelDoubleSpinBox.valueChanged.connect(self.setMaxLevel)
        self.colormap_selector.currentIndexChanged.connect(self.setColorMapID)        
        
        self.setZoomMode(1,True)
        self.setOutputLevelsRange((0,100))
        self.setDisplayLevelsFitMode(0)
    
    def doSaveImage(self):
        if self.mapped_image is not None:
            frm=utils.Frame()
            frm.saveData(data=self.mapped_image.getMappedData())
                       
    def setColorMapID(self, cmapid):
        self.setColorMap(cmaps.COLORMAPS[cmapid])
        
    def setColorMap(self,cmap):
        log.log(repr(self),"Setting new colormap",level=logging.DEBUG)
        if self.mapped_image is not None:
            self.mapped_image.setColormap(cmap,update=False)
            self.generateScaleMaps(remap=False)
            self.mapped_image.remap()
    
    def getColorMap(self):
        return self.mapped_image.getColormap()
    
    def updateColorMap(self,val):
        self.colormap_selector.setCurrentIndex(val)
            
    def generateScaleMaps(self, remap=True):        
        
        if self.mapped_image is None:
            return
        
        ncomponents = self.mapped_image.componentsCount()
        
        if ncomponents < 1:
            return
        
        elif ncomponents == 1:
            log.log(repr(self),"Generating ColorBar scalemaps...",level=logging.DEBUG)
            data1 = np.arange(0,self.colorBar.width())*255.0/self.colorBar.width()
            data2 = np.array([data1]*(self.colorBar.height()-8))
            data3 = data2

        else:
            log.log(repr(self),"Generating ColorBar RGB scalemaps...",level=logging.DEBUG)
            data1 = np.arange(0,self.colorBar.width())*255.0/self.colorBar.width()
            data2 = np.array([data1]*int((self.colorBar.height()-8)/float(ncomponents)))
            hh=len(data2)
            data3 = np.zeros((ncomponents*hh,len(data1),ncomponents))
            
            for i in xrange(ncomponents):
                data3[i*hh:(i+1)*hh,0:,i]=data2

        if isinstance(self.colorbarmap,mappedimage.MappedImage):
            self.colorbarmap.setColormap(self.mapped_image.getColormap(),update=False)
            self.colorbarmap.setOutputLevels(lrange=self.levels_range, lfitting=self.fit_levels, update=False)
            self.colorbarmap.setData(data3,update=remap)
        else:
            self.colorbarmap = mappedimage.MappedImage(data3,
                                                       self.mapped_image.getColormap(),
                                                       fit_levels=self.fit_levels,
                                                       levels_range=self.levels_range,
                                                       name='colorbar',
                                                       update=remap)
    
    #resizeEvent callback
    def scrollAreaResizeEvent(self, event):
        val = self.__resizeEvent__(event)# old implementation
        if self.zoom_fit:
            self.updateImage()
        self.generateScaleMaps()
        return val
    
    #mouseMoveEvent callback    
    def imageLabelMouseMoveEvent(self, event):
        val = self.imageLabel.__mouseMoveEvent__(event)
        mx=event.x()
        my=event.y()
        x=utils.Int(mx/self.actual_zoom)
        y=utils.Int(my/self.actual_zoom)
                
        if (self.mapped_image is not None):
            if self.mapped_image.getOriginalData() is not None:
                imshape = self.mapped_image.getOriginalData().shape
                if ((y>=0) and (y < imshape[0]) and
                    (x>=0) and (x < imshape[1])):
                        pix_val=self.mapped_image.getOriginalData()[y,x]
                        self.current_pixel=(x,y)
                        try:
                            self.colorBar.current_val=tuple(pix_val)
                        except:
                            try:
                                self.colorBar.current_val=(int(pix_val),)
                            except:
                                self.colorBar.current_val=(0,)*self.mapped_image.componentsCount()
                        self.colorBar.repaint()
            else:
                pix_val=None
                
                
        if self.panning:            
            sx = mx-self.movement_start[0]
            sy = my-self.movement_start[1]           
            
            self.viewHScrollBar.setValue(self.viewHScrollBar.value()-sx)
            self.viewVScrollBar.setValue(self.viewVScrollBar.value()-sy)
            
        elif self.feature_moveing:
            self.selected_feature.move(x,y)
            self.repaint()
        else:            
            for feature in self.image_features:
                if ((x-feature.x)**2 + (y-feature.y)**2) < feature.r**2:
                    self.scrollArea.setCursor(QtCore.Qt.SizeAllCursor)
                    self.imageLabel.setCursor(QtCore.Qt.SizeAllCursor)
                    feature.mouse_over=True
                    self.selected_feature=feature                    
                    break
                else:
                    self.imageLabel.setCursor(self.user_cursor)
                    feature.mouse_over=False
                    self.selected_feature=None
            self.repaint()
        return val
    
    
    def scrollAreaWheelEvent(self, event):
        if self.zoom_enabled:
            delta = np.sign(event.delta())*math.log10(self.zoom+1)/2.5
            mx=event.x()
            my=event.y()
            cx = self.scrollArea.width()/2.0
            cy = self.scrollArea.height()/2.0
            sx=(cx - mx)/2
            sy=(cy - my)/2
            self.viewHScrollBar.setValue(self.viewHScrollBar.value()-sx)
            self.viewVScrollBar.setValue(self.viewVScrollBar.value()-sy)
                        
            self.setZoom(self.zoom+delta)

            
        return Qt.QWheelEvent.accept(event)
    
    def imageLabelMousePressEvent(self, event):
        val = self.imageLabel.__mousePressEvent__(event)
        btn=event.button()
        
        if btn==1:
            self.movement_start=(event.x(),event.y())
            if self.selected_feature is None:
                self.scrollArea.setCursor(QtCore.Qt.ClosedHandCursor)
                self.imageLabel.setCursor(QtCore.Qt.ClosedHandCursor)
                self.panning=True
                self.feature_moveing=False
            else:
                self.panning=False
                self.scrollArea.setCursor(QtCore.Qt.BlankCursor)
                self.imageLabel.setCursor(QtCore.Qt.BlankCursor)
                self.feature_moveing=True
                self.selected_feature.mouse_grabbed=True

        return val
    
    def imageLabelMouseReleaseEvent(self, event):
        val = self.imageLabel.__mouseReleaseEvent__(event)
        btn=event.button()
        if btn==1:
            self.panning=False
            self.feature_moveing=False
            self.scrollArea.setCursor(self.user_cursor)
            self.imageLabel.setCursor(self.user_cursor)
            
            if not (self.selected_feature is None):
                self.selected_feature.mouse_grabbed=False
        
        return val
    
    #paintEvent callback
    def imageLabelPaintEvent(self, obj):
        val=self.imageLabel.__paintEvent__(obj)
        
        painter = Qt.QPainter(self.imageLabel)
        
        if self.mapped_image is not None:
            qimg = self.mapped_image.getQImage()
            if qimg is not None:
                painter.scale(self.actual_zoom,self.actual_zoom)
                painter.drawImage(0,0,self.mapped_image.getQImage())
                
        for feature in self.image_features:
            try:
                feature.draw(painter)
            except:
                pass
            
        del painter
        return val

    #paintEvent callback for colorBar
    def colorBarPaintEvent(self, obj):
        val=self.colorBar.__paintEvent__(obj)

        if self.mapped_image is None:
            return self.colorBar.__paintEvent__(obj)
        
        if self.colorBar.current_val is not None:
            painter = Qt.QPainter(self.colorBar)
            cb = self.colorBar
            
            
            _gpo=2 #geometric corrections
            _gno=5 #geometric corrections
            _gpv=4 #geometric corrections
            
            dw=painter.device().width()-_gno
            dh=painter.device().height()-2*_gpv
            
            devicerect = QtCore.QRect(_gpo,_gpv,dw,dh)
            
            fnt_size=10
            painter.setFont(Qt.QFont("Arial", fnt_size))
            y=(cb.height()+fnt_size/2)/2 + 2
            max_txt=str(cb.max_val)
            
            if self.statusLabelMousePos is not None:
                try:
                    self.statusLabelMousePos.setText('position='+str(self.current_pixel)+' value='+str(cb.current_val))
                except:
                    pass
            
            qimg = self.colorbarmap.getQImage()
            if qimg is not None:
                painter.drawImage(devicerect,qimg)
            
            ncomp = len(cb.current_val)
            hh = dh/ncomp
            
            painter.setCompositionMode(22)
            
            for i in xrange(ncomp):
                
                try:
                    x = int((float(cb.current_val[i]-cb.min_val)/float(cb.max_val-cb.min_val))*(cb.width()-_gno))+_gpo
                except Exception:
                    x = -1
                                    
                painter.setPen(QtCore.Qt.white)
                painter.drawLine(x,_gpv+i*hh,x,_gpv+(i+1)*hh)
                            
            painter.setCompositionMode(0)
            painter.setPen(QtCore.Qt.white)
            painter.drawText(fnt_size-4,y,str(cb.min_val))
            painter.setPen(QtCore.Qt.black)
            painter.drawText(cb.width()-(fnt_size-2)*len(max_txt),y,max_txt)
                
            del painter
            
        return val
    
    def setZoomMode(self, val, check=False):
        
        if check:
            self.zoomCheckBox.setCheckState(val)
        
        if val is 0:
            self.zoomCheckBox.setText(utils.tr('zoom: none'))
            self.zoomSlider.setEnabled(False)
            self.zoomDoubleSpinBox.setEnabled(False)
            self.zoom_enabled=False
            self.zoom_fit=False
        elif val is 1:
            self.zoomCheckBox.setText(utils.tr('zoom: fit'))
            self.zoomSlider.setEnabled(False)
            self.zoomDoubleSpinBox.setEnabled(False)
            self.zoom_enabled=False
            self.zoom_fit=True
        else:
            self.zoomCheckBox.setText(utils.tr('zoom: full'))
            self.zoomSlider.setEnabled(True)
            self.zoomDoubleSpinBox.setEnabled(True)
            self.zoom_enabled=True
            self.zoom_fit=False
        self.updateImage()
    
    def setZoom(self,zoom):
        
        if zoom <= self.zoomDoubleSpinBox.maximum():
            self.zoom=zoom
        else:
            self.zoom=self.zoomDoubleSpinBox.maximum()
            
        self.zoomDoubleSpinBox.setValue(self.zoom)
        self.zoomSlider.setValue(utils.Int(self.zoom*100))
        
    def signalSliderZoom(self, value, update=False):
        self.zoom=(value/100.0)
        vp = self.getViewport()
        self.zoomDoubleSpinBox.setValue(self.zoom)
        if update:
            self.updateImage()

        self.setViewport(vp)
        
    def signalSpinZoom(self, value, update=True):
        self.zoom=value
        vp = self.getViewport()
        self.zoomSlider.setValue(utils.Int(self.zoom*100))
        if update:
            self.updateImage()
        self.setViewport(vp)
        
    def getViewport(self):
        try:
            x = float(self.viewHScrollBar.value())/float(self.viewHScrollBar.maximum())
        except ZeroDivisionError:
            x = 0.5
        try:
            y = float(self.viewVScrollBar.value())/float(self.viewVScrollBar.maximum())
        except ZeroDivisionError:
            y = 0.5
            
        return (x,y)
    
    def setViewport(self,viewPoint):
        self.viewHScrollBar.setValue(viewPoint[0]*self.viewHScrollBar.maximum())
        self.viewVScrollBar.setValue(viewPoint[1]*self.viewVScrollBar.maximum())
            
    def showImage(self, image):
        if isinstance(image,mappedimage.MappedImage):
            log.log(repr(self),"Displaying new mappedimage",level=logging.DEBUG)
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
            log.log(repr(self),"Displaying new image",level=logging.DEBUG)
            self.mapped_image.setData(image)
            
    def clearImage(self):
        self.mapped_image.setData(None)
        self.imageLabel.setPixmap(Qt.QPixmap())
        
    def updateImage(self, paint=True, overridden_image=None):
        
        log.log(repr(self),"Updating the displayed image",level=logging.DEBUG)
        
        if overridden_image is not None:
            if isinstance(image,MappedImage):
                current_image=overridden_image
            else:
                return False
        elif self.mapped_image is not None:
            current_image=self.mapped_image
        else:
            return False
        
        qimg=current_image.getQImage()
        
        if qimg is None:
            return False
        
        imh = qimg.height()
        imw = qimg.width()
        
        if imw*imh <= 0:
            return False
        
                    
        self.colorbarmap.setCurve(*current_image.getCurve(),update=False)
        self.colorbarmap.setMWBCorrectionFactors(*current_image.getMWBCorrectionFactors(),update=False)
        self.colorbarmap.setOutputLevels(lrange=self.levels_range, lfitting=self.fit_levels, update=False)
        self.colorbarmap.setMapping(*current_image.getMapping(),update=False)
        
        if (self.colorbarmap.getQImage() is None or
            self.colorbarmap.getNumberOfComponents() != current_image.getNumberOfComponents()):
            self.generateScaleMaps()
        else:
            self.colorbarmap.remap()
        
        try:
            pix_val = current_image.getOriginalData()[self.current_pixel[1],self.current_pixel[0]]
            try:
                self.colorBar.current_val=tuple(pix_val)
            except:
                try:
                    self.colorBar.current_val=(int(pix_val),)
                except:
                    self.colorBar.current_val=(0,)*self.mapped_image.componentsCount()
            self.colorBar.repaint()
        except Exception as exc:
            self.current_pixel=(0,0)

        if self.zoom_enabled:
            self.actual_zoom=self.zoom
        elif self.zoom_fit:
                        
            self.actual_zoom=min(float(self.scrollArea.width()-10)/imw,
                                 float(self.scrollArea.height()-10)/imh
                                )
                                
            self.zoomDoubleSpinBox.setValue(self.zoom)
        else:
            self.actual_zoom=1
            
        if paint:
            imh+=1
            imw+=1
            self.imageLabel.setMaximumSize(imw*self.actual_zoom,imh*self.actual_zoom)
            self.imageLabel.setMinimumSize(imw*self.actual_zoom,imh*self.actual_zoom)
            self.imageLabel.resize(imw*self.actual_zoom,imh*self.actual_zoom)
            self.imageLabel.update()
            
            if current_image._original_data is not None:
                self.colorBar.max_val=current_image._original_data.max()
                self.colorBar.min_val=current_image._original_data.min()

                if (self.colorBar.max_val <=1) or self.fit_levels:
                    pass
                elif self.colorBar.max_val <= 255:
                    self.colorBar.max_val*=255.0/self.colorBar.max_val
                elif self.colorBar.max_val <= 65536:
                    self.colorBar.max_val*=65536.0/self.colorBar.max_val
                    
                if self.fit_levels:
                    pass
                elif self.colorBar.min_val > 0:
                    self.colorBar.min_val*=0
                
                if not self.colorBar.isVisible():
                    self.colorBar.show()
            else:
                self.colorBar.max_val=1
                self.colorBar.max_val=0
                if self.colorBar.isVisible():
                    self.colorBar.hide()
                
            #this shuold avoid division by zero
            if  self.colorBar.max_val ==  self.colorBar.min_val:
                self.colorBar.max_val=self.colorBar.max_val+1
                self.colorBar.min_val=self.colorBar.min_val-1
                
        return True
    
    def setOutputLevelsRange(self, lrange):
        self.minLevelDoubleSpinBox.setValue(np.min(lrange))
        self.maxLevelDoubleSpinBox.setValue(np.max(lrange))

    def setMinLevel(self, val):
        self.levels_range[0]=val
        if val <= self.levels_range[1]-1:
            self.setDisplayLevelsFitMode(self.fit_levels)
        else:
            self.maxLevelDoubleSpinBox.setValue(val+1)
        
    def setMaxLevel(self, val):
        self.levels_range[1]=val
        if val >= self.levels_range[0]+1:
            self.setDisplayLevelsFitMode(self.fit_levels)
        else:
            self.minLevelDoubleSpinBox.setValue(val-1)
    
    def forceDisplayLevelsFitMode(self,state):
        self.setDisplayLevelsFitMode(state)
        self.fitMinMaxCheckBox.hide()
        
    def setDisplayLevelsFitMode(self, state):
        
        log.log(repr(self),"Updating output levels",level=logging.DEBUG)
        
        if state==0:
            self.minLevelDoubleSpinBox.hide()
            self.maxLevelDoubleSpinBox.hide()
            self.fitMinMaxCheckBox.setText(utils.tr('contrast')+': '+utils.tr('none'))
        elif state==1:
            self.minLevelDoubleSpinBox.hide()
            self.maxLevelDoubleSpinBox.hide()
            self.fitMinMaxCheckBox.setText(utils.tr('contrast')+': '+utils.tr('full'))
        else:
            self.minLevelDoubleSpinBox.show()
            self.maxLevelDoubleSpinBox.show()
            self.fitMinMaxCheckBox.setText(utils.tr('contrast')+': '+utils.tr('yes'))
               
        self.fit_levels=state
        
        Qt.QApplication.instance().processEvents()
        
        if self.mapped_image is not None:
            self.setOutputLevelsRange(self.levels_range)
            self.mapped_image.setOutputLevels(self.levels_range,self.fit_levels,update=True)
            self.updateImage()
        else:
            self.generateScaleMaps()
            
        self.colorBar.repaint()
    
    def doEditLevels(self, clicked):
        return self.mapped_image.editLevels(clicked)


class DifferenceViewer(ImageViewer):
    
    
    def __init__(self, reference=None):
        ImageViewer.__init__(self)
        self.offset=(0,0,0)
        self.ref_shift=(0,0,0)
        self.reference_image = mappedimage.MappedImage(reference)
    
    def setOffset(self, dx, dy, theta):
        self.offset=(dx,dy,theta)
        self.repaint()
    
    def setRefShift(self, dx, dy, theta):
        self.ref_shift=(dx,dy,theta)
        self.repaint()    
    
    def setRefImage(self, image):
        if isinstance(image,mappedimage.MappedImage):
            del self.mapped_image
            self.reference_image = image
        else:
            self.reference_image.setData(image)
        self.updateImage()
        
    #paintEvent callback
    def imageLabelPaintEvent(self, obj):        
        painter = Qt.QPainter(self.imageLabel)
        
        if (self.mapped_image is not None) and (self.reference_image is not None):
            
            ref = self.reference_image.getQImage()
            img = self.mapped_image.getQImage()
            
            if (img is None) or (ref is None) :
                return
            
            rot_center=(img.width()/2.0,img.height()/2.0)
            
            mainframe_angle=-self.ref_shift[2]
            
            painter.scale(self.actual_zoom,self.actual_zoom)
            painter.translate(rot_center[0],rot_center[1])
            painter.rotate(mainframe_angle)
            painter.drawImage(-int(rot_center[0]),-int(rot_center[1]),ref)
            painter.drawLine(rot_center[0],rot_center[1],rot_center[0]+50,rot_center[1])
            painter.setCompositionMode(22)
            
            x = self.offset[0]-self.ref_shift[0]
            y = self.offset[1]-self.ref_shift[1]
            
            cosa = math.cos(np.deg2rad(-self.ref_shift[2]))
            sina = math.sin(np.deg2rad(-self.ref_shift[2]))
            
            xi = x*cosa + y*sina
            yi = y*cosa - x*sina
                        
            painter.translate(-xi,-yi)
            painter.rotate(-self.offset[2]+self.ref_shift[2])
            
            painter.drawImage(-int(rot_center[0]),-int(rot_center[1]),img)
            painter.setCompositionMode(0)
            
            # drawing mainframe
            painter.resetTransform()
            painter.translate(15,15)
            painter.rotate(mainframe_angle)
            
            # x axis
            painter.setPen(QtCore.Qt.red)
            painter.drawLine(0,0,50,0)
            painter.drawLine(40,3,50,0)
            painter.drawLine(40,-3,50,0)
            
            # y axis
            painter.setPen(QtCore.Qt.green)
            painter.drawLine(0,0,0,50)
            painter.drawLine(-3,40,0,50)
            painter.drawLine(3,40,0,50)
        del painter

