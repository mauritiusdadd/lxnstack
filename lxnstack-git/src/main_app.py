#lxnstack is a program to align and stack atronomical images
#Copyright (C) 2013  Maurizio D'Addona

#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import math
import time
import shutil
import subprocess
import webbrowser
from xml.dom import minidom
from PyQt4 import uic, Qt, QtCore, QtGui

def tr(s):
    news=QtCore.QCoreApplication.translate('@default',s)
    #python3 return str...
    if type(news) == str:
        return news
    else:
        #... while python2 return QString 
        # that must be converted to str
        return str(news.toAscii())

try:
    import numpy
except ImportError:
    msgBox = Qt.QMessageBox()
    msgBox.setText(tr("\'numpy\' python module not found!"))
    msgBox.setInformativeText(tr("Please install numpy."))
    msgBox.setIcon(Qt.QMessageBox.Critical)
    msgBox.exec_()
    sys.exit(1)

try:
    from PIL import Image
    Image.init()
except ImportError:
    msgBox = Qt.QMessageBox()
    msgBox.setText(tr("\'PIL\' python module not found!"))
    msgBox.setInformativeText(tr("Please install the python imaging library (PIL)."))
    msgBox.setIcon(Qt.QMessageBox.Critical)
    msgBox.exec_()
    sys.exit(1)

try:
    import cv2
except ImportError:
    msgBox = Qt.QMessageBox()
    msgBox.setText(tr("\'opencv2\' python module found!"))
    msgBox.setInformativeText(tr("Please install opencv2."))
    msgBox.setIcon(Qt.QMessageBox.Warning)
    msgBox.exec_()
    sys.exit(1)

import utils
import paths

def Int(val):
    i = math.floor(val)
    if ((val-i)<0.5):
        return int(i)
    else:
        return int(math.ceil(val))
    
def dist(x1,y1,x2,y2):
    return (((x2-x1)**2)+((y2-y1)**2))**0.5

class theApp(Qt.QObject):

    def __init__(self,qapp,lang=''):

        self.__operating=False
        self._photo_time_clock=0

        self.current_match_mode=cv2.TM_SQDIFF

        self.qapp=qapp

        self.images_extensions = ' ('
        for ext in Image.EXTENSION.keys():
            self.images_extensions+='*'+str(ext)+' '
        self.images_extensions += ');;'
        
        ImageTypes={}
        
        for ext in Image.EXTENSION.keys():
            key=str(Image.EXTENSION[ext])
            if key in ImageTypes:
                ImageTypes[key]+=' *'+str(ext)
            else:
                ImageTypes[key]=' *'+str(ext)

        for ext in ImageTypes:
            self.images_extensions+=tr('Image')+' '+ext+' : '+ImageTypes[ext]
            self.images_extensions+='('+ImageTypes[ext]+');;'

        if not os.path.isdir(paths.TEMP_PATH):
            os.makedirs(paths.TEMP_PATH)

        self.__current_lang=lang
        self.zoom = 1
        self.min_zoom = 0
        self.actual_zoom=1
        self.exposure=0
        self.zoom_enabled=False
        self.zoom_fit=False
        self.current_image = None
        self.ref_image=None
        self.current_dir='~'

        self.wasCanceled=False
        self.wasStopped=False
        self.wasStarted=False
        self.isPreviewing=False
        self.shooting=False
        
        self.image_idx=-1
        self.ref_image_idx=-1
        self.dif_image_idx=-1
        self.point_idx=-1

        self._drk=None
        self._avg=None
        self._flt=None
        
        self.autoalign_rectangle=(256,256)
        self.auto_align_use_whole_image=0
        
        self.manual_align=False

        self.IMAGE_RANGE=255
        self.IMAGE_ARRAY_TYPE='uint8'

        self.wnd = uic.loadUi(os.path.join(paths.UI_PATH,'main.ui'))
        self.dlg = uic.loadUi(os.path.join(paths.UI_PATH,'option_dialog.ui'))
        self.about_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'about_dialog.ui'))
        
        self.currentWidth=0
        self.currentHeight=0
        self.currentDepht=0
        
        self.result_w=0
        self.result_h=0
        self.resut_d=3
        
        self.current_project_fname=None
        
        self.average_save_file=os.path.join(paths.TEMP_PATH,'average.tiff')       
        self.master_dark_save_file=os.path.join(paths.TEMP_PATH,'master-dark.tiff')
        self.master_flat_save_file=os.path.join(paths.TEMP_PATH,'master-flat.tiff')

        self.master_dark_mul_factor=1.0
        self.master_flat_mul_factor=1.0
        
        self.elab_prefix = 'elab_'
        
        self.filelist=[]
        self.offsetlist=[]
        self.darkfilelist=[]
        self.flatfilelist=[]
        
        self.alignpointlist=[]

        self.tracking_align_point=False
        
        self.current_cap_device=cv2.VideoCapture(None)
        self.video_writer = cv2.VideoWriter()
        self.video_url=''
        self.writing=False
        self.captured_frames=0
        self.max_captured_frames=0
        self.current_cap_device_idx=-1
        self.save_image_dir=os.path.join(os.path.expandvars('$HOME'),'Pictures',paths.PROGRAM_NAME.lower())
        self.current_cap_combo_idx=-1
        self.devices=[]
        self.device_propetyes=None
        self.format=0
        self.fps=0
        self.resolution=0
        self.exposure_type=0
        self.exposure=0
        self.gain=0
        self.contrast=0
        self.brightness=0
        self.saturation=0
        self.hue=0
        self.max_points=200
        self.min_quality=0.20
        
        self.statusLabelMousePos = Qt.QLabel()
        self.statusBar = self.wnd.statusBar()
        self.setUpStatusBar()
        self.imageLabel= Qt.QLabel()
        self.imageLabel.setMouseTracking(True)
        self.imageLabel.setAlignment(QtCore.Qt.AlignTop)
        self.wnd.imageViewer.setWidget(self.imageLabel)
        self.wnd.imageViewer.setAlignment(QtCore.Qt.AlignTop)
        
        self.align_methon=True
        
        self.wnd.manualAlignGroupBox.setEnabled(False)
        
        # resize callback
        self.wnd.__resizeEvent__= self.wnd.resizeEvent #base implementation
        self.wnd.resizeEvent = self.mainWindowResizeEvent #new callback
        
        # mousemove callback
        self.imageLabel.__mouseMoveEvent__= self.imageLabel.mouseMoveEvent #base implementation
        self.imageLabel.mouseMoveEvent = self.imageLabelMouseMoveEvent #new callback
        
        self.imageLabel.__mousePressEvent__ = self.imageLabel.mousePressEvent
        self.imageLabel.mousePressEvent = self.imageLabelMousePressEvent
        
        self.imageLabel.__mouseReleaseEvent__ = self.imageLabel.mouseReleaseEvent
        self.imageLabel.mouseReleaseEvent = self.imageLabelMouseReleaseEvent
        
        # paint callback
        self.imageLabel.__paintEvent__= self.imageLabel.paintEvent #base implementation
        self.imageLabel.paintEvent = self.imageLabelPaintEvent #new callback        

        # exit callback
        self.wnd.__closeEvent__= self.wnd.closeEvent #base implementation
        self.wnd.closeEvent = self.mainWindowCloseEvent #new callback        


        self.wnd.alignGroupBox.setEnabled(False)
        self.wnd.exposureGroupBox.setEnabled(False)
        self.wnd.manualAlignGroupBox.setEnabled(False)
        self.wnd.masterDarkGroupBox.setEnabled(False)
        self.wnd.masterFlatGroupBox.setEnabled(False)
        self.wnd.masterDarkGroupBox.hide()
        self.wnd.masterFlatGroupBox.hide()
        self.wnd.stopCapturePushButton.hide()
        
        self.wnd.zoomCheckBox.stateChanged.connect(self.setZoomMode)
        self.wnd.zoomSlider.valueChanged.connect(self.signalSliderZoom)
        self.wnd.zoomDoubleSpinBox.valueChanged.connect(self.signalSpinZoom)
        self.wnd.addPushButton.released.connect(self.loadFiles)
        self.wnd.remPushButton.released.connect(self.removeImage)
        self.wnd.clrPushButton.released.connect(self.clearList)
        self.wnd.darkAddPushButton.released.connect(self.doAddDarkFiles)
        self.wnd.darkClearPushButton.released.connect(self.doClearDarkList)
        self.wnd.flatAddPushButton.released.connect(self.doAddFlatFiles)
        self.wnd.flatClearPushButton.released.connect(self.doClearFlatList)
        self.wnd.listCheckAllBtn.released.connect(self.checkAllListItems)
        self.wnd.listUncheckAllBtn.released.connect(self.uncheckAllListItems)
        self.wnd.alignDeleteAllPushButton.released.connect(self.clearAlignPoinList)
        self.wnd.darkClearPushButton.released.connect(self.clearDarkList)
        self.wnd.listWidget.currentRowChanged.connect(self.listItemChanged)
        self.wnd.listWidgetManualAlign.currentRowChanged.connect(self.manualAlignListItemChanged)
        self.wnd.listWidgetManualAlign.itemChanged.connect(self.currentManualAlignListItemChanged)
        self.wnd.alignPointsListWidget.currentRowChanged.connect(self.alignListItemChanged)
        self.wnd.avrPushButton.released.connect(self.average)
        self.wnd.toolBox.currentChanged.connect(self.updateToolBox)
        self.wnd.spinBoxXAlign.valueChanged.connect(self.shiftX)
        self.wnd.spinBoxYAlign.valueChanged.connect(self.shiftY)
        self.wnd.spinBoxOffsetX.valueChanged.connect(self.shiftOffsetX)
        self.wnd.spinBoxOffsetY.valueChanged.connect(self.shiftOffsetY)
        self.wnd.addPointPushButton.released.connect(self.addAlignPoint)
        self.wnd.removePointPushButton.released.connect(self.removeAlignPoint)
        self.wnd.alignPushButton.released.connect(self.__align__)
        self.wnd.saveResultPushButton.released.connect(self.saveResult)
        self.wnd.exposureSlider.valueChanged.connect(self.signalSliderExp)
        self.wnd.exposureDoubleSpinBox.valueChanged.connect(self.signalSpinExp)
        self.wnd.expAvgPushButton.released.connect(self.setExpAvg)
        self.wnd.expSumPushButton.released.connect(self.setExpSum)
        self.wnd.expNrmPushButton.released.connect(self.setExpNrm)
        self.wnd.autoSetPushButton.released.connect(self.autoSetAlignPoint)
        self.wnd.autoDetectPushButton.released.connect(self.autoDetectAlignPoins)
        self.wnd.masterDarkCheckBox.stateChanged.connect(self.useMasterDark)
        self.wnd.masterFlatCheckBox.stateChanged.connect(self.useMasterFlat)
        self.wnd.masterDarkPushButton.released.connect(self.loadMasterDark)
        self.wnd.masterFlatPushButton.released.connect(self.loadMasterFlat)
        self.wnd.stopCapturePushButton.released.connect(self.stopped)
        self.wnd.capturePushButton.released.connect(self.started)
        self.wnd.singleShotPushButton.released.connect(self.oneShot)
        self.wnd.captureGroupBox.toggled.connect(self.capture)
        self.wnd.darkMulDoubleSpinBox.valueChanged.connect(self.setDarkMul)
        self.wnd.flatMulDoubleSpinBox.valueChanged.connect(self.setFlatMul)
        
        self.dlg.devComboBox.currentIndexChanged.connect(self.getDeviceInfo)
        self.dlg.videoSaveDirPushButton.released.connect(self.__set_save_video_dir)
        self.dlg.formatComboBox.currentIndexChanged.connect(self.deviceFormatChanged)
        self.dlg.resolutionComboBox.currentIndexChanged.connect(self.deviceResolutionChanged)
        self.dlg.fpsComboBox.currentIndexChanged.connect(self.deviceFpsChanged)
        self.dlg.expTypeComboBox.currentIndexChanged.connect(self.deviceExposureTypeChanged)
        self.dlg.expSlider.valueChanged.connect(self.deviceExposureChanged)
        self.dlg.gainSlider.valueChanged.connect(self.deviceGainChanged)
        self.dlg.contrastSlider.valueChanged.connect(self.deviceContrastChanged)
        self.dlg.brightnessSlider.valueChanged.connect(self.deviceBrightnessChanged)
        self.dlg.saturationSlider.valueChanged.connect(self.deviceSaturationChanged)
        self.dlg.hueSlider.valueChanged.connect(self.deviceHueChanged)
        self.dlg.sharpSlider.valueChanged.connect(self.deviceSharpnessChanged)
        self.dlg.gammaSlider.valueChanged.connect(self.deviceGammaChanged)
        
        QtCore.QObject.connect(self.wnd.actionOpen_files, QtCore.SIGNAL("activated()"), self.loadFiles)
        QtCore.QObject.connect(self.wnd.actionOpen_video, QtCore.SIGNAL("activated()"), self.loadVideo)
        QtCore.QObject.connect(self.wnd.actionNew_project, QtCore.SIGNAL("activated()"), self.doNewProject)
        QtCore.QObject.connect(self.wnd.actionSave_project_as, QtCore.SIGNAL("activated()"), self.doSaveProjectAs)
        QtCore.QObject.connect(self.wnd.actionSave_project, QtCore.SIGNAL("activated()"), self.doSaveProject)
        QtCore.QObject.connect(self.wnd.actionLoad_project, QtCore.SIGNAL("activated()"), self.doLoadProject)
        QtCore.QObject.connect(self.wnd.actionPreferences, QtCore.SIGNAL("activated()"), self.doSetPreferences)
        QtCore.QObject.connect(self.wnd.actionAbout, QtCore.SIGNAL("activated()"), self.about_dlg.exec_)
        QtCore.QObject.connect(self.wnd.actionUserManual, QtCore.SIGNAL("activated()"), self.showUserMan)

        self.__resetPreferencesDlg()
                    
        if not os.path.isdir(self.save_image_dir):
            os.makedirs(self.save_image_dir)

    def showUserMan(self):
        webbrowser.open(os.path.join(paths.DOCS_PATH,'usermanual.html'))

    def lock(self):
        self.progress.show()
        self.cancelProgress.show()
        self.wnd.toolBox.setEnabled(False)
        self.wnd.MainFrame.setEnabled(False)
        self.wnd.menubar.setEnabled(False)
        
    def unlock(self):
        self.progress.hide()
        self.cancelProgress.hide()
        self.progress.reset()
        self.wnd.toolBox.setEnabled(True)
        self.wnd.MainFrame.setEnabled(True)
        self.wnd.menubar.setEnabled(True)

    def setDarkMul(self,val):
        self.master_dark_mul_factor=val
        
    def setFlatMul(self,val):
        self.master_flat_mul_factor=val

    def __resetPreferencesDlg(self):
        idx=self.dlg.langComboBox.findData(self.__current_lang)
        self.dlg.langComboBox.setCurrentIndex(idx)

        self.dlg.devComboBox.setCurrentIndex(self.current_cap_combo_idx)

        self.dlg.rWSpinBox.setValue(self.autoalign_rectangle[0])
        self.dlg.rHSpinBox.setValue(self.autoalign_rectangle[1])

        self.dlg.maxPointsSpinBox.setValue(self.max_points)
        self.dlg.minQualityDoubleSpinBox.setValue(self.min_quality)

        self.dlg.langFileLineEdit.setText(self.__current_lang)
        self.dlg.videoSaveLineEdit.setText(self.save_image_dir)
        
        self.dlg.wholeImageCheckBox.setChecked(self.auto_align_use_whole_image)
        
    def __set_save_video_dir(self):
        self.save_image_dir = str(Qt.QFileDialog.getExistingDirectory(self.dlg,tr("Choose the detination folder"),self.save_image_dir))
        self.dlg.videoSaveLineEdit.setText(self.save_image_dir)
        
    def doSetPreferences(self):

        qtr = Qt.QTranslator()
        self.dlg.langComboBox.clear()
        for qmf in os.listdir(paths.LANG_PATH):
            fl = os.path.join(paths.LANG_PATH,qmf)
            if qtr.load(fl):
                self.dlg.langComboBox.addItem(qmf,fl)
        self.__resetPreferencesDlg()

        v4l2_ctl = subprocess.Popen(['v4l2-ctl', '--list-devices'], stdout=subprocess.PIPE)
        v4l2_ctl.wait()
        data = v4l2_ctl.stdout.read().split('\n')[:-1]
        del v4l2_ctl

        #OpenCV cannot list devices yet!
        self.dlg.devComboBox.clear()
        self.devices=[]
        for x in range(0,len(data),3):
            name=data[x]
            dev=data[x+1].replace(' ','').replace('\t','')
            idx = int(data[x+1][data[x+1].find('video')+5:])
            self.devices.append({'name':name,'dev':dev,'id':idx})
            self.dlg.devComboBox.addItem(name)

        if self.current_cap_combo_idx < 0:
            self.current_cap_combo_idx=0

        self.dlg.devComboBox.setCurrentIndex(self.current_cap_combo_idx)

        if self.isPreviewing:
            current_tab_idx=self.dlg.tabWidget.currentIndex()
            self.dlg.tabWidget.setCurrentIndex(2)
            self.dlg.show()
            return True
        else:
           pass
            
        if self.dlg.exec_() == 1:
            r_w=int(self.dlg.rWSpinBox.value())
            r_h=int(self.dlg.rHSpinBox.value())
            self.max_points=int(self.dlg.maxPointsSpinBox.value())
            self.min_quality=float(self.dlg.minQualityDoubleSpinBox.value())
            self.autoalign_rectangle=(r_w, r_h)
            self.save_image_dir = str(self.dlg.videoSaveLineEdit.text())
            self.saveSettings()
            self.current_cap_combo_idx=int(self.dlg.devComboBox.currentIndex())
            self.current_cap_device_idx=self.devices[self.current_cap_combo_idx]['id']
            self.auto_align_use_whole_image=int(self.dlg.wholeImageCheckBox.checkState())
            return True
        else:
            self.__resetPreferencesDlg()
            return False
            
    def getDeviceInfo(self,idx):
        if idx >= 0:

            if not self.isPreviewing:
                i=self.devices[self.current_cap_combo_idx]['id']
                self.current_cap_device.open(i)
                self.current_cap_device_idx=i
            else:
                pass
                       
            if self.current_cap_device.isOpened():
                self.device_propetyes=utils.getV4LDeviceProperties(self.devices[idx]['dev'])

                w = int(self.current_cap_device.get(3))
                h = int(self.current_cap_device.get(4))
                self.resolution=str(w)+'x'+str(h)

                #setting up control interface
                keys=self.device_propetyes['formats'].keys()
                keys.sort()
                self.format=self._setParamMenu(self.dlg.formatComboBox, keys, self.format)

                keys=self.device_propetyes['formats'][self.format].keys()
                keys.sort()

                self.resolution=self._setParamMenu(self.dlg.resolutionComboBox, keys, self.resolution)
                
                keys=self.device_propetyes['formats'][self.format][self.resolution]['fps']
                keys.sort()
                keys.reverse()
                self.fps=self._setParamMenu(self.dlg.fpsComboBox, keys, self.fps)
                
                keys=self.device_propetyes['exposure_auto']['menu'].keys()
                keys.sort()
                self.exposure_type=self._setParamMenu(self.dlg.expTypeComboBox, keys, self.exposure_type)
                
                self._setParamLimits(self.dlg.expSlider,self.dlg.expSpinBox,'exposure_absolute')
                self._setParamLimits(self.dlg.gainSlider,self.dlg.gainSpinBox,'gain')
                self._setParamLimits(self.dlg.gammaSlider,self.dlg.gammaSpinBox,'gamma')
                self._setParamLimits(self.dlg.contrastSlider,self.dlg.contrastSpinBox,'contrast')
                self._setParamLimits(self.dlg.brightnessSlider,self.dlg.brightnessSpinBox,'brightness')
                self._setParamLimits(self.dlg.saturationSlider,self.dlg.saturationSpinBox,'saturation')
                self._setParamLimits(self.dlg.hueSlider,self.dlg.hueSpinBox,'hue')
                self._setParamLimits(self.dlg.sharpSlider,self.dlg.sharpSpinBox,'sharpness')
                        
            if not self.isPreviewing:
                self.current_cap_device.release()
    
    def _setParamMenu(self, combo, keys, def_val):
        combo.clear()
        for i in keys:
            combo.addItem(str(i))
        if (def_val not in keys):
             def_val=keys[combo.currentIndex()]
        else:
             index=combo.findText(def_val)
             combo.setCurrentIndex(index)
        return def_val

    def _setParamLimits(self, slider, spin, key):
        if key not in self.device_propetyes:
            slider.setEnabled(False)
            spin.setEnabled(False)
            return False
        else:
            slider.setEnabled(True)
            spin.setEnabled(True)
        keys=self.device_propetyes[key]
        if keys['min']!=None:
            slider.setMinimum(int(keys['min']))
            spin.setMinimum(int(keys['min']))
        if keys['max']!=None:
            slider.setMaximum(int(keys['max']))
            spin.setMaximum(int(keys['max']))
        if keys['value']!=None:
            slider.setValue(int(keys['value']))
            spin.setValue(int(keys['value']))
        elif keys['default']!=None:
            slider.setValue(int(keys['default']))
            spin.setValue(int(keys['default']))             

    def deviceFormatChanged(self,idx):
        if idx>0:
            self.old_format=self.format
            self.format=str(self.dlg.formatComboBox.itemText(idx))
            keys=self.device_propetyes['formats'][self.format].keys()
            keys.sort()
            self.resolution=self._setParamMenu(self.dlg.resolutionComboBox, keys, self.resolution)
            device=self.devices[self.current_cap_combo_idx]['dev']
            _4CC = cv2.cv.FOURCC(*list(self.format[0:4]))
            self.current_cap_devicep.set(cv2.cv.CV_CAP_PROP_FOURCC,_4CC)
            #utils.setV4LFormat(device,'pixelformat='+self.format)
                        
    def deviceResolutionChanged(self, idx):
        if idx>=0:
            self.resolution=str(self.dlg.resolutionComboBox.itemText(idx))
            keys=self.device_propetyes['formats'][self.format][self.resolution]['fps']
            keys.sort()
            keys.reverse()
            self.fps=self._setParamMenu(self.dlg.fpsComboBox, keys, self.fps)
            device=self.devices[self.current_cap_combo_idx]['dev']
            size=self.resolution.split('x')
            self.current_cap_device.set(3,int(size[0]))
            self.current_cap_device.set(4,int(size[1]))

    def deviceFpsChanged(self, idx):
        if idx>=0:
            self.fps=str(self.dlg.fpsComboBox.itemText(idx))
            device=self.devices[self.current_cap_combo_idx]['dev']
            fps = float(self.fps.split(' ')[0])
            self.current_cap_device.set(cv2.cv.CV_CAP_PROP_FPS,fps)
                
    def deviceExposureTypeChanged(self, idx):
        if idx>=0:
            self.exposure_type=str(self.dlg.expTypeComboBox.itemText(idx))
            device=self.devices[self.current_cap_combo_idx]['dev']
            value=self.device_propetyes['exposure_auto']['menu'][self.exposure_type]
            utils.setV4LCtrl(device,'exposure_auto',value)

    def deviceExposureChanged(self, value):
        device=self.devices[self.current_cap_combo_idx]['dev']
        utils.setV4LCtrl(device,'exposure_absolute',value)
        
    def deviceGainChanged(self, value):
        device=self.devices[self.current_cap_combo_idx]['dev']
        utils.setV4LCtrl(device,'gain',value)

    def deviceContrastChanged(self, value):
        device=self.devices[self.current_cap_combo_idx]['dev']
        utils.setV4LCtrl(device,'contrast',value)

    def deviceBrightnessChanged(self, value):
        device=self.devices[self.current_cap_combo_idx]['dev']
        utils.setV4LCtrl(device,'brightness',value)

    def deviceSaturationChanged(self, value):
        device=self.devices[self.current_cap_combo_idx]['dev']
        utils.setV4LCtrl(device,'saturation',value)
        
    def deviceHueChanged(self, value):
        device=self.devices[self.current_cap_combo_idx]['dev']
        utils.setV4LCtrl(device,'hue',value)
        
    def deviceSharpnessChanged(self, value):
        device=self.devices[self.current_cap_combo_idx]['dev']
        utils.setV4LCtrl(device,'sharpness',value)
        
    def deviceGammaChanged(self, value):
        device=self.devices[self.current_cap_combo_idx]['dev']
        utils.setV4LCtrl(device,'gamma',value)
        
    def capture(self, enabled=False, origin=None):
        
        if (not enabled) and self.current_cap_device.isOpened():
            self.wasCanceled=True
            return
        elif not enabled:
            self.wasCanceled=False
            return

        if origin == None:
            if ((self.current_cap_device_idx == -1) or
                (self.save_image_dir==None)):
                current_tab_idx=self.dlg.tabWidget.currentIndex()
                self.dlg.tabWidget.setCurrentIndex(2)
                if not self.doSetPreferences():
                    self.current_cap_device_idx = -1
                    self.wnd.captureGroupBox.setChecked(False)
                    msgBox = Qt.QMessageBox(self.wnd)
                    msgBox.setText(tr("No capture device selected"))
                    msgBox.setIcon(Qt.QMessageBox.Critical)
                    msgBox.exec_()
                    return False
                self.dlg.tabWidget.setCurrentIndex(current_tab_idx)
            self.current_cap_device.open(self.current_cap_device_idx)
        else:
            pass

        if self.current_cap_device.isOpened():
            self.isPreviewing = True
            self._photo_time_clock=time.clock()
            while(not(self.wasCanceled)):
                self.qapp.processEvents()
                img = self.current_cap_device.read()
                if (img[0]==True):
                    self.__processCaptured(img[1])
                    if self.shooting:
                        self.shooting=False
                        if self._dismatchMsgBox(img[1]):
                            continue
                        ftime=time.strftime('%Y%m%d%H%M%S')
                        mstime='{0:05d}'.format(int((time.clock()-self._photo_time_clock)*100))
                        name=os.path.join(self.save_image_dir,ftime+mstime+'.tiff')
                        self.filelist.append(name)
                        self.alignpointlist.append([])
                        self.offsetlist.append([0,0])
                    
                        q=Qt.QListWidgetItem(os.path.basename(name),self.wnd.listWidget)
                        q.setCheckState(2)
                        q.setToolTip(name)
                        self.wnd.listWidget.setCurrentItem(q)
                        cv2.imwrite(name,img[1])
                        self._unlock_cap_ctrls()

                del img
            self.updateImage()
            self.isPreviewing = False
            self.wasCanceled=False
            self.current_cap_device.release()
        else:
            msgBox = Qt.QMessageBox(self.wnd)
            if origin == None:
                msgBox.setText(tr("Cannot open current capture device!"))
            else:
                msgBox.setText(tr("Cannot open this video file."))
            msgBox.setIcon(Qt.QMessageBox.Critical)
            msgBox.exec_()
            return False
                    
    def _unlock_cap_ctrls(self):
        self.wnd.remPushButton.setEnabled(True)
        self.wnd.clrPushButton.setEnabled(True)
        self.wnd.listCheckAllBtn.setEnabled(True)
        self.wnd.listUncheckAllBtn.setEnabled(True)
        self.wnd.darkAddPushButton.setEnabled(True)
        self.wnd.flatAddPushButton.setEnabled(True)
        self.wnd.masterDarkCheckBox.setEnabled(True)
        self.wnd.masterFlatCheckBox.setEnabled(True)
        
    def _dismatchMsgBox(self,img):
        imw = img.shape[1]
        imh = img.shape[0]

        if len(img[1].shape)==2:
            dep='L'
        elif img[1].shape[-1]==3:
            dep='RGB'
        else:
            dep='RGBA'  
        if len(self.filelist)>0:
            if((imw != self.currentWidth) or
               (imh != self.currentHeight) or
               (dep != self.currentDepht[0:3])):
                msgBox = Qt.QMessageBox(self.wnd)
                msgBox = Qt.QMessageBox(self.wnd)
                msgBox.setText(tr("Frame size or number of channels does not match.\n"))
                msgBox.setInformativeText(tr('current size=')+
                    str(self.currentWidth)+'x'+str(self.currentHeight)+
                    tr(' image size=')+
                    str(imw)+'x'+str(imh)+'\n'+
                    tr('current channels=')+str(self.currentDepht)+
                    tr(' image channels=')+str(dep)
                                     )
                msgBox.setIcon(Qt.QMessageBox.Critical)
                msgBox.exec_()
                return True
            else:
                return False
        else:
            self.currentWidth=imw
            self.currentHeight=imh
            self.currentDepht=dep
            return False
            
    def oneShot(self):
        self.shooting=True
                        
    def __processCaptured(self, img):
        self.showImage(utils.arrayToQImage(img,2,1,0))
        if self.wasStarted:
            self.wnd.stopCapturePushButton.show()
            self.wnd.capturePushButton.hide()
            self.wnd.listWidget.setEnabled(False)
            if not self.wasStopped:
                if not self.writing:
                    self.video_url = os.path.join(self.save_image_dir,time.strftime('%Y-%m-%d@%H:%M:%S'))
                    self.wnd.singleShotPushButton.setEnabled(False)
                    self.captured_frames=0
                    self.writing=True
                    self.max_captured_frames=self.wnd.frameCountSpinBox.value()
                    
                    if self._dismatchMsgBox(img):
                        self.stopped()
                        return False

                    if not (os.path.isdir(self.video_url)):
                        os.makedirs(self.video_url)
                        
                    self.wnd.maxCapturedCheckBox.setEnabled(False)
                    self.wnd.singleShotPushButton.setEnabled(False)
                else:
                    self.captured_frames+=1
                    
                    name=os.path.join(self.video_url,'#{0:05d}'.format(self.captured_frames)+'.tiff')
                    
                    self.filelist.append(name)
                    self.alignpointlist.append([])
                    self.offsetlist.append([0,0])
                    
                    q=Qt.QListWidgetItem(os.path.basename(name),self.wnd.listWidget)
                    q.setCheckState(2)
                    q.setToolTip(name)
                    self.wnd.listWidget.setCurrentItem(q)
                    cv2.imwrite(name,img)
                    
                    if(self.wnd.maxCapturedCheckBox.checkState()==2):
                        self.max_captured_frames-=1
                        if self.max_captured_frames <= 0:
                            self.stopped()
                        elif self.captured_frames%5==0:
                            self.wnd.frameCountSpinBox.setValue(self.max_captured_frames)
                    elif self.captured_frames%5==0:
                        self.wnd.frameCountSpinBox.setValue(self.captured_frames)

            else:
                self.writing=False
                self.wnd.singleShotPushButton.setEnabled(True)
                self.wnd.maxCapturedCheckBox.setEnabled(True)
                self.wnd.singleShotPushButton.setEnabled(True)
                self.wnd.stopCapturePushButton.hide()
                self.wnd.capturePushButton.show()
                self.wnd.listWidget.setEnabled(True)
                self.wasStarted=False
                if (len(self.filelist)>0):
                    self.wnd.frameCountSpinBox.setValue(self.captured_frames)
                    self.wnd.listWidget.setCurrentRow(0)
                    self._unlock_cap_ctrls()
            
    def setExpAvg(self):
        self.setExp(self._avg[1])
        
    def setExpSum(self):
        self.setExp(1)
        
    def setExpNrm(self):
        exp = self._avg[0].max()/self.IMAGE_RANGE
        self.setExp(exp)
        
    def setExp(self,exp):
        self.exposure=exp
        self.wnd.exposureDoubleSpinBox.setValue(self.exposure)
        self.wnd.exposureSlider.setValue(Int(self.exposure*100))

    def useMasterDark(self,state):        
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
        open_str=tr("All supported images")+self.images_extensions+";;"+tr("All files *.* (*.*)")
        master_dark_file = str(Qt.QFileDialog.getOpenFileName(self.wnd,
                                                              tr("Select master-dark file"),
                                                              self.current_dir,
                                                              open_str
                                                              )
                              )
        if os.path.isfile(master_dark_file):
           try:
               i = Image.open(master_dark_file)
               imw,imh=i.size
               dep = i.mode
               if ((self.currentWidth == imw) and
                   (self.currentHeight == imh) and
                   (self.currentDepht == dep)):
                   self.master_dark_file=master_dark_file
                   self.wnd.masterDarkLineEdit.setText(self.master_dark_file)
               else:
                   msgBox = Qt.QMessageBox(self.wnd)
                   msgBox.setText(tr("Cannot use this file:")+tr(" size or number of channels does not match!"))
                   msgBox.setInformativeText(tr('current size=')+
                                        str(self.currentWidth)+'x'+str(self.currentHeight)+
                                        tr(' image size=')+
                                        str(imw)+'x'+str(imh)+'\n'+
                                        tr('current channels=')+str(self.currentDepht)+
                                        tr(' image channels=')+str(dep)
                                                     )
                   msgBox.setIcon(Qt.QMessageBox.Critical)
                   msgBox.exec_()
               del i
           except Exception as exc:
               msgBox = Qt.QMessageBox(self.wnd)
               msgBox.setText(tr("Error:"))
               msgBox.setInformativeText(str(exc))
               msgBox.setIcon(Qt.QMessageBox.Critical)
               msgBox.exec_()
            
    def useMasterFlat(self,state):        
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
        open_str=tr("All supported images")+self.images_extensions+";;"+tr("All files *.* (*.*)")
        master_flat_file = str(Qt.QFileDialog.getOpenFileName(self.wnd,
                                                              tr("Select master-flatfield file"),
                                                              self.current_dir,
                                                              open_str
                                                              )
                              )
        if os.path.isfile(master_flat_file):
           try:
               i = Image.open(master_flat_file)
               imw,imh=i.size
               dep = i.mode
               if ((self.currentWidth == imw) and
                   (self.currentHeight == imh) and
                   (self.currentDepht == dep)):
                   self.master_flat_file=master_flat_file
                   self.wnd.masterFlatLineEdit.setText(self.master_flat_file)
               else:
                   msgBox = Qt.QMessageBox(self.wnd)
                   msgBox.setText(tr("Cannot use this file:"))
                   msgBox.setInformativeText(tr("Size or number of channels does not match!"))
                   msgBox.setInformativeText(tr('current size=')+
                                        str(self.currentWidth)+'x'+str(self.currentHeight)+
                                        tr(' image size=')+
                                        str(imw)+'x'+str(imh)+'\n'+
                                        tr('current channels=')+str(self.currentDepht)+
                                        tr(' image channels=')+str(dep)
                                                     )
                   msgBox.setIcon(Qt.QMessageBox.Critical)
                   msgBox.exec_()
               del i
           except Exception as exc:
               msgBox = Qt.QMessageBox(self.wnd)
               msgBox.setText(tr("Error:"))
               msgBox.setInformativeText(tr(str(exc)))
               msgBox.setIcon(Qt.QMessageBox.Critical)
               msgBox.exec_()
        
    #closeEvent callback
    def mainWindowCloseEvent(self, event):
        msgBox = Qt.QMessageBox(self.wnd)
        msgBox.setText(tr("Do you really want to quit?"))
        msgBox.setInformativeText(tr("All unsaved changes will be lost!"))
        msgBox.setIcon(Qt.QMessageBox.Question)
        msgBox.setStandardButtons(Qt.QMessageBox.Yes | Qt.QMessageBox.No)
        val = msgBox.exec_()
        if val == Qt.QMessageBox.Yes:
            self.stopped()
            self.canceled()
            self.saveSettings()
            if os.path.exists(paths.TEMP_PATH):
                shutil.rmtree(paths.TEMP_PATH)
            return self.wnd.__closeEvent__(event)
        elif val == Qt.QMessageBox.No:
            event.ignore()
        else:
            return self.wnd.__closeEvent__(event)
    
    def saveSettings(self):
        settings = Qt.QSettings()

        settings.beginGroup("mainwindow")
        settings.setValue("geometry", self.wnd.saveGeometry())
        settings.setValue("window_state", self.wnd.saveState())
        settings.endGroup()
        
        settings.beginGroup("options");
        qpoint=Qt.QPoint(self.autoalign_rectangle[0],self.autoalign_rectangle[1])
        settings.setValue("autoalign_rectangle", qpoint)
        settings.setValue("max_align_points",self.max_points)
        settings.setValue("min_point_quality",self.min_quality)
        settings.endGroup()
        
        settings.beginGroup("settings")
        if self.dlg.useCustomLangCheckBox.checkState()==2:
            self.__current_lang = str(self.dlg.langFileLineEdit.text())
            settings.setValue("custom_language",2)
        else:
            idx=self.dlg.langComboBox.currentIndex()
            settings.setValue("custom_language",0)
            if idx >= 0:
                lang=self.dlg.langComboBox.itemData(idx)
                if type(lang) == Qt.QVariant:
                    self.__current_lang = str(lang.toString())
                else:
                    self.__current_lang = str(lang)
        settings.setValue("language_file",self.__current_lang)
        settings.setValue("images_save_dir",self.save_image_dir)
        settings.endGroup()
        

    def loadSettings(self):
        settings = Qt.QSettings()
    
        settings.beginGroup("mainwindow");
        val=settings.value("geometry",None,QtCore.QByteArray)
        self.wnd.restoreGeometry(val)
        self.wnd.restoreState(settings.value("window_state",None,QtCore.QByteArray))
        settings.endGroup()
        settings.beginGroup("options");
        point=settings.value("autoalign_rectangle",None,Qt.QPoint)
        self.autoalign_rectangle=(point.x(),point.y())
        settings.endGroup()
        
        settings.beginGroup("settings");
        self.__current_lang = str(settings.value("language_file",None,str))
        customChkState=int(settings.value("custom_language",None,int))
        self.dlg.useCustomLangCheckBox.setCheckState(customChkState)
        self.save_image_dir = str(settings.value("images_save_dir",None,str))
        self.max_points=int(settings.value("max_align_points",None,int))
        self.min_quality=float(settings.value("min_point_quality",None,float))
        settings.endGroup()

    ##resizeEvent callback
    def mainWindowResizeEvent(self, event):
        val = self.wnd.__resizeEvent__(event)# old implementation
        if self.zoom_fit:
            self.updateImage()            
        return val

    #mouseMoveEvent callback    
    def imageLabelMouseMoveEvent(self, event):
        val = self.imageLabel.__mouseMoveEvent__(event)
        x=Int(event.x()/self.actual_zoom)
        y=Int(event.y()/self.actual_zoom)
        self.statusLabelMousePos.setText(str(x)+','+str(y))
        if (self.tracking_align_point and 
            (self.image_idx>=0) and 
            (self.point_idx>=0)
           ):
            self.alignpointlist[self.image_idx][self.point_idx][0]=x
            self.alignpointlist[self.image_idx][self.point_idx][1]=y
            self.wnd.spinBoxXAlign.setValue(x)
            self.wnd.spinBoxYAlign.setValue(y)
            self.imageLabel.repaint()
        return val
    
    def imageLabelMousePressEvent(self, event):
        val = self.imageLabel.__mousePressEvent__(event)
        btn=event.button()
        if btn==2:
            self.tracking_align_point=True
        return val
    
    def imageLabelMouseReleaseEvent(self, event):
        val = self.imageLabel.__mouseReleaseEvent__(event)
        btn=event.button()
        x=Int(event.x()/self.actual_zoom)
        y=Int(event.y()/self.actual_zoom)
        if btn==2:
            if self.point_idx >= 0:
                self.tracking_align_point=False
                self.alignpointlist[self.image_idx][self.point_idx][0]=x
                self.alignpointlist[self.image_idx][self.point_idx][1]=y
                self.alignpointlist[self.image_idx][self.point_idx][3]=False
                self.wnd.spinBoxXAlign.setValue(x)
                self.wnd.spinBoxYAlign.setValue(y)
                self.imageLabel.repaint()
        return val
    
    #paintEvent callback
    def imageLabelPaintEvent(self, obj):
        val=self.imageLabel.__paintEvent__(obj)
        if self.image_idx<0:
            return val
        painter = Qt.QPainter(self.imageLabel)
        if (not self.manual_align):
            self.__draw_align_points__(painter)
        else:
            self.__draw_difference__(painter)
        del painter
        return val

    def __draw_align_points__(self, painter):
        if(len(self.alignpointlist)) is 0:
            return False
        painter.setFont(Qt.QFont("Arial", 8))            
        for i in self.alignpointlist[self.image_idx]:
            x=Int((i[0]+0.5)*self.actual_zoom)
            y=Int((i[1]+0.5)*self.actual_zoom)
            painter.setCompositionMode(28)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtCore.Qt.white)
            painter.drawEllipse(x-7,y-7,14,14)
            painter.drawLine(x-10,y,x-4,y)
            painter.drawLine(x+4,y,x+10,y)
            painter.drawLine(x,y-10,x,y-4)
            painter.drawLine(x,y+10,x,y+4)
            painter.setCompositionMode(0)
            rect=Qt.QRect(x+8,y+10,45,15)
            painter.setBrush(QtCore.Qt.blue)
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRect(rect)
            painter.setPen(QtCore.Qt.yellow)
            painter.drawText(rect,QtCore.Qt.AlignCenter,i[2])
            rect=Qt.QRect(Int(x-self.autoalign_rectangle[0]*self.actual_zoom/2),
                          Int(y-self.autoalign_rectangle[1]*self.actual_zoom/2),
                          self.autoalign_rectangle[0]*self.actual_zoom,
                          self.autoalign_rectangle[1]*self.actual_zoom)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRect(rect)
            
    def __draw_difference__(self,painter):
        if (self.ref_image != None) and (self.current_image != None):
            painter.drawPixmap(0,0,self.updateImage(False,self.ref_image))
            painter.setCompositionMode(22)
            x = (self.offsetlist[self.dif_image_idx][0]-self.offsetlist[self.ref_image_idx][0])*self.actual_zoom
            y = (self.offsetlist[self.dif_image_idx][1]-self.offsetlist[self.ref_image_idx][1])*self.actual_zoom
            painter.drawPixmap(-x,-y,self.updateImage(False))
            painter.setCompositionMode(0)
    
    def setZoomMode(self, val):
        if val is 0:
            self.wnd.zoomCheckBox.setText(tr('zoom: none'))
            self.wnd.zoomSlider.setEnabled(False)
            self.wnd.zoomDoubleSpinBox.setEnabled(False)
            self.zoom_enabled=False
            self.zoom_fit=False
        elif val is 1:
            self.wnd.zoomCheckBox.setText(tr('zoom: fit'))
            self.zoom_enabled=False
            self.zoom_fit=True
        else:
            self.wnd.zoomCheckBox.setText(tr('zoom: full'))
            self.wnd.zoomSlider.setEnabled(True)
            self.wnd.zoomDoubleSpinBox.setEnabled(True)
            self.zoom_enabled=True
            self.zoom_fit=False
        self.updateImage()
    
    def setZoom(self,zoom):
        self.zoom=zoom
        self.wnd.zoomDoubleSpinBox.setValue(self.zoom)
        self.wnd.zoomSlider.setValue(Int(self.zoom*100))
        
    def signalSliderZoom(self, value, update=False):
        self.zoom=(value/100.0)
        self.wnd.zoomDoubleSpinBox.setValue(self.zoom)
        if update:
            self.updateImage()

    def signalSpinZoom(self, value, update=True):
        self.zoom=value
        self.wnd.zoomSlider.setValue(Int(self.zoom*100))
        if update:
            self.updateImage()

    def updateResultImage(self):
        arr = (self._avg[0]/self.exposure).clip(0,255).astype('uint8')
        img = utils.arrayToQImage(arr)
        self.showImage(img)

    def signalSliderExp(self, value, update=False):
        self.exposure=(value/100.0)
        self.wnd.exposureDoubleSpinBox.setValue(self.exposure)
        if update:
            self.updateResultImage()

    def signalSpinExp(self, value, update=True):
        self.exposure=value
        self.wnd.exposureSlider.setValue(Int(self.exposure*100))
        if update:
            self.updateResultImage()
        
    def showImage(self, image):
        self.current_image = image
        self.updateImage()
            
    def clearImage(self):
        self.current_image=None
        self.imageLabel.setPixmap(Qt.QPixmap())

    def updateImage(self, paint=True, overrided_image=None):
        
        if overrided_image != None:
            current_image=overrided_image
        else:
            current_image=self.current_image

        if current_image is None:
            return False
        elif self.zoom_enabled:
            pix = Qt.QPixmap.fromImage(current_image.scaled(
                                        Int(current_image.width()*self.zoom),
                                        Int(current_image.height()*self.zoom),
                                        1)
                                      )
            self.actual_zoom=self.zoom
        elif self.zoom_fit:
            imh = current_image.height()
            imw = current_image.width()
            pix = Qt.QPixmap.fromImage(current_image.scaled(
                                        self.wnd.imageViewer.width()-10,
                                        self.wnd.imageViewer.height()-10,
                                        1)
                                      )
            self.actual_zoom=min(float(self.wnd.imageViewer.width()-10)/imw,
                                 float(self.wnd.imageViewer.height()-10)/imh
                                )
                                
            self.wnd.zoomDoubleSpinBox.setValue(self.zoom)
        else:
            pix = Qt.QPixmap.fromImage(current_image)
            self.actual_zoom=1
        if paint:
            self.imageLabel.setPixmap(pix)
        else:
            return pix
    
    def setUpStatusBar(self):      
        self.progress = Qt.QProgressBar()
        self.progress.setRange(0,100)
        self.progress.setMaximumSize(200,16)
        self.cancelProgress=Qt.QPushButton(tr('cancel'))
        self.cancelProgress.released.connect(self.canceled)
        self.statusBar.addPermanentWidget(self.statusLabelMousePos)
        self.statusBar.addPermanentWidget(self.cancelProgress)
        self.statusBar.addPermanentWidget(self.progress)
        self.progress.hide()
        self.cancelProgress.hide()
        self.statusBar.showMessage(tr('Welcome!'))

    def canceled(self):
        self.wasCanceled=True

    def stopped(self):
        self.wasStopped=True

    def started(self):
        self.wasStarted=True
        self.wasStopped=False

    def loadVideo(self):

        oldlist=self.filelist[:]
        oldalignpointlist=self.alignpointlist[:]
        oldoffsetlist=self.offsetlist[:]

        open_str=tr("All files *.* (*.*)")
        vidname=str(Qt.QFileDialog.getOpenFileName(self.wnd,
                                                   tr("Select a video"),
                                                   self.current_dir,
                                                   open_str)
                   )

        if vidname!='':
            video = cv2.VideoCapture(vidname)
            s=video.read()
            if not s[0]:
                return False
            else:
                imh,imw,dpth = s[1].shape
                if dpth == 1:
                    dep = 'L'
                elif dpth == 3:
                    dep = 'RGB'
                elif dpth == 4:
                    dep = 'RGBA'
                else:
                    return False
            if len(self.filelist) > 0:
                if((imw != self.currentWidth) or
                   (imh != self.currentHeight) or
                   (dep != self.currentDepht[0:3])):
                    msgBox = Qt.QMessageBox(self.wnd)
                    msgBox.setText(tr("Frame size or number of channels does not match.\n"))
                    msgBox.setInformativeText(tr('current size=')+
                                        str(self.currentWidth)+'x'+str(self.currentHeight)+
                                        tr(' image size=')+
                                        str(imw)+'x'+str(imh)+'\n'+
                                        tr('current channels=')+str(self.currentDepht)+
                                        tr(' image channels=')+str(dep)
                                                     )
                    msgBox.setIcon(Qt.QMessageBox.Critical)
                    msgBox.exec_()
                    return False
            else:
                self.currentWidth=imw
                self.currentHeight=imh
                self.currentDepht=dep
        else:
            return
        tmp_url=os.path.join(paths.TEMP_PATH,'splitted',os.path.basename(vidname))
        if not os.path.isdir(tmp_url):
            os.makedirs(tmp_url)

        count=0
        total=video.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT)-1
        self.progress.setMaximum(total)
        self.lock()
        
        newlist=[]
        while(count < total) and (not self.wasCanceled):
            count+=1
            self.statusBar.showMessage(tr('Splitting video: frame ')+str(count)+tr(' of ')+str(total))
            self.progress.setValue(count)
            img=video.read()[1]
            imname=os.path.join(tmp_url,'frame-'+'{0:05d}'.format(count)+'.tiff')
            cv2.imwrite(imname,img)
            newlist.append(imname)
            self.qapp.processEvents()
            
        self.unlock()

        self.loadFiles(newlist)
        
        
    def loadFiles(self, newlist=None):

        oldlist=self.filelist[:]
        oldalignpointlist=self.alignpointlist[:]
        oldoffsetlist=self.offsetlist[:]

        if newlist==None:
            open_str=tr("All supported images")+self.images_extensions+";;"+tr("All files *.* (*.*)")
            newlist=list(Qt.QFileDialog.getOpenFileNames(self.wnd,
                                                         tr("Select one or more files"),
                                                         self.current_dir,
                                                         open_str)
                        )
                    
        if len(self.filelist) > 0:
            imw = self.currentWidth
            imh = self.currentHeight
            dep = self.currentDepht[0:3]
        elif len(newlist) > 0:
            ref = Image.open(str(newlist[0]))
            imw,imh = ref.size
            dep = ref.mode
            del ref            
            self.currentWidth=imw
            self.currentHeight=imh
            self.currentDepht=dep
        else:
            return
        
        
        self.current_dir=os.path.dirname(str(newlist[0]))
        
        rejected=''
        
        self.progress.setMaximum(len(newlist))
        self.lock()
        self.statusBar.showMessage(tr('Analizing images, please wait...'))
        count=0
        warnings=False
        listitemslist=[]
        for i in newlist:
            count+=1
            if not (i in self.filelist):    
                img=Image.open(str(i))
                if (imw,imh)!=img.size:
                    warnings=True
                    rejected+=(str(i)+tr(' --> size does not match:')+'\n'+
                                        tr('current size=')+
                                        str(self.currentWidth)+'x'+str(self.currentHeight)+
                                        ' '+tr('image size=')+
                                        str(img.size[0])+'x'+str(img.size[1])+'\n')
                elif not(dep in img.mode):
                    warnings=True
                    rejected+=(str(i)+tr(' --> number of channels does not match:')+'\n'+
                                        tr('current channels=')+
                                        str(self.currentDepht)+
                                        ' '+tr('image channels=')+
                                        str(img.mode)+'\n')
                else:                    
                    self.filelist.append(str(i))
                    self.alignpointlist.append([])
                    self.offsetlist.append([0,0])
                    q=Qt.QListWidgetItem(os.path.basename(str(i)))
                    q.setCheckState(2)
                    q.setToolTip(i)
                    listitemslist.append(q)
            self.progress.setValue(count)
            if self.progressWasCanceled():
                self.filelist=oldlist=self.filelist
                self.alignpointlist=oldalignpointlist
                self.offsetlist=oldoffsetlist
                return False
        self.unlock()
        for item in listitemslist:
            self.wnd.listWidget.addItem(item)
        newlist=[]

        if warnings:
            msgBox = Qt.QMessageBox(self.wnd)
            msgBox.setText(tr("Some imagese have different sizes or number of channels and will been ignored.\n"))
            msgBox.setInformativeText(tr("All images must have the same size and number of channels.\n\n")+
                                      tr("Click the \'Show Details' button for more information.\n"))
            msgBox.setDetailedText (rejected)
            msgBox.setIcon(Qt.QMessageBox.Warning)
            msgBox.exec_()
            del msgBox

        self.wnd.manualAlignGroupBox.setEnabled(True)
        
        self.darkfilelist=[]
        
        self.dark_dir = os.path.join(self.current_dir,'dark')
        self.statusBar.showMessage(tr('Searching for dark frames, please wait...'))
        if not self.doAddDarkFiles(self.dark_dir):
            pass

        self.flat_dir = os.path.join(self.current_dir,'flat')
        self.statusBar.showMessage(tr('Searching for flatfiled frames, please wait...'))
        if not self.doAddFlatFiles(self.flat_dir):
            pass

        self.statusBar.showMessage(tr('DONE'))
        
        if (len(self.filelist)>0):
            self._unlock_cap_ctrls()

        self.statusBar.showMessage(tr('Ready'))

    def doAddDarkFiles(self, directory=None):
        if directory is None:
            open_str=tr("All supported images")+self.images_extensions+";;"+tr("All files *.* (*.*)")
            files = list(Qt.QFileDialog.getOpenFileNames(self.wnd,
                                                         tr("Select one or more files"),
                                                         self.current_dir,
                                                         open_str)
                        )
        elif os.path.exists(directory) and os.path.isdir(directory):
            files = []
            lst = os.listdir(directory)
            for x in lst:
                files.append(os.path.join(directory,x))
        else:
            return False
            
        for fn in files:
            if (os.path.isfile(fn) and 
               not (fn in self.darkfilelist)):
               try:
                   i = Image.open(fn)
                   imw,imh=i.size
                   dep = i.mode
                   if ((self.currentWidth == imw) and
                       (self.currentHeight == imh) and
                       (self.currentDepht == dep)):
                        self.darkfilelist.append(fn)
                        q=Qt.QListWidgetItem(str(os.path.basename(fn)),self.wnd.darkListWidget)
                        q.setToolTip(str(fn))
                   del i
               except:
                   pass
                
        if (len(self.darkfilelist) == 0):
            return False
        else:
            self.wnd.darkClearPushButton.setEnabled(True)
        return True
        
    def doClearDarkList(self):
        self.darkfilelist=[]
        self.wnd.darkListWidget.clear()
        self.wnd.darkClearPushButton.setEnabled(False)
        
    def doAddFlatFiles(self, directory=None):
        if directory is None:
            open_str=tr("All supported images")+self.images_extensions+";;"+tr("All files *.* (*.*)")
            files = list(Qt.QFileDialog.getOpenFileNames(self.wnd,
                                                         tr("Select one or more files"),
                                                         self.current_dir,
                                                         open_str)
                        )
            
        elif os.path.exists(directory) and os.path.isdir(directory):
            files = []
            lst = os.listdir(directory)
            for x in lst:
                files.append(os.path.join(directory,x))
        else:
            return False
            
        for fn in files:
            if (os.path.isfile(fn) and 
               not (fn in self.darkfilelist)):
               try:
                   i = Image.open(fn)
                   imw,imh=i.size
                   dep = i.mode
                   if ((self.currentWidth == imw) and
                       (self.currentHeight == imh) and
                       (self.currentDepht == dep)):
                        self.flatfilelist.append(fn)
                        q=Qt.QListWidgetItem(str(os.path.basename(fn)),self.wnd.flatListWidget)
                        q.setToolTip(str(fn))
                   del i
               except:
                   pass
                
        if (len(self.flatfilelist) == 0):
            return False
        else:
            self.wnd.flatClearPushButton.setEnabled(True)
        return True

    def doClearFlatList(self):
        self.flatfilelist=[]
        self.wnd.flatListWidget.clear()
        self.wnd.flatClearPushButton.setEnabled(False)

    def clearList(self):
        self.filelist=[]
        self.offsetlist=[]
        self.alignpointlist=[]
            
        self.wnd.listWidget.clear()
        self.wnd.alignPointsListWidget.clear()
        self.wnd.remPushButton.setEnabled(False)
        self.wnd.clrPushButton.setEnabled(False)
        self.wnd.listCheckAllBtn.setEnabled(False)
        self.wnd.listUncheckAllBtn.setEnabled(False)
        self.wnd.avrPushButton.setEnabled(False)
        self.wnd.alignPushButton.setEnabled(False)
        self.wnd.saveResultPushButton.setEnabled(False)
        self.clearImage()

    def removeImage(self):
        q = self.wnd.listWidget.takeItem(self.wnd.listWidget.currentRow())
        self.filelist.pop(self.wnd.listWidget.currentRow())
        self.offsetlist.pop(self.wnd.listWidget.currentRow())
        self.alignpointlist.pop(self.wnd.listWidget.currentRow())
        del q
        
        if (len(self.filelist)==0):
            self.wnd.manualAlignGroupBox.setEnabled(False)
            self.wnd.remPushButton.setEnabled(False)
            self.wnd.clrPushButton.setEnabled(False)
            self.wnd.listCheckAllBtn.setEnabled(False)
            self.wnd.listUncheckAllBtn.setEnabled(False)
            self.clearImage()

    def checkAllListItems(self):
        self.setAllListItemsChechState(2)

    def uncheckAllListItems(self):
        self.setAllListItemsChechState(0)
        
    def clearDarkList(self):
        self.darkfilelist = []
        self.aligned_dark=[]
        
    def clearAlignPoinList(self):
        for i in range(len(self.alignpointlist)):
           self.alignpointlist[i]=[]
        self.wnd.alignPointsListWidget.clear()
        self.wnd.removePointPushButton.setEnabled(False)
        self.updateImage()

    def setAllListItemsChechState(self, state):
        for i in range(self.wnd.listWidget.count()):
            self.wnd.listWidget.item(i).setCheckState(state)

    def listItemChanged(self, idx):
        if self.wasStarted:
            return
        self.image_idx = self.wnd.listWidget.currentRow()
        if idx >= 0:
            self.showImage(Qt.QImage(self.filelist[idx]))
            self.wnd.alignGroupBox.setEnabled(True)
            self.wnd.alignDeleteAllPushButton.setEnabled(True)
            self.updateAlignPointList()
            self.wnd.manualAlignGroupBox.setEnabled(True)
        else:
            self.wnd.alignGroupBox.setEnabled(False)
            self.wnd.alignDeleteAllPushButton.setEnabled(False)
            self.wnd.manualAlignGroupBox.setEnabled(False)
            
    def manualAlignListItemChanged(self,idx):
        item = self.wnd.listWidgetManualAlign.item(idx)
        self.dif_image_idx=item.original_id
        self.current_image=Qt.QImage(self.filelist[item.original_id])
        self.wnd.spinBoxOffsetX.setValue(self.offsetlist[item.original_id][0])
        self.wnd.spinBoxOffsetY.setValue(self.offsetlist[item.original_id][1])
        self.imageLabel.repaint()
                
    def currentManualAlignListItemChanged(self, cur_item):
        if cur_item == None:
            return False
        elif cur_item.checkState()==2:
            if self.__operating!=True:
                self.__operating=True
                self.ref_image_idx=cur_item.original_id
                self.ref_image = Qt.QImage(self.filelist[cur_item.original_id])
                for i in range(self.wnd.listWidgetManualAlign.count()):
                    item = self.wnd.listWidgetManualAlign.item(i)
                    if (item != cur_item) and (item.checkState() == 2):
                        item.setCheckState(0)
                self.__operating=False
                self.imageLabel.repaint()
        elif cur_item.checkState()==0:
            if not self.__operating:
                cur_item.setCheckState(2)


            
    def updateAlignList(self):
        if self.ref_image_idx == -1:
            self.ref_image_idx=0
        self.wnd.listWidgetManualAlign.clear()
        count=0
        self.__operating=True
        for i in range(self.wnd.listWidget.count()):
            if self.wnd.listWidget.item(i).checkState()==2:
                item = self.wnd.listWidget.item(i)
                if item.checkState()==2:
                    q=Qt.QListWidgetItem(item.text(),self.wnd.listWidgetManualAlign)
                    q.original_id=i
                    if i == self.ref_image_idx:
                        q.setCheckState(2)
                    else:
                        q.setCheckState(0)
                    count+=1
        self.__operating=False

    def alignListItemChanged(self, idx):
        self.point_idx=idx
        if idx >= 0:
            self.wnd.spinBoxXAlign.setEnabled(True)
            self.wnd.spinBoxYAlign.setEnabled(True)
            self.wnd.removePointPushButton.setEnabled(True)
            self.wnd.spinBoxXAlign.setValue(self.alignpointlist[self.image_idx][idx][0])
            self.wnd.spinBoxYAlign.setValue(self.alignpointlist[self.image_idx][idx][1])
        else:
            self.wnd.spinBoxXAlign.setEnabled(False)
            self.wnd.spinBoxYAlign.setEnabled(False)
            self.wnd.removePointPushButton.setEnabled(False)
            self.wnd.spinBoxXAlign.setValue(0)
            self.wnd.spinBoxYAlign.setValue(0)
            
    def addAlignPoint(self):
        imagename=self.wnd.listWidget.item(self.image_idx).text()
        idx=1
        for i in range(self.wnd.alignPointsListWidget.count()):
            pname='#{0:05d}'.format(i+1)
            if self.alignpointlist[0][i][2] != pname:
                idx=i+1
                break
            else:
                idx=i+2
                
        pname='#{0:05d}'.format(idx)
        q=Qt.QListWidgetItem(pname)
        q.setToolTip(tr('image') +imagename+tr('\nalign point ')+pname)
        self.wnd.alignPointsListWidget.insertItem(idx-1,q)
        
        if(len(self.alignpointlist[self.image_idx])==0):
            self.wnd.removePointPushButton.setEnabled(True)
            
        for i in range(len(self.alignpointlist)):
           self.alignpointlist[i].insert(idx-1,[0,0,pname,False])

        self.imageLabel.repaint()
        self.wnd.alignPointsListWidget.setCurrentRow(idx-1)
        return (idx-1)
    
    def removeAlignPoint(self):
        point_idx=self.wnd.alignPointsListWidget.currentRow()
        for i in range(len(self.alignpointlist)):
            self.alignpointlist[i].pop(point_idx)
        self.wnd.alignPointsListWidget.setCurrentRow(-1) #needed to avid bugs
        item = self.wnd.alignPointsListWidget.takeItem(point_idx)
        if(len(self.alignpointlist[self.image_idx])==0):
            self.wnd.removePointPushButton.setEnabled(False)
        del item
        self.updateImage()
        
    def updateAlignPointList(self):
        self.wnd.alignPointsListWidget.clear()
        imagename=self.wnd.listWidget.item(self.wnd.listWidget.currentRow()).text()
        for idx in range(len(self.alignpointlist[self.image_idx])):
            pname=self.alignpointlist[self.image_idx][idx][2]
            q=Qt.QListWidgetItem(pname,self.wnd.alignPointsListWidget)
            q.setToolTip(tr('image') +imagename+tr('\nalign point ')+pname)

    def shiftX(self,val):
        if (self.point_idx >= 0):
            self.alignpointlist[self.image_idx][self.point_idx][0]=val
            if self.alignpointlist[self.image_idx][self.point_idx][3]==True:
                self.alignpointlist[self.image_idx][self.point_idx][3]=False
            self.imageLabel.repaint()

    def shiftY(self,val):
        if (self.point_idx >= 0):
            self.alignpointlist[self.image_idx][self.point_idx][1]=val
            if self.alignpointlist[self.image_idx][self.point_idx][3]==True:
                self.alignpointlist[self.image_idx][self.point_idx][3]=False
            self.imageLabel.repaint()

    def shiftOffsetX(self,val):
        if (self.dif_image_idx >= 0):
            self.offsetlist[self.dif_image_idx][0]=val
            self.imageLabel.repaint()
        
    def shiftOffsetY(self,val):
        if (self.dif_image_idx >= 0):
            self.offsetlist[self.dif_image_idx][1]=val
            self.imageLabel.repaint()
            
    def updateToolBox(self, idx):
        self.ref_image_idx=-1
    
        if idx==2:
            self.manual_align=True
            self.updateAlignList()
            if len(self.filelist)>0:
                self.ref_image = Qt.QImage(self.filelist[0])
            self.imageLabel.repaint()
        else:
            self.manual_align=False
            self.imageLabel.repaint()
        
        if (idx==5):
            if (self._avg != None):
                self.wnd.exposureGroupBox.setEnabled(True)
                self.updateResultImage()
            if (len(self.filelist)>0):
                self.wnd.alignPushButton.setEnabled(True)
                self.wnd.avrPushButton.setEnabled(True)

    def doNewProject(self):

        self.zoom = 1
        self.min_zoom = 0
        self.actual_zoom=1
        self.exposure=0
        self.zoom_enabled=False
        self.zoom_fit=False
        self.current_image = None
        self.ref_image=None

        self.image_idx=-1
        self.ref_image_idx=-1
        self.dif_image_idx=-1
        self.point_idx=-1

        self._drk=None
        self._avg=None
        self._flt=None
    
        self.manual_align=False

        self.currentWidth=0
        self.currentHeight=0
        self.currentDepht=0
        
        self.result_w=0
        self.result_h=0
        self.resut_d=3
        
        self.current_project_fname=None

        self.filelist=[]
        self.offsetlist=[]
        self.darkfilelist=[]
        self.flatfilelist=[]
        self.alignpointlist=[]


        self.setZoom(1)
        self.setZoomMode(0)
        self.wnd.zoomCheckBox.setCheckState(0)
        self.wnd.alignPushButton.setEnabled(False)
        self.wnd.avrPushButton.setEnabled(False)
        self.wnd.saveResultPushButton.setEnabled(False)
        self.wnd.exposureGroupBox.setEnabled(False)
        self.wnd.alignGroupBox.setEnabled(False)
        self.wnd.exposureGroupBox.setEnabled(False)
        self.wnd.manualAlignGroupBox.setEnabled(False)
        self.wnd.masterDarkGroupBox.setEnabled(False)
        self.wnd.masterFlatGroupBox.setEnabled(False)
        self.wnd.darkFramesGroupBox.setEnabled(True)
        self.wnd.flatFramesGroupBox.setEnabled(True)
        self.wnd.masterDarkGroupBox.hide()
        self.wnd.masterFlatGroupBox.hide()
        self.wnd.flatFramesGroupBox.show()
        self.wnd.darkFramesGroupBox.show()
        self.wnd.masterDarkCheckBox.setCheckState(0)
        self.wnd.masterFlatCheckBox.setCheckState(0)
        self.wnd.darkMulDoubleSpinBox.setValue(1.0)
        self.wnd.flatMulDoubleSpinBox.setValue(1.0)
        self.clearList()
        self.wnd.darkListWidget.clear()
        self.wnd.flatListWidget.clear()
        
        self.progress.reset()
        self.clearImage()
        
    def doSaveProjectAs(self):
        self.current_project_fname = str(Qt.QFileDialog.getSaveFileName(self.wnd, tr("Save the project"),
                                         os.path.join(self.current_dir,'Untitled.prj'),
                                         "Project (*.prj);;All files (*.*)"))
        if self.current_project_fname == '':
            self.current_project_fname=None
            return
        self.__save_project__()

    def doSaveProject(self):
        if self.current_project_fname is None:
            self.doSaveProjectAs()
        else:
            self.__save_project__()

    def corruptedMsgBox(self,info=None):
            msgBox = Qt.QMessageBox(self.wnd)
            msgBox.setText(tr("Project invalid or corrupted!"))
            if info!=None:
                msgBox.setInformativeText(info)
            msgBox.setIcon(Qt.QMessageBox.Critical)
            msgBox.exec_()
            return False

    def __save_project__(self):
        
        doc = minidom.Document()
        
        root=doc.createElement('project')
        doc.appendChild(root)
        
        information_node = doc.createElement('information')
        dark_frames_node = doc.createElement('dark-frames')
        flat_frames_node = doc.createElement('flat-frames')
        pict_frames_node = doc.createElement('frames')

        root.appendChild(information_node)
        root.appendChild(dark_frames_node)
        root.appendChild(flat_frames_node)
        root.appendChild(pict_frames_node)
        
        #<information> section
        information_node.setAttribute('width',str(int(self.currentWidth)))
        information_node.setAttribute('height',str(int(self.currentHeight)))
        information_node.setAttribute('mode',str(self.currentDepht))
        
        current_dir_node = doc.createElement('current-dir')
        current_row_node = doc.createElement('current-row')
        master_dark_node = doc.createElement('master-dark')
        master_flat_node = doc.createElement('master-flat')
        align_rect_node  = doc.createElement('align-rect')
        max_points_node  = doc.createElement('max-align-points')
        min_quality_node = doc.createElement('min-point-quality')
        
        
        information_node.appendChild(current_dir_node)
        information_node.appendChild(current_row_node)
        information_node.appendChild(master_dark_node)
        information_node.appendChild(master_flat_node)
        information_node.appendChild(align_rect_node)
        information_node.appendChild(max_points_node)
        information_node.appendChild(min_quality_node)
        

        current_dir_node.setAttribute('url',str(self.current_dir))
        current_row_node.setAttribute('index',str(self.image_idx))
        master_dark_node.setAttribute('checked',str(self.wnd.masterDarkCheckBox.checkState()))
        master_dark_node.setAttribute('mul',str(self.master_dark_mul_factor))
        master_flat_node.setAttribute('checked',str(self.wnd.masterDarkCheckBox.checkState()))
        master_flat_node.setAttribute('mul',str(self.master_flat_mul_factor))
        align_rect_node.setAttribute('width',str(self.autoalign_rectangle[0]))
        align_rect_node.setAttribute('height',str(self.autoalign_rectangle[1]))
        align_rect_node.setAttribute('whole-image',str(self.auto_align_use_whole_image))
        max_points_node.setAttribute('value',str(self.max_points))
        min_quality_node.setAttribute('value',str(self.min_quality))

        url=doc.createElement('url')
        master_dark_node.appendChild(url)
        url_txt=doc.createTextNode(str(self.wnd.masterDarkLineEdit.text()))
        url.appendChild(url_txt)
        
        url=doc.createElement('url')
        master_flat_node.appendChild(url)
        url_txt=doc.createTextNode(str(self.wnd.masterFlatLineEdit.text()))
        url.appendChild(url_txt)

        #<dark-frams> section
        for i in range(len(self.darkfilelist)):
            im_dark_name = str(self.wnd.darkListWidget.item(i).text())
            im_dark_url = self.darkfilelist[i]
            image_node = doc.createElement('image')
            image_node.setAttribute('name',im_dark_name)
            
            dark_frames_node.appendChild(image_node)
            
            url=doc.createElement('url')
            image_node.appendChild(url)
            url_txt=doc.createTextNode(im_dark_url)
            url.appendChild(url_txt)

        #<flat-frames> section
        for i in range(len(self.flatfilelist)):
            im_flat_name = str(self.wnd.flatListWidget.item(i).text())
            im_flat_url = self.flatfilelist[i]
            image_node = doc.createElement('image')
            image_node.setAttribute('name',im_flat_name)
            
            flat_frames_node.appendChild(image_node)
            
            url=doc.createElement('url')
            image_node.appendChild(url)
            url_txt=doc.createTextNode(im_flat_url)
            url.appendChild(url_txt)  
            
        #<frames> section
        for i in range(len(self.filelist)):
            im_used = str(self.wnd.listWidget.item(i).checkState())
            im_name = str(self.wnd.listWidget.item(i).text())
            im_url = self.filelist[i]
            image_node = doc.createElement('image')
            image_node.setAttribute('name',im_name)
            image_node.setAttribute('used',im_used)
            
            pict_frames_node.appendChild(image_node)

            for point in self.alignpointlist[i]:
                point_node=doc.createElement('align-point')
                point_node.setAttribute('x',str(int(point[0])))
                point_node.setAttribute('y',str(int(point[1])))
                point_node.setAttribute('id',str(point[2]))
                point_node.setAttribute('aligned',str(point[3]))
                image_node.appendChild(point_node)
            
            offset_node=doc.createElement('offset')
            offset_node.setAttribute('x',str(int(self.offsetlist[i][0])))
            offset_node.setAttribute('y',str(int(self.offsetlist[i][1])))
            image_node.appendChild(offset_node)

            url=doc.createElement('url')
            image_node.appendChild(url)
            url_txt=doc.createTextNode(im_url)
            url.appendChild(url_txt)

        try:
            f = open(self.current_project_fname,'w')
            f.write(doc.toprettyxml(' ','\n'))
            f.close()
        except IOError as err:
            msgBox = Qt.QMessageBox(self.wnd)
            msgBox.setText(tr("Cannot save the project: ")+ str(err))
            msgBox.setInformativeText(tr("Assure you have the permissions to write the file."))
            msgBox.setIcon(Qt.QMessageBox.Critical)
            msgBox.exec_()
            del msgBox
            return

    def doLoadProject(self):
        old_fname = self.current_project_fname
        project_fname = str(Qt.QFileDialog.getOpenFileName(self.wnd,
                                                           tr("Open a project"),
                                                           os.path.join(self.current_dir,'Untitled.prj'),
                                                           "Project (*.prj);;All files (*.*)")
                           )

        if project_fname == '':
            return False

        try:
            dom = minidom.parse(project_fname)
        except Exception as err:
            return self.corruptedMsgBox(err)
        

        try:
            root = dom.getElementsByTagName('project')[0]
            
            information_node = root.getElementsByTagName('information')[0]
            dark_frames_node = root.getElementsByTagName('dark-frames')[0]
            flat_frames_node = root.getElementsByTagName('flat-frames')[0]
            pict_frames_node = root.getElementsByTagName('frames')[0]
            
            current_dir_node = information_node.getElementsByTagName('current-dir')[0]
            current_row_node = information_node.getElementsByTagName('current-row')[0]
            master_dark_node = information_node.getElementsByTagName('master-dark')[0]
            master_flat_node = information_node.getElementsByTagName('master-flat')[0]
            align_rect_node  = information_node.getElementsByTagName('align-rect')[0]
            max_points_node  = information_node.getElementsByTagName('max-align-points')[0]
            min_quality_node = information_node.getElementsByTagName('min-point-quality')[0]

            imw=int(information_node.getAttribute('width'))
            imh=int(information_node.getAttribute('height'))
            dep=information_node.getAttribute('mode')
            
            ar_w=int(align_rect_node.getAttribute('width'))
            ar_h=int(align_rect_node.getAttribute('height'))
            use_whole_image=int(align_rect_node.getAttribute('whole-image'))
            max_points=int(max_points_node.getAttribute('value'))
            min_quality=float(min_quality_node.getAttribute('value'))
                        
            current_dir=current_dir_node.getAttribute('url')
            current_row=int(current_row_node.getAttribute('index'))
            master_dark_checked=int(master_dark_node.getAttribute('checked'))
            master_flat_checked=int(master_flat_node.getAttribute('checked'))
            master_dark_mul_factor=float(master_dark_node.getAttribute('mul'))
            master_flat_mul_factor=float(master_flat_node.getAttribute('mul'))

            try:
                master_dark_url=master_dark_node.getElementsByTagName('url')[0].childNodes[0].data
            except:
                master_dark_url = ''

            try:
                master_flat_url=master_flat_node.getElementsByTagName('url')[0].childNodes[0].data
            except:
                master_flat_url = ''
                        
            darkfilelist=[]
            darkListWidgetElements = []    
            for node in dark_frames_node.getElementsByTagName('image'):
                im_dark_name = node.getAttribute('name')
                im_dark_url = node.getElementsByTagName('url')[0].childNodes[0].data
                q=Qt.QListWidgetItem(im_dark_name,None)
                q.setToolTip(im_dark_url)
                darkListWidgetElements.append(q)
                darkfilelist.append(im_dark_url)
                
            flatfilelist=[]
            flatListWidgetElements = []    
            for node in flat_frames_node.getElementsByTagName('image'):
                im_flat_name = node.getAttribute('name')
                im_flat_url = node.getElementsByTagName('url')[0].childNodes[0].data
                q=Qt.QListWidgetItem(im_flat_name,None)
                q.setToolTip(im_flat_url)
                flatListWidgetElements.append(q)
                flatfilelist.append(im_flat_url)

                
            alignpointlist=[]
            offsetlist=[]
            filelist=[]  
            listWidgetElements=[]
            for node in pict_frames_node.getElementsByTagName('image'):
                im_name = node.getAttribute('name')
                im_used = int(node.getAttribute('used'))
                im_url  = node.getElementsByTagName('url')[0].childNodes[0].data
                alignpointlist.append([])
                for point in node.getElementsByTagName('align-point'):
                    point_id = point.getAttribute('id')
                    point_x  = int(point.getAttribute('x'))
                    point_y  = int(point.getAttribute('y'))
                    point_al = bool(point.getAttribute('aligned')=='True')
                    alignpointlist[-1].append([point_x, point_y, point_id, point_al])
                
                offset_node=node.getElementsByTagName('offset')[0]
                offset_x=float(offset_node.getAttribute('x'))
                offset_y=float(offset_node.getAttribute('y'))
                offsetlist.append([offset_x,offset_y])
                q=Qt.QListWidgetItem(im_name,None)
                q.setToolTip(im_url)
                q.setCheckState(im_used)
                listWidgetElements.append(q)
                filelist.append(im_url)
            
        except Exception as exc:
            self.current_project_fname=old_fname
            return self.corruptedMsgBox()
       
        self.doNewProject()
        
        self.current_project_fname=project_fname
        
        for item in flatListWidgetElements:
            self.wnd.flatListWidget.addItem(item)
            
        for item in darkListWidgetElements:
            self.wnd.darkListWidget.addItem(item)
            
        for item in listWidgetElements:
            self.wnd.listWidget.addItem(item)
        
        
        self.currentWidth=imw
        self.currentHeight=imh
        self.currentDepht=dep
        self.filelist=filelist
        self.darkfilelist=darkfilelist
        self.flatfilelist=flatfilelist
        self.offsetlist=offsetlist
        self.alignpointlist=alignpointlist
        self.image_idx=current_row
        self.master_dark_file=master_dark_url
        self.master_flat_file=master_flat_url
        self.wnd.listWidget.setCurrentRow(current_row)
        self.autoalign_rectangle=(ar_w, ar_h)
        self.max_points=max_points
        self.min_quality=min_quality
        self.auto_align_use_whole_image=use_whole_image
                
        if (len(self.filelist)>0):
            self._unlock_cap_ctrls()

        self.wnd.masterDarkCheckBox.setCheckState(master_dark_checked)
        self.wnd.masterDarkLineEdit.setText(master_dark_url)
        self.wnd.darkMulDoubleSpinBox.setValue(master_dark_mul_factor)
        if (len(self.darkfilelist)>0):
            self.wnd.darkClearPushButton.setEnabled(True)

        self.wnd.masterFlatCheckBox.setCheckState(master_flat_checked)
        self.wnd.masterFlatLineEdit.setText(master_flat_url)
        self.wnd.flatMulDoubleSpinBox.setValue(master_flat_mul_factor)
        if (len(self.flatfilelist)>0):
            self.wnd.flatClearPushButton.setEnabled(True)

    def autoDetectAlignPoins(self):
        i = numpy.array(Image.open(self.filelist[self.image_idx]))
        g = cv2.cvtColor(i,cv2.cv.CV_BGR2GRAY)
        imh,imw=g.shape
        
        del i
        
        rw=self.autoalign_rectangle[0]
        rh=self.autoalign_rectangle[1]
        
        min_dist = int(math.ceil((rw**2+rh**2)**0.5))
        
        points = cv2.goodFeaturesToTrack(g,self.max_points,self.min_quality,min_dist)

        for p in points:
            if ((p[0][0]<rw) or (p[0][1]<rh) or
                ((p[0][0]+rw)>imw) or ((p[0][1]+rh)>imh)):
                    #point is out of bounds
                    continue
            self.point_idx=self.addAlignPoint()
            self.wnd.spinBoxXAlign.setValue(p[0][0])
            self.wnd.spinBoxYAlign.setValue(p[0][1])

    def autoSetAlignPoint(self):
        image_idx=self.wnd.listWidget.currentRow()
        current_point=self.wnd.alignPointsListWidget.currentRow()
        self.statusBar.showMessage(tr('detecting points, please wait...'))
        for point_idx in range(len(self.alignpointlist[image_idx])):
            self.point_idx=point_idx
            if not self.__auto_point_cv__(point_idx, image_idx):
                self.wnd.alignPointsListWidget.setCurrentRow(current_point)
                return False
        self.wnd.alignPointsListWidget.setCurrentRow(current_point)
        self.point_idx=current_point

    def __auto_point_cv__(self, point_idx, image_idx=0):
        point = self.alignpointlist[image_idx][point_idx]


        #if already detected and not moved
        skip=True   
        for i in range(len(self.alignpointlist)):
            skip &= self.alignpointlist[i][point_idx][3]

        #then skip            
        if skip:
            return True

        r_w=Int(self.autoalign_rectangle[0]/2)
        r_h=Int(self.autoalign_rectangle[1]/2)
        x1=point[0]-r_w
        x2=point[0]+r_w
        y1=point[1]-r_h
        y2=point[1]+r_h
        
        rawi = Image.open(self.filelist[image_idx])
        refi = rawi.crop((x1,y1,x2,y2))
        del rawi
        cv_ref = numpy.array(refi)
        del refi
        
        self.progress.setMaximum(len(self.filelist)-1)
        self.lock()
        
        for i in range(len(self.filelist)):
            self.progress.setValue(i)

            if self.progressWasCanceled():
                return False

            self.alignpointlist[i][point_idx][3]=True                

            if i == image_idx:
                continue
            self.statusBar.showMessage(tr('detecting point ')+str(point_idx+1)+tr(' of ')+str(len(self.alignpointlist[image_idx]))+tr(' on image ')+str(i)+tr(' of ')+str(len(self.filelist)-1))
            if self.auto_align_use_whole_image==2:
                rawi=Image.open(self.filelist[i])
            else:
                rawi=Image.open(self.filelist[i]).crop((x1-r_w,y1-r_h,x2+r_w,y2+r_h))
            cv_im=numpy.array(rawi)
            del rawi
            
            min_dif = None
            min_point=(0,0)

            res = cv2.matchTemplate(cv_im,cv_ref,self.current_match_mode)
            minmax = cv2.minMaxLoc(res)
            del res            
            if self.auto_align_use_whole_image==2:
                self.alignpointlist[i][point_idx][0]=minmax[2][0]+r_w
                self.alignpointlist[i][point_idx][1]=minmax[2][1]+r_h
            else:
                self.alignpointlist[i][point_idx][0]=minmax[2][0]+x1
                self.alignpointlist[i][point_idx][1]=minmax[2][1]+y1
            
        self.unlock()
        
        return True

    def average(self):
        dark_image=None
        dark_stdev=None
        
        self.master_dark_file = str(self.wnd.masterDarkLineEdit.text())
        self.master_flat_file = str(self.wnd.masterFlatLineEdit.text())
        
        if (self.wnd.masterDarkCheckBox.checkState() == 2):
            if os.path.isfile(self.master_dark_file):
                drk=numpy.array(Image.open(self.master_dark_file))
                self._drk=drk
            elif self.master_dark_file.replace(' ','').replace('\t','') == '':
                pass #ignore
            else:
                msgBox = Qt.QMessageBox()
                msgBox.setText(tr("Cannot open \'"+self.master_dark_file+"\':"))
                msgBox.setInformativeText(tr("the file does not exist."))
                msgBox.setIcon(Qt.QMessageBox.Critical)
                msgBox.exec_()
                return False
        elif (len(self.darkfilelist)>0):
            _drk=self.__average_dark__()
            if _drk==None:
                return False
            else:
                self._drk=_drk
                
        if (self.wnd.masterFlatCheckBox.checkState() == 2):
            if os.path.isfile(self.master_flat_file):
                flt=numpy.array(Image.open(str(self.master_flat_file)))
                self._flt=flt
            elif self.master_flat_file.replace(' ','').replace('\t','') == '':
                pass #ignore
            else:
                msgBox = Qt.QMessageBox()
                msgBox.setText(tr("Cannot open \'"+self.master_dark_file+"\':"))
                msgBox.setInformativeText(tr("the file does not exist."))
                msgBox.setIcon(Qt.QMessageBox.Critical)
                msgBox.exec_()
                return False
        elif (len(self.flatfilelist)>0):
            _flt=self.__average_flat__(self._drk)
            if _flt==None:
                return False
            else:
                self._flt=_flt

        if(self.__average__(self._drk,self._flt)):        
            self.wnd.exposureGroupBox.setEnabled(True)
            self.wnd.saveResultPushButton.setEnabled(True)
        else:
            return False

    def __align__(self):
        
        if len(self.filelist) == 0:
            return False

        if (len(self.alignpointlist) > 0) and (len(self.alignpointlist[0])>0):
            self.statusBar.showMessage(tr('Calculating image shift, please wait...'))

            total_points = len(self.alignpointlist[0])
            self.progress.setMaximum(len(self.alignpointlist)-1)
            self.lock()       

            for i in range(len(self.alignpointlist)):
                x=0
                y=0
                for p in self.alignpointlist[i]:
                    x+=p[0]
                    y+=p[1]
                            
                self.offsetlist[i][0]=(x/total_points)
                self.offsetlist[i][1]=(y/total_points)

                self.progress.setValue(i)
                if ((i%25)==0) and self.progressWasCanceled():
                    return False
            self.unlock()
        else:
            self.statusBar.showMessage(tr('No align points: using manual alignment.'))
        
        

    def __average_dark__(self):
        result=None
        #total = len(self.aligned_dark)
        total = len(self.darkfilelist)
        self.statusBar.showMessage(tr('Creating master-dark, please wait...'))
        
        self.progress.setMaximum(total-1)
        self.lock()
        for i in range(total):
            self.progress.setValue(i)

            if self.progressWasCanceled():
                return None

            rawi=Image.open(self.darkfilelist[i])
            
            raw = numpy.array(rawi)
            del rawi
            
            if ('RGB' in self.currentDepht) and (len(raw[0][0]) > 3):
                raw.resize((len(raw),len(raw[0]),3),refcheck=False)
            if 'float' in str(raw.dtype):
                raw = (raw*self.IMAGE_RANGE).astype('ulonglong')
            else:
                raw = raw.astype('ulonglong')
                
            if result is None:
                result = raw
            else:
                result += raw
            del raw
            
        self.unlock()
               
        self.statusBar.showMessage(tr('Computing final image...'))

        result2=(result/total).clip(0,self.IMAGE_RANGE).astype(self.IMAGE_ARRAY_TYPE)
        rawi = Image.fromarray(result2)
        rawi.save(self.master_dark_save_file)

        del rawi
        self.statusBar.clearMessage()
        return result2
    
    def __average_flat__(self,dark_image=None):
        result=None

        if (dark_image != None):
            use_dark = True

        total = len(self.flatfilelist)
        
        self.statusBar.showMessage(tr('Creating master-flatfield, please wait...'))
        
        self.progress.setMaximum(total-1)
        self.lock()

        for i in range(total):
            self.progress.setValue(i)

            if self.progressWasCanceled():
                return None
                
            rawi=Image.open(self.flatfilelist[i])

            raw=numpy.array(rawi)
            del rawi
                        
            if ('RGB' in self.currentDepht) and (len(raw[0][0]) > 3):
                raw.resize((len(raw),len(raw[0]),3),refcheck=False)
            if 'float' in str(raw.dtype):
                raw = (raw*self.IMAGE_RANGE).astype('ulonglong')
            else:
                raw = raw.astype('ulonglong')
                
            if result is None:
                if use_dark:
                    result = (raw - dark_image)
                else:
                    result = raw
            else:
                if use_dark:
                    result += (raw-dark_image)
                else:
                    result += raw
            del raw
            
        self.unlock()
               
        self.statusBar.showMessage(tr('Computing final image...'))

        result=(result/total).clip(0,self.IMAGE_RANGE).astype(self.IMAGE_ARRAY_TYPE)        
        rawi = Image.fromarray(result)
        rawi.save(self.master_flat_save_file)

        del rawi
        
        self.statusBar.showMessage(tr('DONE'))

        return result
    
    def __average__(self,dark_image=None, flat_image=None): 
    
        ref_set=False
        self.progress.setMaximum(len(self.offsetlist)-1)
        self.lock()
        self.statusBar.showMessage(tr('Calculating refernces, please wait...'))
        
        for i in range(len(self.offsetlist)):
            self.progress.setValue(i)

            if ((i%25)==0) and self.progressWasCanceled():
                return False

            if self.wnd.listWidget.item(i).checkState()==2:
                if not ref_set:
                    ref_x=self.offsetlist[i][0]
                    ref_y=self.offsetlist[i][1]
                    ref_set=True
                else:
                    ref_x = min(ref_x,self.offsetlist[i][0])
                    ref_y = min(ref_y,self.offsetlist[i][1])
                    
        self.progress.reset()

        self.progress.setMaximum(len(self.offsetlist)-1)
   
        self.statusBar.showMessage(tr('Calculating refernces, please wait...'))
        
        for i in range(len(self.offsetlist)):
            self.progress.setValue(i)

            if ((i%25)==0) and self.progressWasCanceled():
                return False

            self.offsetlist[i][0]=Int(self.offsetlist[i][0]-ref_x)
            self.offsetlist[i][1]=Int(self.offsetlist[i][1]-ref_y)
            
        self.progress.reset()
                
        self.max_x_offset = 0
        self.max_y_offset = 0

        self.statusBar.showMessage(tr('Setting bound limits, please wait...'))

        total=len(self.filelist)
        self.progress.setMaximum(total-1)

        for i in range(total):
            if self.wnd.listWidget.item(i).checkState()==2:
                total+=1
                self.max_x_offset=max(self.offsetlist[i][0],self.max_x_offset)
                self.max_y_offset=max(self.offsetlist[i][1],self.max_y_offset)
            self.progress.setValue(i)

            if ((i%25)==0) and self.progressWasCanceled():
                return False

        self.result_w  = Int(self.currentWidth - abs(self.max_x_offset))
        self.result_h = Int(self.currentHeight - abs(self.max_y_offset))

        result=None
        
        if (dark_image != None):
            use_dark = True
            master_dark=dark_image*self.master_dark_mul_factor
        else:
            use_dark = False
            master_dark=None

        if (flat_image != None):
            use_flat = True
            normalizer = float(flat_image.sum()/flat_image.size)
            master_flat=(flat_image/normalizer)*self.master_flat_mul_factor
        else:
            use_flat = False
            master_flat=None

            
        total = len(self.filelist)
        
        self.statusBar.showMessage(tr('Adding images, please wait...'))
        
        self.progress.reset()
        self.progress.setMaximum(4*(total-1))
        count = 0
        
        for i in range(total):

            if self.progressWasCanceled():
                return False
                
            self.progress.setValue(4*i)
            if self.wnd.listWidget.item(i).checkState()!=2:
                continue
            count+=1
            x_start = self.offsetlist[i][0]
            y_start = self.offsetlist[i][1]
            
            rawi_unc=Image.open(self.filelist[i])
            rawi=rawi_unc.crop((x_start,y_start,x_start+self.result_w,y_start+self.result_h))

            del rawi_unc
            
            raw=numpy.array(rawi)

            del rawi
            
            if use_dark:
                rad = master_dark[y_start:y_start+self.result_h,x_start:x_start+self.result_w]
                
            self.progress.setValue((4*i)+1)

            if self.progressWasCanceled():
                return False
                
            if use_flat:
                raf = master_flat[y_start:y_start+self.result_h,x_start:x_start+self.result_w]

            self.progress.setValue((4*i)+2)

            if ('RGB' in self.currentDepht) and (len(raw[0][0]) > 3):
                raw.resize((len(raw),len(raw[0]),3),refcheck=False)
            if 'float' in str(raw.dtype):
                raw = (raw*self.IMAGE_RANGE).astype('longlong')
            else:
                raw = raw.astype('longlong')
                
            if use_dark:
                r = (raw - rad)
            else:
                r = raw                    
            if use_flat:
                r = r/raf

            self.progress.setValue((4*i)+3)

            if self.progressWasCanceled():
                return False
                
            if result is None:    
                result=r
            else:
                result+=r
            del raw
            
        self.progress.setValue(4*(total-1))   
        self.statusBar.showMessage(tr('Computing final image...'))

        self._avg=(result,count)
        result=(result/count).clip(0,self.IMAGE_RANGE).astype(self.IMAGE_ARRAY_TYPE)
        rawi = Image.fromarray(result)
        rawi.save(self.average_save_file)

        exp = self._avg[0].max()/self.IMAGE_RANGE

        if count < exp:
            self.wnd.exposureDoubleSpinBox.setMaximum(exp)
            self.wnd.exposureSlider.setMaximum(exp*100)
        else:
            self.wnd.exposureDoubleSpinBox.setMaximum(count)
            self.wnd.exposureSlider.setMaximum(count*100)            
        self.setExp(count)
        
        qimg = Qt.QImage(self.average_save_file)
        self.statusBar.clearMessage()
        self.showImage(qimg)
        self.unlock()
        self.statusBar.showMessage(tr('DONE'))

        del rawi
        del result

        return True
        
    def progressWasCanceled(self):
        self.qapp.processEvents()

        if self.wasCanceled:
            self.wasCanceled=False
            self.progress.hide()
            self.progress.reset()
            self.cancelProgress.hide()
            self.statusBar.showMessage(tr('Operation canceled by user'))
            self.unlock()
            return True
        else:
            return False

        
    def saveResult(self):
        outdir = str(Qt.QFileDialog.getExistingDirectory(self.wnd,tr("Choose the output folder"),self.current_dir))

        avg_name=os.path.basename(self.average_save_file)
        drk_name=os.path.basename(self.master_dark_save_file)
        flt_name=os.path.basename(self.master_flat_save_file)

        f = open(self.average_save_file,'rb')
        data = f.read()
        f.close()
        f = open(os.path.join(outdir,avg_name),'wb')
        f.write(data)
        f.close()

        rawi=Image.fromarray((self._avg[0]/self.exposure).clip(0,self.IMAGE_RANGE).astype(self.IMAGE_ARRAY_TYPE))
        rawi.save(os.path.join(outdir,self.elab_prefix+avg_name))
        del rawi
        
        if (self._drk!=None):
            rawi=Image.fromarray(self._drk)
            rawi.save(os.path.join(outdir,drk_name))
            del rawi
            
        if (self._flt!=None):
            rawi=Image.fromarray(self._flt)
            rawi.save(os.path.join(outdir,flt_name))
            del rawi
        