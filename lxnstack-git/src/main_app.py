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
import tempfile
from xml.dom import minidom
import paths
from PyQt4 import uic, Qt, QtCore, QtGui

loading = Qt.QProgressDialog()
loading.setWindowFlags(QtCore.Qt.SplashScreen)
logo =  Qt.QPixmap(os.path.join(paths.RESOURCES_PATH,"splashscreen.jpg"))
logoLabel=Qt.QLabel()
logoLabel.setPixmap(logo)
loading.setWindowTitle("starting lxnstack")
loading.setLabel(logoLabel)
loading.setCancelButton(None)
loading.setMaximum(100)

loading.show()
loading.setValue(1)

time.sleep(1)

def tr(s):
    news=QtCore.QCoreApplication.translate('@default',s)
    #python3 return str...
    if type(news) == str:
        return news
    else:
        #... while python2 return QString 
        # that must be converted to str
        return str(news.toAscii())

loading.setValue(10)

try:
    import numpy
except ImportError:
    msgBox = Qt.QMessageBox()
    msgBox.setText(tr("\'numpy\' python module not found!"))
    msgBox.setInformativeText(tr("Please install numpy."))
    msgBox.setIcon(Qt.QMessageBox.Critical)
    msgBox.exec_()
    sys.exit(1)

loading.setValue(20)
    
try:
    import scipy
except ImportError:
    msgBox = Qt.QMessageBox()
    msgBox.setText(tr("\'scipy\' python module not found!"))
    msgBox.setInformativeText(tr("Please install scipy."))
    msgBox.setIcon(Qt.QMessageBox.Critical)
    msgBox.exec_()
    sys.exit(1)

loading.setValue(30)

try:
    import cv2
except ImportError:
    msgBox = Qt.QMessageBox()
    msgBox.setText(tr("\'opencv2\' python module found!"))
    msgBox.setInformativeText(tr("Please install opencv2."))
    msgBox.setIcon(Qt.QMessageBox.Warning)
    msgBox.exec_()
    sys.exit(1)

loading.setValue(40)

import utils
        
loading.setValue(60)

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
        
        self._old_tab_idx=0
        self.__operating=False
        self._photo_time_clock=0
        self._ignore_histogrham_update = False #this will be used to avoid recursion loop!
        
        
        # it seems that kde's native dialogs work correctly while, on the contrary,
        # gnome's dialogs (and also dialogs of other desktop environmets?) will not
        # display correclty! In this case the Qt dialog (non native) dialogs will be
        # used.
        
        try:
            #try automatic detection
            if 'kde' == os.environ['XDG_CURRENT_DESKTOP'].lower():
                self._dialog_options = Qt.QFileDialog.Option(0)
            else:
                self._dialog_options = Qt.QFileDialog.DontUseNativeDialog
        except Exception:
            # This should work in each Desktop Environment
            self._dialog_options = Qt.QFileDialog.DontUseNativeDialog
        
        self.current_match_mode=cv2.TM_SQDIFF #TODO: Add selection box

        self.qapp=qapp
        
        self._generateOpenStrings()

        if not os.path.isdir(paths.TEMP_PATH):
            os.makedirs(paths.TEMP_PATH)
            
        self.temp_path=paths.TEMP_PATH

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
        
        self.current_align_method=0
        self.is_aligning=False
        
        self.showAlignPoints = True
        
        self.image_idx=-1
        self.ref_image_idx=-1
        self.dif_image_idx=-1
        self.point_idx=-1

        self._drk=None
        self._avg=None
        self._flt=None
        self._hst=None
        
        self._old_avg=None
        self._oldhst=None
        
        self.autoalign_rectangle=(256,256)
        self.auto_align_use_whole_image=0
        
        self.manual_align=False

        self.ftype=numpy.float32

        self.wnd = uic.loadUi(os.path.join(paths.UI_PATH,'main.ui'))
        self.dlg = uic.loadUi(os.path.join(paths.UI_PATH,'option_dialog.ui'))
        self.about_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'about_dialog.ui'))
        self.save_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'save_dialog.ui'))
        self.stack_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'stack_dialog.ui'))
        self.align_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'align_dialog.ui'))
        self.levels_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'levels_dialog.ui'))
        
        self.currentWidth=0
        self.currentHeight=0
        self.currentDepht=0
        
        self.use_colormap_jet = True

        self.result_w=0
        self.result_h=0
        self.result_d=3
        
        self.current_project_fname=None
        
        self.average_save_file='average'
        self.master_dark_save_file='master-dark'
        self.master_flat_save_file='master-flat'
        
        self.master_dark_mul_factor=1.0
        self.master_flat_mul_factor=1.0
                
        self.framelist=[]
        self.darkframelist=[]
        self.flatframelist=[]
        
        self.tracking_align_point=False
        self.use_cursor = QtCore.Qt.OpenHandCursor
        self.panning=False
        self.panning_startig=(0,0)
        self.panning_ending=(0,0)
        self.checked_seach_dark_flat=0
        self.checked_autodetect_rectangle_size=2
        self.checked_autodetect_min_quality=2
        self.checked_colormap_jet=2
        self.checked_rgb_fits=0
        self.checked_custom_temp_dir=2
        self.custom_chkstate=0
        self.ftype_idx=0
        self.checked_compressed_temp=0
        self.custom_temp_path=os.path.join(os.path.expandvars('$HOME'),paths.PROGRAM_NAME.lower(),'.temp')
        
        self.rgb_fits_mode=2
        
        self.fit_levels=False
        
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
        self.max_points=10
        self.min_quality=0.20
        
        self.levelfunc_idx=0
        
        self.current_pixel=(0,0)
        
        self.statusLabelMousePos = Qt.QLabel()
        self.statusBar = self.wnd.statusBar()
        self.setUpStatusBar()
        self.imageLabel= Qt.QLabel()
        self.imageLabel.setMouseTracking(True)
        self.imageLabel.setAlignment(QtCore.Qt.AlignTop)
        self.wnd.imageViewer.setWidget(self.imageLabel)
        self.wnd.imageViewer.setAlignment(QtCore.Qt.AlignTop)
        
        self.viewHScrollBar =  self.wnd.imageViewer.horizontalScrollBar()
        self.viewVScrollBar =  self.wnd.imageViewer.verticalScrollBar()
        
        self.wnd.colorBar.current_val=None
        self.wnd.colorBar.max_val=1.0
        self.wnd.colorBar.min_val=0.0
        self.wnd.colorBar._is_rgb=False
        
        self.bw_colormap=None
        self.rgb_colormap=None
                
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
        
        
        self.wnd.imageViewer.__wheelEvent__ = self.wnd.imageViewer.wheelEvent
        self.wnd.imageViewer.wheelEvent = self.imageViewerWheelEvent
        
        # paint callback
        self.imageLabel.__paintEvent__= self.imageLabel.paintEvent #base implementation
        self.imageLabel.paintEvent = self.imageLabelPaintEvent #new callback        
        
        # paint callback for colorBar
        self.wnd.colorBar.__paintEvent__= self.wnd.colorBar.paintEvent #base implementation
        self.wnd.colorBar.paintEvent = self.colorBarPaintEvent #new callback        

        # paint callback for histoGraphicsView
        self.levels_dlg.histoView.__paintEvent__= self.levels_dlg.histoView.paintEvent #base implementation
        self.levels_dlg.histoView.paintEvent = self.histoViewPaintEvent #new callback        


        # exit callback
        self.wnd.__closeEvent__= self.wnd.closeEvent #base implementation
        self.wnd.closeEvent = self.mainWindowCloseEvent #new callback        


        self.wnd.alignGroupBox.setEnabled(False)
        self.wnd.manualAlignGroupBox.setEnabled(False)
        self.wnd.masterDarkGroupBox.setEnabled(False)
        self.wnd.masterFlatGroupBox.setEnabled(False)
        self.wnd.masterDarkGroupBox.hide()
        self.wnd.masterFlatGroupBox.hide()
        self.wnd.stopCapturePushButton.hide()
        self.wnd.rawModeWidget.hide()
        self.wnd.captureWidget.hide()
        self.changeAlignMethod(self.current_align_method)
        
        self.save_dlg.radioButtonFits.setEnabled(utils.FITS_SUPPORT)
        
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
        self.wnd.avrPushButton.released.connect(self.stack)
        self.wnd.levelsPushButton.released.connect(self.editLevels)
        self.wnd.toolBox.currentChanged.connect(self.updateToolBox)
        self.wnd.spinBoxXAlign.valueChanged.connect(self.shiftX)
        self.wnd.spinBoxYAlign.valueChanged.connect(self.shiftY)
        self.wnd.doubleSpinBoxOffsetX.valueChanged.connect(self.shiftOffsetX)
        self.wnd.doubleSpinBoxOffsetY.valueChanged.connect(self.shiftOffsetY)
        self.wnd.spinBoxOffsetT.valueChanged.connect(self.rotateOffsetT)
        self.wnd.addPointPushButton.released.connect(self.addAlignPoint)
        self.wnd.removePointPushButton.released.connect(self.removeAlignPoint)
        self.wnd.alignPushButton.released.connect(self.align)
        self.wnd.saveResultPushButton.released.connect(self.saveResult)
        self.wnd.autoSetPushButton.released.connect(self.autoSetAlignPoint)
        self.wnd.autoDetectPushButton.released.connect(self.autoDetectAlignPoints)
        self.wnd.masterDarkCheckBox.stateChanged.connect(self.useMasterDark)
        self.wnd.masterFlatCheckBox.stateChanged.connect(self.useMasterFlat)
        self.wnd.masterDarkPushButton.released.connect(self.loadMasterDark)
        self.wnd.masterFlatPushButton.released.connect(self.loadMasterFlat)
        self.wnd.stopCapturePushButton.released.connect(self.stopped)
        self.wnd.capturePushButton.released.connect(self.started)
        self.wnd.singleShotPushButton.released.connect(self.oneShot)
        self.wnd.captureGroupBox.toggled.connect(self.capture)
        self.wnd.rawGroupBox.toggled.connect(self.updateBayerMatrix)
        self.wnd.bayerComboBox.currentIndexChanged.connect(self.updateBayerMatrix)
        self.wnd.darkMulDoubleSpinBox.valueChanged.connect(self.setDarkMul)
        self.wnd.flatMulDoubleSpinBox.valueChanged.connect(self.setFlatMul)
        self.wnd.alignMethodComboBox.currentIndexChanged.connect(self.changeAlignMethod)
        self.wnd.fitMinMaxCheckBox.stateChanged.connect(self.setDisplayLevelsFitMode)
        
        self.dlg.devComboBox.currentIndexChanged.connect(self.getDeviceInfo)
        self.dlg.videoSaveDirPushButton.released.connect(self._set_save_video_dir)
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
        self.dlg.jetCheckBox.stateChanged.connect(self.setJetmapMode)
        self.dlg.jetCheckBox.setCheckState(2)
        self.dlg.fTypeComboBox.currentIndexChanged.connect(self.setFloatPrecision)
        self.dlg.jetCheckBox.setCheckState(2)
        self.dlg.rgbFitsCheckBox.stateChanged.connect(self.setRGBFitsMode)
        self.dlg.tempPathPushButton.released.connect(self._set_temp_path)
        
        self.save_dlg.pushButtonDestDir.released.connect(self.getDestDir)
        
        self.levels_dlg.curveTypeComboBox.currentIndexChanged.connect(self.updateHistograhm)
        self.levels_dlg.aDoubleSpinBox.valueChanged.connect(self.updateHistograhm2)
        self.levels_dlg.bDoubleSpinBox.valueChanged.connect(self.updateHistograhm2)
        self.levels_dlg.oDoubleSpinBox.valueChanged.connect(self.updateHistograhm2)
        self.levels_dlg.nDoubleSpinBox.valueChanged.connect(self.updateHistograhm2)
        self.levels_dlg.mDoubleSpinBox.valueChanged.connect(self.updateHistograhm2)
        self.levels_dlg.dataClippingGroupBox.toggled.connect(self.updateHistograhm2)
        self.levels_dlg.dataClipping8BitRadioButton.toggled.connect(self.updateHistograhm2)
        self.levels_dlg.dataClippingFitDataRadioButton.toggled.connect(self.updateHistograhm2)
        self.levels_dlg.buttonBox.clicked.connect(self.levelsDialogButtonBoxClickedEvent)
        
        
        self.wnd.actionOpen_files.triggered.connect(self.doLoadFiles)
        self.wnd.actionOpen_video.triggered.connect(self.doLoadVideo)
        self.wnd.actionNew_project.triggered.connect(self.doNewProject)
        self.wnd.actionSave_project_as.triggered.connect(self.doSaveProjectAs)
        self.wnd.actionSave_project.triggered.connect(self.doSaveProject)
        self.wnd.actionLoad_project.triggered.connect(self.doLoadProject)
        self.wnd.actionPreferences.triggered.connect(self.doSetPreferences)
        self.wnd.actionAbout.triggered.connect(self.doShowAbout)
        self.wnd.actionUserManual.triggered.connect(self.doShowUserMan)

        self._resetPreferencesDlg()
                    
        if not os.path.isdir(self.save_image_dir):
            os.makedirs(self.save_image_dir)
        
        if not os.path.isdir(self.custom_temp_path):
            os.makedirs(self.custom_temp_path)
            
        self.setZoomMode(1,True)

    def _generateOpenStrings(self):
        self.supported_formats = utils.getSupportedFormats()
        # all supported formats
        self.images_extensions = ' ('
        for ext in self.supported_formats.keys():
            self.images_extensions+='*'+str(ext)+' '
        self.images_extensions += ');;'
        
        ImageTypes={}
        # each format
        for ext in self.supported_formats.keys():
            key=str(self.supported_formats[ext])
            
            if key in ImageTypes:
                ImageTypes[key]+=' *'+str(ext)
            else:
                ImageTypes[key]=' *'+str(ext)

        for ext in ImageTypes:
            self.images_extensions+=tr('Image')+' '+ext+' : '+ImageTypes[ext]
            self.images_extensions+='('+ImageTypes[ext]+');;'

    def setDisplayLevelsFitMode(self, state):
        self.fit_levels=(state==2)
        self.showImage(utils.arrayToQImage(self.current_image._original_data,bw_jet=self.use_colormap_jet,fit_levels=self.fit_levels))
        
    def setRGBFitsMode(self, state):
        self.rgb_fits_mode=(state==2)
        
    #slots for menu actions

    @QtCore.pyqtSlot(bool)
    def doLoadFiles(self, is_checked):
        self.loadFiles()
    
    @QtCore.pyqtSlot(bool)
    def doLoadVideo(self, is_checked):
        self.loadVideo()

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
    
    def changeAlignMethod(self, idx):
        self.current_align_method=idx
        self.imageLabel.repaint()
        if idx == 0:
            self.wnd.phaseGroupBox.show()
            self.wnd.alignGroupBox.hide()
        elif idx ==1:
            self.wnd.phaseGroupBox.hide()
            self.wnd.alignGroupBox.show()
        else:
            self.wnd.phaseGroupBox.hide()
            self.wnd.alignGroupBox.hide()
            #for other possible impementations
            pass
        
    def setFloatPrecision(self, idx):
        if idx==0:
            self.ftype=numpy.float32
        elif idx==1:
            self.ftype=numpy.float64
        
        utils.trace("setting float precision to " + str(self.ftype))
        
    def setJetmapMode(self,val):
        if val==0:
            self.use_colormap_jet=False
        else:
            self.use_colormap_jet=True
        
        if self.current_image != None:
            self.current_image = utils.arrayToQImage(self.current_image._original_data,bw_jet=self.use_colormap_jet,fit_levels=self.fit_levels)
            self.generateScaleMaps()
            self.updateImage()  

    def showUserMan(self):
        webbrowser.open(os.path.join(paths.DOCS_PATH,'usermanual.html'))

    def lock(self, show_cnacel = True):
        self.qapp.setOverrideCursor(QtCore.Qt.WaitCursor)
        self.statusLabelMousePos.setText('')
        self.progress.show()
        
        if show_cnacel:
            self.cancelProgress.show()
        else:
            self.cancelProgress.hide()
            
        self.wnd.toolBox.setEnabled(False)
        self.wnd.MainFrame.setEnabled(False)
        self.wnd.menubar.setEnabled(False)
        
    def unlock(self):
        self.statusBar.clearMessage()
        self.progress.hide()
        self.cancelProgress.hide()
        self.progress.reset()
        self.wnd.toolBox.setEnabled(True)
        self.wnd.MainFrame.setEnabled(True)
        self.wnd.menubar.setEnabled(True)
        self.qapp.restoreOverrideCursor()

    def setDarkMul(self,val):
        self.master_dark_mul_factor=val
        
    def setFlatMul(self,val):
        self.master_flat_mul_factor=val

    def _resetPreferencesDlg(self):
        idx=self.dlg.langComboBox.findData(self.__current_lang)
        self.dlg.langComboBox.setCurrentIndex(idx)
        
        self.dlg.useCustomLangCheckBox.setCheckState(self.custom_chkstate)
        
        self.dlg.fTypeComboBox.setCurrentIndex(self.ftype_idx)
        
        self.dlg.jetCheckBox.setCheckState(self.checked_colormap_jet)
        self.dlg.rgbFitsCheckBox.setCheckState(self.checked_rgb_fits)

        self.dlg.devComboBox.setCurrentIndex(self.current_cap_combo_idx)

        self.dlg.rWSpinBox.setValue(self.autoalign_rectangle[0])
        self.dlg.rHSpinBox.setValue(self.autoalign_rectangle[1])

        self.dlg.maxPointsSpinBox.setValue(self.max_points)
        self.dlg.minQualityDoubleSpinBox.setValue(self.min_quality)
        
        self.dlg.autoSizeCheckBox.setCheckState(self.checked_autodetect_rectangle_size)
        
        self.dlg.langFileLineEdit.setText(self.__current_lang)
        self.dlg.videoSaveLineEdit.setText(self.save_image_dir)
        
        self.dlg.wholeImageCheckBox.setChecked(self.auto_align_use_whole_image)
        self.dlg.autoSizeCheckBox.setChecked(self.checked_autodetect_rectangle_size)
        self.dlg.minQualitycheckBox.setCheckState(self.checked_autodetect_min_quality)

        self.dlg.autoFolderscheckBox.setCheckState(self.checked_seach_dark_flat)
        
        self.dlg.tempPathCheckBox.setCheckState(self.checked_custom_temp_dir)
        self.dlg.tempPathLineEdit.setText(self.custom_temp_path)
        self.dlg.compressedTempCheckBox.setCheckState(self.checked_compressed_temp)
        
        if self.checked_custom_temp_dir==2:
            self.temp_path=self.custom_temp_path
        else:
            self.temp_path=paths.TEMP_PATH
            
        
    def _set_save_video_dir(self):
        self.save_image_dir = str(Qt.QFileDialog.getExistingDirectory(self.dlg,
                                                                      tr("Choose the detination folder"),
                                                                      self.save_image_dir,
                                                                      self._dialog_options))
        self.dlg.videoSaveLineEdit.setText(self.save_image_dir)
        
    def _set_temp_path(self):
        self.custom_temp_path = str(Qt.QFileDialog.getExistingDirectory(self.dlg,
                                                                        tr("Choose the temporary folder"),
                                                                        self.temp_path,
                                                                        self._dialog_options))
        self.dlg.tempPathLineEdit.setText(self.custom_temp_path)
        
    def setPreferences(self):

        qtr = Qt.QTranslator()
        self.dlg.langComboBox.clear()
        for qmf in os.listdir(paths.LANG_PATH):
            fl = os.path.join(paths.LANG_PATH,qmf)
            if qtr.load(fl):
                self.dlg.langComboBox.addItem(qmf,fl)
        self._resetPreferencesDlg()

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
            #update settings
            r_w=int(self.dlg.rWSpinBox.value())
            r_h=int(self.dlg.rHSpinBox.value())
            self.custom_chkstate=int(self.dlg.useCustomLangCheckBox.checkState())
            self.max_points=int(self.dlg.maxPointsSpinBox.value())
            self.min_quality=float(self.dlg.minQualityDoubleSpinBox.value())
            self.autoalign_rectangle=(r_w, r_h)
            self.save_image_dir = str(self.dlg.videoSaveLineEdit.text())
            self.current_cap_combo_idx=int(self.dlg.devComboBox.currentIndex())
            self.current_cap_device_idx=self.devices[self.current_cap_combo_idx]['id']
            self.auto_align_use_whole_image=int(self.dlg.wholeImageCheckBox.checkState())
            self.checked_autodetect_rectangle_size=int(self.dlg.autoSizeCheckBox.checkState())
            self.checked_colormap_jet=int(self.dlg.jetCheckBox.checkState())
            self.checked_rgb_fits=int(self.dlg.rgbFitsCheckBox.checkState())
            self.checked_autodetect_min_quality=int(self.dlg.minQualitycheckBox.checkState())
            self.checked_seach_dark_flat=int(self.dlg.autoFolderscheckBox.checkState())
            self.ftype_idx=int(self.dlg.fTypeComboBox.currentIndex())
            self.checked_custom_temp_dir=int(self.dlg.tempPathCheckBox.checkState())
            self.checked_compressed_temp=int(self.dlg.compressedTempCheckBox.checkState())
            self.custom_temp_path=str(self.dlg.tempPathLineEdit.text())
            self.saveSettings()
            
            if self.checked_custom_temp_dir==2:
                self.temp_path=self.custom_temp_path
            else:
                self.temp_path=paths.TEMP_PATH
            
            return True
        else:
            #discard changes
            self._resetPreferencesDlg()
            return False
            
    def getDeviceInfo(self,idx):
        if idx >= 0:

            if not self.isPreviewing:
                i=self.devices[self.current_cap_combo_idx]['id']
                self.current_cap_device.open(i)
                self.current_cap_device_idx=i
            
                       
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
                try:
                    keys=self.device_propetyes['exposure_auto']['menu'].keys()
                    keys.sort()
                    self.exposure_type=self._setParamMenu(self.dlg.expTypeComboBox, keys, self.exposure_type)
                except:
                    pass
                
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
            self.current_cap_device.set(cv2.cv.CV_CAP_PROP_FOURCC,_4CC)
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
            
            actual_fps = utils.getV4LFps(device)

            if actual_fps != fps:
                #the fps is not set correclty
                self.statusBar.showMessage(tr("Sorry, but Fps cannot be changed on this device"))
                new_idx=self.dlg.fpsComboBox.findText(str(actual_fps)+" fps")
                self.dlg.fpsComboBox.setCurrentIndex(new_idx)
                
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
                if not self.setPreferences():
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
            self.wnd.framesGroupBox.setEnabled(False)
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
                        cv2.imwrite(name,img[1])
                        frm=utils.frame(name, data=img[1])
                        
                        self.framelist.append(frm)
                        
                        q=Qt.QListWidgetItem(os.path.basename(name),self.wnd.listWidget)
                        q.setCheckState(2)
                        q.setToolTip(name)
                        frm.addProperty("listItem",q)
                        self.wnd.listWidget.setCurrentItem(q)
                        self._unlock_cap_ctrls()

                del img

            self.isPreviewing = False
            self.wasCanceled=False
            self.current_cap_device.release()
            self.wnd.framesGroupBox.setEnabled(True)
            self.clearImage()
            
            if len(self.framelist)>0:
                self.wnd.listWidget.setCurrentRow(0)
                self.listItemChanged(0)

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
        self.wnd.rawGroupBox.setChecked(False)
        
        if self.framelist[0].isRGB():
            self.wnd.rawGroupBox.setEnabled(False)
        else:
            self.wnd.rawGroupBox.setEnabled(True)
        
    def _dismatchMsgBox(self,img):
        imw = img.shape[1]
        imh = img.shape[0]

        if len(img.shape)==2:
            dep='L'
        elif (len(img.shape)==3) and img.shape[-1]==3:
            dep='RGB'
        else:
            dep='RGBA'  
        if len(self.framelist)>0:
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
        
        if len(img.shape)==3:
            self.wnd.colorBar._is_rgb=True
        else:
            self.wnd.colorBar._is_rgb=False
        
        self.showImage(utils.arrayToQImage(img,2,1,0, bw_jet=self.use_colormap_jet,fit_levels=self.fit_levels))
        if self.wasStarted:
            self.wnd.stopCapturePushButton.show()
            self.wnd.capturePushButton.hide()
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
                    
                    self.framelist.append(utils.frame(name,0,rgb_fits=self.rgb_fits_mode,skip_loading=True))
                    
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
                self.wasStarted=False
                if (len(self.framelist)>0):
                    self.wnd.frameCountSpinBox.setValue(self.captured_frames)
                    self.wnd.listWidget.setCurrentRow(0)
                    self._unlock_cap_ctrls()
            
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
                                                              open_str,
                                                              None,
                                                              self._dialog_options
                                                              )
                              )
        if os.path.isfile(master_dark_file):
           try:
               i = utils.frame(master_dark_file)
               if not i.is_good:
                   msgBox = Qt.QMessageBox(self.wnd)
                   msgBox.setText(tr("Cannot open image")+" \""+str(i.url)+"\"")
                   msgBox.setIcon(Qt.QMessageBox.Critical)
                   msgBox.exec_()
                   return False
               imw = i.width
               imh = i.height
               dep = i.mode
               if ((self.currentWidth == imw) and
                   (self.currentHeight == imh) and
                   (self.currentDepht == dep)):
                   self.master_dark_file=i.url
                   self.wnd.masterDarkLineEdit.setText(i.url)
               else:
                   msgBox = Qt.QMessageBox(self.wnd)
                   msgBox.setText(tr("Cannot use this file:")+tr(" size or number of channels does not match!"))
                   msgBox.setInformativeText(tr('current size=')+
                                        str(self.currentWidth)+'x'+str(self.currentHeight)+'\n'+
                                        tr('image size=')+
                                        str(imw)+'x'+str(imh)+'\n'+
                                        tr('current channels=')+str(self.currentDepht)+'\n'+
                                        tr('image channels=')+str(dep)
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
                                                              open_str,
                                                              None,
                                                              self._dialog_options
                                                              )
                              )
        if os.path.isfile(master_flat_file):
           try:
               i = utils.frame(master_flat_file)
               if not i.is_good:
                   msgBox = Qt.QMessageBox(self.wnd)
                   msgBox.setText(tr("Cannot open image")+" \""+str(i.url)+"\"")
                   msgBox.setIcon(Qt.QMessageBox.Critical)
                   msgBox.exec_()
                   return False
               imw = i.width
               imh = i.height
               dep = i.mode
               if ((self.currentWidth == imw) and
                   (self.currentHeight == imh) and
                   (self.currentDepht == dep)):
                   self.master_flat_file=i.url
                   self.wnd.masterFlatLineEdit.setText(i.url)
               else:
                   msgBox = Qt.QMessageBox(self.wnd)
                   msgBox.setText(tr("Cannot use this file:"))
                   msgBox.setInformativeText(tr("Size or number of channels does not match!"))
                   msgBox.setInformativeText(tr('current size=')+
                                        str(self.currentWidth)+'x'+str(self.currentHeight)+'\n'+
                                        tr(' image size=')+
                                        str(imw)+'x'+str(imh)+'\n'+
                                        tr('current channels=')+str(self.currentDepht)+'\n'+
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
        settings.setValue("autodetect_rectangle", int(self.dlg.autoSizeCheckBox.checkState()))
        settings.setValue("autodetect_quality", int(self.dlg.minQualitycheckBox.checkState()))
        settings.setValue("max_align_points",int(self.max_points))
        settings.setValue("min_point_quality",float(self.min_quality))
        settings.setValue("use_whole_image", int(self.dlg.wholeImageCheckBox.checkState()))
        settings.setValue("use_colormap_jet", int(self.dlg.jetCheckBox.checkState()))
        settings.setValue("auto_rgb_fits", int(self.dlg.rgbFitsCheckBox.checkState()))
        settings.setValue("auto_search_dark_flat",int(self.dlg.autoFolderscheckBox.checkState()))
        settings.setValue("sharp1",float(self.wnd.sharp1DoubleSpinBox.value()))
        settings.setValue("sharp2",float(self.wnd.sharp2DoubleSpinBox.value()))
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
        settings.setValue("current_align_method",int(self.current_align_method))
        settings.setValue("float_precision",int(self.ftype_idx))
        settings.setValue("use_custom_temp_path",int(self.checked_custom_temp_dir))
        settings.setValue("custom_temp_path",str(self.custom_temp_path))
        settings.setValue("use_zipped_tempfiles",int(self.checked_compressed_temp))
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
        self.checked_autodetect_rectangle_size=settings.value("autodetect_rectangle",None,int)
        self.checked_autodetect_min_quality=settings.value("autodetect_quality",None,int)
        self.dlg.minQualitycheckBox.setCheckState(self.checked_autodetect_min_quality)
        self.auto_align_use_whole_image=settings.value("use_whole_image",None,int)
        self.dlg.wholeImageCheckBox.setCheckState(self.auto_align_use_whole_image)
        self.checked_colormap_jet=settings.value("use_colormap_jet",None,int)
        self.dlg.jetCheckBox.setCheckState(self.checked_colormap_jet)
        self.checked_rgb_fits=settings.value("auto_rgb_fits",None,int)
        self.dlg.rgbFitsCheckBox.setCheckState(self.checked_rgb_fits)
        self.checked_seach_dark_flat=settings.value("auto_search_dark_flat",None,int)
        self.dlg.autoFolderscheckBox.setCheckState(self.checked_seach_dark_flat)
        self.max_points=int(settings.value("max_align_points",None,int))
        self.min_quality=float(settings.value("min_point_quality",None,float))
        sharp1=float(settings.value("sharp1",None,float))
        self.wnd.sharp1DoubleSpinBox.setValue(sharp1)
        sharp2=float(settings.value("sharp1",None,float))
        self.wnd.sharp2DoubleSpinBox.setValue(sharp2)
        settings.endGroup()

        settings.beginGroup("settings");
        self.__current_lang = str(settings.value("language_file",None,str))
        self.custom_chkstate=int(settings.value("custom_language",None,int))
        self.save_image_dir = str(settings.value("images_save_dir",None,str))
        self.current_align_method=int(settings.value("current_align_method",None,int))
        self.ftype_idx=int(settings.value("float_precision",None,int))
        self.checked_custom_temp_dir=int(settings.value("use_custom_temp_path",None,int))
        self.custom_temp_path=str(settings.value("custom_temp_path",None,str))
        self.checked_compressed_temp=int(settings.value("use_zipped_tempfiles",None,int))
        settings.endGroup()

        self.wnd.alignMethodComboBox.setCurrentIndex(self.current_align_method)
        self.changeAlignMethod(self.current_align_method)

    ##resizeEvent callback
    def mainWindowResizeEvent(self, event):
        val = self.wnd.__resizeEvent__(event)# old implementation
        if self.zoom_fit:
            self.updateImage()    
        self.generateScaleMaps()
        return val

    #mouseMoveEvent callback    
    def imageLabelMouseMoveEvent(self, event):
        val = self.imageLabel.__mouseMoveEvent__(event)
        mx=event.x()
        my=event.y()
        x=Int(mx/self.actual_zoom)
        y=Int(my/self.actual_zoom)

        if (self.current_image != None) and (not self.manual_align):
            if self.current_image._original_data != None:
                imshape = self.current_image._original_data.shape
                if ((y>=0) and (y < imshape[0]) and
                    (x>=0) and (x < imshape[1])):
                        pix_val=self.current_image._original_data[y,x]
                        self.current_pixel=(x,y)
                        self.wnd.colorBar.current_val=pix_val
                        self.wnd.colorBar.repaint()
            else:
                pix_val=None
                
        if self.panning:            
            sx = mx-self.panning_startig[0]
            sy = my-self.panning_startig[1]           
            
            self.viewHScrollBar.setValue(self.viewHScrollBar.value()-sx)
            self.viewVScrollBar.setValue(self.viewVScrollBar.value()-sy)
            
        if (self.tracking_align_point and 
            (self.image_idx>=0) and 
            (self.point_idx>=0)
           ):
            pnt = self.framelist[self.image_idx].alignpoints[self.point_idx]
            pnt[0]=x
            pnt[1]=y
            self.wnd.spinBoxXAlign.setValue(x)
            self.wnd.spinBoxYAlign.setValue(y)
            self.imageLabel.repaint()
        return val
    
    
    def imageViewerWheelEvent(self, event):
        if self.zoom_enabled:
            delta = numpy.sign(event.delta())*math.log10(self.zoom+1)/2.5
            mx=event.x()
            my=event.y()
            cx = self.wnd.imageViewer.width()/2.0
            cy = self.wnd.imageViewer.height()/2.0
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
            self.wnd.imageViewer.setCursor(QtCore.Qt.ClosedHandCursor)
            self.imageLabel.setCursor(QtCore.Qt.ClosedHandCursor)
            self.panning=True
            self.panning_startig=(event.x(),event.y())
        elif btn==2:
            self.tracking_align_point=True
        return val
    
    def imageLabelMouseReleaseEvent(self, event):
        val = self.imageLabel.__mouseReleaseEvent__(event)
        btn=event.button()
        x=Int(event.x()/self.actual_zoom)
        y=Int(event.y()/self.actual_zoom)
        if btn==1:
            self.panning=False
            self.wnd.imageViewer.setCursor(self.use_cursor)
            self.imageLabel.setCursor(self.use_cursor)
        elif btn==2:
            if self.point_idx >= 0:
                self.tracking_align_point=False
                pnt = self.framelist[self.image_idx].alignpoints[self.point_idx]
                pnt[0]=x
                pnt[1]=y
                pnt[3]=False
                self.wnd.spinBoxXAlign.setValue(x)
                self.wnd.spinBoxYAlign.setValue(y)
                self.imageLabel.repaint()
        return val
    
    #paintEvent callback for colorBar
    def colorBarPaintEvent(self, obj):
        val=self.wnd.colorBar.__paintEvent__(obj)

        if self.current_image==None:
            self.wnd.colorBar.setPixmap(Qt.QPixmap())
            return val
        
        if self.wnd.colorBar.current_val!=None:
            painter = Qt.QPainter(self.wnd.colorBar)
            cb = self.wnd.colorBar
            
            _gpo=2 #geometric corrections
            _gno=5 #geometric corrections
            
            fnt_size=10
            painter.setFont(Qt.QFont("Arial", fnt_size))
            y=(cb.height()+fnt_size/2)/2 + 2
            max_txt=str(cb.max_val)
            self.statusLabelMousePos.setText('position='+str(self.current_pixel)+' value='+str(cb.current_val))        
            if cb._is_rgb == True:
                cb.setPixmap(Qt.QPixmap.fromImage(self.rgb_colormap))
                
                try:
                    xr = int((float(cb.current_val[0]-cb.min_val)/float(cb.max_val-cb.min_val))*(cb.width()-_gno))+_gpo
                except Exception:
                    xr = -1
                    
                try:
                    xg = int((float(cb.current_val[1]-cb.min_val)/float(cb.max_val-cb.min_val))*(cb.width()-_gno))+_gpo
                except Exception:
                    xg = -1
                
                try:
                    xb = int((float(cb.current_val[2]-cb.min_val)/float(cb.max_val-cb.min_val))*(cb.width()-_gno))+_gpo
                except Exception:
                    xb = -1
                painter.setCompositionMode(22)
                
                painter.setPen(QtCore.Qt.red)
                painter.drawLine(xr,4,xr,self.wnd.colorBar.height()-4)
                
                painter.setPen(QtCore.Qt.green)
                painter.drawLine(xg,4,xg,self.wnd.colorBar.height()-4)
                
                painter.setPen(QtCore.Qt.blue)
                painter.drawLine(xb,4,xb,self.wnd.colorBar.height()-4)
                                
                painter.setCompositionMode(0)
                painter.setPen(QtCore.Qt.white)
                painter.drawText(fnt_size-4,y,str(cb.min_val))
                painter.setPen(QtCore.Qt.black)
                painter.drawText(cb.width()-(fnt_size-2)*len(max_txt),y,max_txt)
                
            else:
                painter.setPen(QtCore.Qt.white)

                painter.setCompositionMode(0)

                #painter.drawPixmap(0,0,Qt.QPixmap.fromImage(self.bw_colormap))
                cb.setPixmap(Qt.QPixmap.fromImage(self.bw_colormap))
                
                try:
                    x = int((float(cb.current_val-cb.min_val)/float(cb.max_val-cb.min_val))*(cb.width()-_gno))+_gpo
                except Exception:
                    x = -1
                
                painter.setCompositionMode(22)
                
                painter.drawLine(x,4,x,self.wnd.colorBar.height()-4)

                painter.drawText(fnt_size-4,y,str(cb.min_val))
                painter.drawText(cb.width()-(fnt_size-2)*len(max_txt),y,max_txt)

                painter.setCompositionMode(0)

            del painter
            
        return val
    
    def histoViewPaintEvent(self, obj):
        
        bins=255
        
        painter = Qt.QPainter(self.levels_dlg.histoView)
        
        xmin,xmax = self.getLevelsClippingRange()
        
        w = self.levels_dlg.histoView.width()
        h = self.levels_dlg.histoView.height()
        
        painter.setBrush(QtCore.Qt.white)
        painter.drawRect(0,0,w,h)
        
        utils.drawHistograhm(painter, w, h, self._hst, xmin, xmax)
        
    #paintEvent callback
    def imageLabelPaintEvent(self, obj):
        val=self.imageLabel.__paintEvent__(obj)
        
        painter = Qt.QPainter(self.imageLabel)
        
        if self.current_image != None:
            painter.scale(self.actual_zoom,self.actual_zoom)
            painter.drawImage(0,0,self.current_image)
                
        if (not self.manual_align):
            if self.image_idx<0:
                return val
            elif (self.current_align_method==0) and (self.is_aligning):
                pass #TODO: draw the phase correlation images
            elif self.current_align_method==1:
                self._drawAlignPoints(painter)
        else:
            self._drawDifference(painter)
        del painter
        return val

    def _drawAlignPoints(self, painter):
        if(len(self.framelist) == 0) or (not self.showAlignPoints):
            return False
        painter.setFont(Qt.QFont("Arial", 8))  
        for i in self.framelist[self.image_idx].alignpoints:
                      
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
            
    def _drawDifference(self,painter):
        if (self.ref_image != None) and (self.current_image != None):
            
            ref = self.framelist[self.ref_image_idx]
            img = self.framelist[self.dif_image_idx] 
            
            rot_center=(img.width/2.0,img.height/2.0)
           
            painter.drawImage(0,0,self.ref_image)
            painter.setCompositionMode(22)
                        
            x = (img.offset[0]-ref.offset[0])
            y = (img.offset[1]-ref.offset[1])
            
            #this is needed because the automatic aignment takes the first image available as
            #reference to calculate derotation
            alpha = self.framelist[self.wnd.listWidgetManualAlign.item(0).original_id].angle            
            
            cosa = math.cos(numpy.deg2rad(-alpha))
            sina = math.sin(numpy.deg2rad(-alpha))
            
            xi = x*cosa + y*sina
            yi = y*cosa - x*sina
                        
            painter.translate(rot_center[0]-xi,rot_center[1]-yi)
            
            painter.rotate(-img.angle+ref.angle)

            painter.drawImage(-int(rot_center[0]),-int(rot_center[1]),self.current_image)
            painter.setCompositionMode(0)
    
    def setZoomMode(self, val, check=False):
        
        if check:
            self.wnd.zoomCheckBox.setCheckState(val)
        
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
        
        if zoom <= self.wnd.zoomDoubleSpinBox.maximum():
            self.zoom=zoom
        else:
            self.zoom=self.wnd.zoomDoubleSpinBox.maximum()
            
        self.wnd.zoomDoubleSpinBox.setValue(self.zoom)
        self.wnd.zoomSlider.setValue(Int(self.zoom*100))
        
    def signalSliderZoom(self, value, update=False):
        self.zoom=(value/100.0)
        vp = self.getViewport()
        self.wnd.zoomDoubleSpinBox.setValue(self.zoom)
        if update:
            self.updateImage()

        self.setViewport(vp)
        
    def signalSpinZoom(self, value, update=True):
        self.zoom=value
        vp = self.getViewport()
        self.wnd.zoomSlider.setValue(Int(self.zoom*100))
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
        
    def updateResultImage(self):
        if self._avg!=None:
            img = utils.arrayToQImage(self._avg,bw_jet=self.use_colormap_jet,fit_levels=self.fit_levels)
            self.showImage(img)
        else:
            self.clearImage()
        
    def showImage(self, image):
        del self.current_image
        self.current_image = image
        self.updateImage()
            
    def clearImage(self):
        del self.current_image
        self.current_image=None
        self.imageLabel.setPixmap(Qt.QPixmap())

    def generateScaleMaps(self):
        # bw or jet colormap
        data1 = numpy.arange(0,self.wnd.colorBar.width())*255.0/self.wnd.colorBar.width()
        data2 = numpy.array([data1]*(self.wnd.colorBar.height()-8))
        qimg = utils.arrayToQImage(data2,bw_jet=self.use_colormap_jet,fit_levels=self.fit_levels)
        self.bw_colormap = qimg

        #rgb colormap
        data1 = numpy.arange(0,self.wnd.colorBar.width())*255.0/self.wnd.colorBar.width()
        data2 = numpy.array([data1]*int((self.wnd.colorBar.height()-8)/3.0))
        hh=len(data2)
        data3 = numpy.zeros((3*hh,len(data1),3))
       
        data3[0:hh,0:,0]=data2
        data3[hh:2*hh,0:,1]=data2
        data3[2*hh:3*hh,0:,2]=data2
        
        qimg = utils.arrayToQImage(data3,bw_jet=self.use_colormap_jet,fit_levels=self.fit_levels)
        self.rgb_colormap = qimg

    def updateImage(self, paint=True, overrided_image=None):
        
        if overrided_image != None:
            current_image=overrided_image
        elif self.current_image != None:
            current_image=self.current_image
        else:
            return False
        
        imh = current_image.height()
        imw = current_image.width()

        try:
            self.wnd.colorBar.current_val=current_image._original_data[self.current_pixel[1],self.current_pixel[0]]
            self.wnd.colorBar.repaint()
        except Exception as exc:
            self.current_pixel=(0,0)

        if self.zoom_enabled:
            self.actual_zoom=self.zoom
        elif self.zoom_fit:
                        
            self.actual_zoom=min(float(self.wnd.imageViewer.width()-10)/imw,
                                 float(self.wnd.imageViewer.height()-10)/imh
                                )
                                
            self.wnd.zoomDoubleSpinBox.setValue(self.zoom)
        else:
            self.actual_zoom=1
            
        if paint:
            imh+=1
            imw+=1
            self.imageLabel.setMaximumSize(imw*self.actual_zoom,imh*self.actual_zoom)
            self.imageLabel.setMinimumSize(imw*self.actual_zoom,imh*self.actual_zoom)
            self.imageLabel.resize(imw*self.actual_zoom,imh*self.actual_zoom)
            self.imageLabel.update()
            if current_image._original_data != None:
                self.wnd.colorBar.max_val=current_image._original_data.max()
                self.wnd.colorBar.min_val=current_image._original_data.min()

                if (self.wnd.colorBar.max_val <=1) or self.fit_levels:
                    pass
                elif self.wnd.colorBar.max_val <= 255:
                    self.wnd.colorBar.max_val*=255.0/self.wnd.colorBar.max_val
                elif self.wnd.colorBar.max_val <= 65536:
                    self.wnd.colorBar.max_val*=65536.0/self.wnd.colorBar.max_val
                    
                if self.fit_levels:
                    pass
                elif self.wnd.colorBar.min_val > 0:
                    self.wnd.colorBar.min_val*=0
                
                if not self.wnd.colorBar.isVisible():
                    self.wnd.colorBar.show()
            else:
                self.wnd.colorBar.max_val=1
                self.wnd.colorBar.max_val=0
                if self.wnd.colorBar.isVisible():
                    self.wnd.colorBar.hide()
                
            #this shuold avoid division by zero
            if  self.wnd.colorBar.max_val ==  self.wnd.colorBar.min_val:
                self.wnd.colorBar.max_val=self.wnd.colorBar.max_val+1
                self.wnd.colorBar.min_val=self.wnd.colorBar.min_val-1
                
            #self.generateScaleMaps()
        #else:
            #return pix
    
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

        oldlist=self.framelist[:]

        open_str=tr("All files *.* (*.*)")
        vidname=str(Qt.QFileDialog.getOpenFileName(self.wnd,
                                                   tr("Select a video"),
                                                   self.current_dir,
                                                   open_str,
                                                   None,
                                                   self._dialog_options)
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
            if len(self.framelist) > 0:
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

        oldlist=self.framelist[:]

        #self.rgb_fits_mode = (self.checked_rgb_fits==2)

        if newlist==None:
            open_str=tr("All supported images")+self.images_extensions+";;"+tr("All files *.* (*.*)")
            newlist=list(Qt.QFileDialog.getOpenFileNames(self.wnd,
                                                         tr("Select one or more files"),
                                                         self.current_dir,
                                                         open_str,
                                                         None,
                                                         self._dialog_options)
                        )

        self.statusBar.showMessage(tr('Loading files, please wait...'))

        if len(self.framelist) > 0:
            imw = self.currentWidth
            imh = self.currentHeight
            dep = self.currentDepht[0:3]
        elif len(newlist) > 0:
            ref = utils.frame(str(newlist[0]),rgb_fits=self.rgb_fits_mode)
            if not ref.is_good:
                msgBox = Qt.QMessageBox(self.wnd)
                msgBox.setText(tr("Cannot open image")+" \""+str(ref.url)+"\"")
                msgBox.setIcon(Qt.QMessageBox.Critical)
                msgBox.exec_()
                return False
            imw = ref.width
            imh = ref.height
            dep = ref.mode
            
            del ref     
            
            self.currentWidth=imw
            self.currentHeight=imh
            self.currentDepht=dep

            if self.dlg.autoSizeCheckBox.checkState()==2:
                r_w=int(self.currentWidth/10)
                r_h=int(self.currentHeight/10)
                r_l=max(r_w,r_h)
                self.autoalign_rectangle=(r_l,r_h)
                self.dlg.rWSpinBox.setValue(r_l)
                self.dlg.rHSpinBox.setValue(r_l)
            
            if 'RGB' in dep:
                self.wnd.colorBar._is_rgb=True
                self.wnd.colorBar.current_val=(0.0,0.0,0.0)
            else:
                self.wnd.colorBar._is_rgb=False
                self.wnd.colorBar.current_val=0.0
                
            self.wnd.colorBar.max_val=1.0
            self.wnd.colorBar.min_val=0.0
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
            if not (i in self.framelist): #TODO:fix here: string must be compared to string
                page = 0
                img=utils.frame(str(i),page, rgb_fits=self.rgb_fits_mode)
                if not img.is_good:
                    msgBox = Qt.QMessageBox(self.wnd)
                    msgBox.setText(tr("Cannot open image")+" \""+str(i)+"\"")
                    msgBox.setIcon(Qt.QMessageBox.Critical)
                    msgBox.exec_()
                    continue
                
                while img.is_good:
                    if (imw,imh)!=(img.width,img.height):
                        warnings=True
                        rejected+=(img.url+tr(' --> size does not match:')+'\n'+
                                            tr('current size=')+
                                            str(self.currentWidth)+'x'+str(self.currentHeight)+
                                            ' '+tr('image size=')+
                                            str(img.width)+'x'+str(img.height)+'\n')
                    elif not(dep in img.mode):
                        warnings=True
                        rejected+=(img.url+tr(' --> number of channels does not match:')+'\n'+
                                            tr('current channels=')+
                                            str(self.currentDepht)+
                                            ' '+tr('image channels=')+
                                            str(img.mode)+'\n')
                    else:                    
                        self.framelist.append(img)
                        q=Qt.QListWidgetItem(img.tool_name)
                        q.setCheckState(2)
                        q.setToolTip(img.long_tool_name)
                        listitemslist.append(q)
                        img.addProperty("listItem",q)
                    page+=1
                    img=utils.frame(str(i),page, rgb_fits=self.rgb_fits_mode)
                    
            self.progress.setValue(count)
            if self.progressWasCanceled():
                self.framelist=oldlist
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
        
        self.darkframelist=[]

        if self.checked_seach_dark_flat==2:
            self.dark_dir = os.path.join(self.current_dir,'dark')
            self.statusBar.showMessage(tr('Searching for dark frames, please wait...'))
            if not self.doAddDarkFiles(self.dark_dir, ignoreErrors=True):
                pass

            self.flat_dir = os.path.join(self.current_dir,'flat')
            self.statusBar.showMessage(tr('Searching for flatfiled frames, please wait...'))
            if not self.doAddFlatFiles(self.flat_dir, ignoreErrors=True):
                pass

        self.statusBar.showMessage(tr('DONE'))
        
        if (len(self.framelist)>0):
            self._unlock_cap_ctrls()

        self.statusBar.showMessage(tr('Ready'))

    def doAddDarkFiles(self, directory=None, ignoreErrors=False):
        if directory is None:
            open_str=tr("All supported images")+self.images_extensions+";;"+tr("All files *.* (*.*)")
            files = list(Qt.QFileDialog.getOpenFileNames(self.wnd,
                                                         tr("Select one or more files"),
                                                         self.current_dir,
                                                         open_str,
                                                         None,
                                                         self._dialog_options)
                        )
        elif os.path.exists(directory) and os.path.isdir(directory):
            files = []
            lst = os.listdir(directory)
            for x in lst:
                files.append(os.path.join(directory,x))
        else:
            return False
            
        self.progress.setMaximum(len(files))
        self.lock()
        count=0
        warnings = False
        rejected = ""
        
        for fn in files:

            self.qapp.processEvents()
            self.progress.setValue(count)
            
            
            if (os.path.isfile(str(fn))): #TODO: check for duplicates

               page=0
               i=utils.frame(str(fn),page,rgb_fits=self.rgb_fits_mode)
               if not i.is_good:
                    if not ignoreErrors:
                        msgBox = Qt.QMessageBox(self.wnd)
                        msgBox.setText(tr("Cannot open image")+" \""+str(fn)+"\"")
                        msgBox.setIcon(Qt.QMessageBox.Critical)
                        msgBox.exec_()
                    continue
               while i.is_good:
                   if ((self.currentWidth == i.width) and
                       (self.currentHeight == i.height) and
                       (self.currentDepht == i.mode)):
                       self.darkframelist.append(i)
                       q=Qt.QListWidgetItem(i.tool_name,self.wnd.darkListWidget)
                       q.setToolTip(i.long_tool_name)
                   else:
                        warnings=True
                        rejected+=(i.url+"\n")
                        break
                   page+=1
                   i=utils.frame(str(fn),page,rgb_fits=self.rgb_fits_mode)

            if self.progressWasCanceled():
                return False
            count+=1
            
        self.unlock()
        
        if warnings:
            msgBox = Qt.QMessageBox(self.wnd)
            msgBox.setText(tr("Some imagese have different sizes or number of channels and will been ignored.\n"))
            msgBox.setInformativeText(tr("All images must have the same size and number of channels.\n\n")+
                                      tr("Click the \'Show Details' button for more information.\n"))
            msgBox.setDetailedText (rejected)
            msgBox.setIcon(Qt.QMessageBox.Warning)
            msgBox.exec_()
            del msgBox
        
        if (len(self.darkframelist) == 0):
            return False
        else:
            self.wnd.darkClearPushButton.setEnabled(True)
        return True
        
    def doClearDarkList(self):
        del self.darkframelist # foce memory release
        self.darkframelist=[]
        self.wnd.darkListWidget.clear()
        self.wnd.darkClearPushButton.setEnabled(False)
        
    def doAddFlatFiles(self, directory=None, ignoreErrors=False):
        if directory is None:
            open_str=tr("All supported images")+self.images_extensions+";;"+tr("All files *.* (*.*)")
            files = list(Qt.QFileDialog.getOpenFileNames(self.wnd,
                                                         tr("Select one or more files"),
                                                         self.current_dir,
                                                         open_str,                                                         
                                                         None,
                                                         self._dialog_options)
                        )
            
        elif os.path.exists(directory) and os.path.isdir(directory):
            files = []
            lst = os.listdir(directory)
            for x in lst:
                files.append(os.path.join(directory,x))
        else:
            return False

        self.progress.setMaximum(len(files))
        self.lock()
        count=0
        warnings = False
        rejected = ""
        
        for fn in files:
            
            self.qapp.processEvents()
            self.progress.setValue(count)
            
            if (os.path.isfile(fn)): # check for duplicates

               page=0
               i=utils.frame(str(fn),page,rgb_fits=self.rgb_fits_mode)
               if not i.is_good:
                    if not ignoreErrors:
                        msgBox = Qt.QMessageBox(self.wnd)
                        msgBox.setText(tr("Cannot open image")+" \""+i.url+"\"")
                        msgBox.setIcon(Qt.QMessageBox.Critical)
                        msgBox.exec_()
                    continue
               while i.is_good:
                   if ((self.currentWidth == i.width) and
                       (self.currentHeight == i.height) and
                       (self.currentDepht == i.mode)):
                       self.flatframelist.append(i)
                       q=Qt.QListWidgetItem(i.tool_name,self.wnd.flatListWidget)
                       q.setToolTip(i.long_tool_name)
                   else:
                        warnings=True
                        rejected+=(i.url+"\n")
                        break
                   page+=1
                   i=utils.frame(str(fn),page,rgb_fits=self.rgb_fits_mode)

            if self.progressWasCanceled():
                return False
            count+=1
            
        self.unlock()
        
        if warnings:
            msgBox = Qt.QMessageBox(self.wnd)
            msgBox.setText(tr("Some imagese have different sizes or number of channels and will been ignored.\n"))
            msgBox.setInformativeText(tr("All images must have the same size and number of channels.\n\n")+
                                      tr("Click the \'Show Details' button for more information.\n"))
            msgBox.setDetailedText (rejected)
            msgBox.setIcon(Qt.QMessageBox.Warning)
            msgBox.exec_()
            del msgBox

        
        if (len(self.flatframelist) == 0):
            return False
        else:
            self.wnd.flatClearPushButton.setEnabled(True)
        return True

    def doClearFlatList(self):
        del self.flatframelist # foce memory release
        self.flatframelist=[]
        self.wnd.flatListWidget.clear()
        self.wnd.flatClearPushButton.setEnabled(False)

    def clearList(self):
        self.framelist=[]
            
        self.wnd.listWidget.clear()
        self.wnd.alignPointsListWidget.clear()
        self.wnd.remPushButton.setEnabled(False)
        self.wnd.clrPushButton.setEnabled(False)
        self.wnd.listCheckAllBtn.setEnabled(False)
        self.wnd.listUncheckAllBtn.setEnabled(False)
        self.wnd.avrPushButton.setEnabled(False)
        self.wnd.alignPushButton.setEnabled(False)
        self.wnd.levelsPushButton.setEnabled(False)
        self.wnd.saveResultPushButton.setEnabled(False)
        self.wnd.rawGroupBox.setChecked(False)
        self.wnd.rawGroupBox.setEnabled(False)
        self.clearImage()
        del self._avg
        self._avg = None

    def removeImage(self):
        q = self.wnd.listWidget.takeItem(self.wnd.listWidget.currentRow())
        self.framelist.pop(self.wnd.listWidget.currentRow())
        del q
        
        del self._avg
        self._avg=None

        if (len(self.framelist)==0):
            self.clearList()
        elif self.image_idx >= len(self.framelist):
            self.wnd.listWidget.setCurrentRow(len(self.framelist)-1)
            self.listItemChanged(self.wnd.listWidget.currentRow())

    def checkAllListItems(self):
        self.setAllListItemsCheckState(2)

    def uncheckAllListItems(self):
        self.setAllListItemsCheckState(0)
        
    def clearDarkList(self):
        self.darkframelist = []
        self.aligned_dark=[]
        
    def clearAlignPoinList(self):
        for frm in self.framelist:
           frm.alignpoints=[]
        self.wnd.alignPointsListWidget.clear()
        self.wnd.removePointPushButton.setEnabled(False)
        self.updateImage()

    def setAllListItemsCheckState(self, state):
        for i in range(self.wnd.listWidget.count()):
            self.wnd.listWidget.item(i).setCheckState(state)

    def debayerize(self, data):
        if (len(data.shape)==2) and self.wnd.rawGroupBox.isChecked():
            bayer = self.wnd.bayerComboBox.currentIndex()
            
            if bayer == 0:
                mode = cv2.cv.CV_BayerBG2RGB
            elif bayer == 1:
                mode = cv2.cv.CV_BayerGB2RGB
            elif bayer == 2:
                mode = cv2.cv.CV_BayerRG2RGB
            else: # this shuold be only bayer == 3
                mode = cv2.cv.CV_BayerGR2RGB
            
            return cv2.cvtColor(data.astype(numpy.uint16),mode).astype(self.ftype)
        else:
            return data

    def updateBayerMatrix(self, *arg):
        # we are forced to ignore *arg because this
        # function is connected  to multiple signals
        img = self.framelist[self.image_idx]
        arr = self.debayerize(img.getData(asarray=True))
        
        if self.wnd.rawGroupBox.isChecked():
            self.wnd.colorBar._is_rgb=True
        else:
            self.wnd.colorBar._is_rgb = img.isRGB()
            
        qimg=utils.arrayToQImage(arr,bw_jet=self.use_colormap_jet,fit_levels=self.fit_levels)
        self.showImage(qimg)
        
    def listItemChanged(self, idx):
        if self.wasStarted:
            return
        self.qapp.setOverrideCursor(QtCore.Qt.WaitCursor)
        self.image_idx = self.wnd.listWidget.currentRow()
        
        if idx >= 0:
            img = self.framelist[idx]
            qimg=utils.arrayToQImage(self.debayerize(img.getData(asarray=True)),bw_jet=self.use_colormap_jet,fit_levels=self.fit_levels)
            self.showImage(qimg)
            
            self.wnd.alignGroupBox.setEnabled(True)
            self.wnd.alignDeleteAllPushButton.setEnabled(True)
            self.updateAlignPointList()
            self.wnd.manualAlignGroupBox.setEnabled(True)
        else:
            self.clearImage()
            self.wnd.alignGroupBox.setEnabled(False)
            self.wnd.alignDeleteAllPushButton.setEnabled(False)
            self.wnd.manualAlignGroupBox.setEnabled(False)
            
        self.wnd.colorBar.repaint()
        self.qapp.restoreOverrideCursor()
        
    def manualAlignListItemChanged(self,idx):
        item = self.wnd.listWidgetManualAlign.item(idx)
        if item is None:
            return        
        self.dif_image_idx=item.original_id
        img = self.framelist[item.original_id]
        self.qapp.setOverrideCursor(QtCore.Qt.WaitCursor)
        self.current_image=utils.arrayToQImage(img.getData(asarray=True),bw_jet=self.use_colormap_jet,fit_levels=self.fit_levels)
        self.wnd.doubleSpinBoxOffsetX.setValue(img.offset[0])
        self.wnd.doubleSpinBoxOffsetY.setValue(img.offset[1])
        self.wnd.spinBoxOffsetT.setValue(img.angle)
        self.updateImage()
        self.qapp.restoreOverrideCursor()

    def currentManualAlignListItemChanged(self, cur_item):
        if cur_item == None:
            return False
        elif cur_item.checkState()==2:
            if self.__operating!=True:
                self.__operating=True
                self.ref_image_idx=cur_item.original_id
                #self.ref_image = Qt.QImage(self.framelist[cur_item.original_id])
                img = self.framelist[cur_item.original_id]
                self.ref_image=utils.arrayToQImage(img.getData(asarray=True),bw_jet=self.use_colormap_jet,fit_levels=self.fit_levels)
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
            pnt=self.framelist[self.image_idx].alignpoints[idx]
            self.wnd.spinBoxXAlign.setValue(pnt[0])
            self.wnd.spinBoxYAlign.setValue(pnt[1])
        else:
            self.wnd.spinBoxXAlign.setEnabled(False)
            self.wnd.spinBoxYAlign.setEnabled(False)
            self.wnd.removePointPushButton.setEnabled(False)
            self.wnd.spinBoxXAlign.setValue(0)
            self.wnd.spinBoxYAlign.setValue(0)
            
    def addAlignPoint(self):
        
        if self.dlg.autoSizeCheckBox.checkState()==2:
            r_w=int(self.currentWidth/10)
            r_h=int(self.currentHeight/10)
            r_l=max(r_w,r_h)
            self.autoalign_rectangle=(r_l,r_h)
            self.dlg.rWSpinBox.setValue(r_l)
            self.dlg.rHSpinBox.setValue(r_l)
        
        imagename=self.wnd.listWidget.item(self.image_idx).text()
        idx=1
        for i in range(self.wnd.alignPointsListWidget.count()):
            pname='#{0:05d}'.format(i+1)
            if self.framelist[0].alignpoints[i][2] != pname:
                idx=i+1
                break
            else:
                idx=i+2
                
        pname='#{0:05d}'.format(idx)
        q=Qt.QListWidgetItem(pname)
        q.setToolTip(tr('image') +imagename+tr('\nalign point ')+pname)
        self.wnd.alignPointsListWidget.insertItem(idx-1,q)
        
        if(len(self.framelist[self.image_idx].alignpoints)==0):
            self.wnd.removePointPushButton.setEnabled(False)
            
        for frm in self.framelist:
           frm.alignpoints.insert(idx-1,[0,0,pname,False])

        self.imageLabel.repaint()
        self.wnd.alignPointsListWidget.setCurrentRow(idx-1)
        return (idx-1)
    
    def removeAlignPoint(self):
        
        point_idx=self.wnd.alignPointsListWidget.currentRow()
        
        for frm in self.framelist:
            frm.alignpoints.pop(point_idx)
            
        self.wnd.alignPointsListWidget.setCurrentRow(-1) #needed to avid bugs
        item = self.wnd.alignPointsListWidget.takeItem(point_idx)
        
        if(len(self.framelist[self.image_idx].alignpoints)==0):
            self.wnd.removePointPushButton.setEnabled(False)
            
        del item
        
        self.updateImage()
        
    def updateAlignPointList(self):
        self.wnd.alignPointsListWidget.clear()
        imagename=self.wnd.listWidget.item(self.wnd.listWidget.currentRow()).text()
        for pnt in self.framelist[self.image_idx].alignpoints:
            pname=pnt[2]
            q=Qt.QListWidgetItem(pname,self.wnd.alignPointsListWidget)
            q.setToolTip(tr('image') +imagename+tr('\nalign point ')+pname)

    def shiftX(self,val):
        if (self.point_idx >= 0):
            pnt = self.framelist[self.image_idx].alignpoints[self.point_idx]
            pnt[0]=val
            if pnt[3]==True:
                pnt[3]=False
            self.imageLabel.repaint()

    def shiftY(self,val):
        if (self.point_idx >= 0):
            pnt = self.framelist[self.image_idx].alignpoints[self.point_idx]
            pnt[1]=val
            if pnt[3]==True:
                pnt[3]=False
            self.imageLabel.repaint()
    
    def shiftOffsetX(self,val):
        if (self.dif_image_idx >= 0):
            self.framelist[self.dif_image_idx].offset[0]=val
            self.imageLabel.repaint()
    
    def shiftOffsetY(self,val):
        if (self.dif_image_idx >= 0):
            self.framelist[self.dif_image_idx].offset[1]=val
            self.imageLabel.repaint()
    
    def rotateOffsetT(self, val):
        if (self.dif_image_idx >= 0):
            self.framelist[self.dif_image_idx].angle=val
            self.imageLabel.repaint()
    
    def updateToolBox(self, idx):
        self.ref_image_idx=-1
        self.qapp.setOverrideCursor(QtCore.Qt.WaitCursor)
        if (idx<=1) and (self._old_tab_idx>1):
            self.showAlignPoints=True
            try:
                try:
                    img = self.framelist[self.image_idx]
                except IndexError:
                    img = self.framelist[self.image_idx]
                qimg=utils.arrayToQImage(self.debayerize(img.getData(asarray=True)),bw_jet=self.use_colormap_jet,fit_levels=self.fit_levels)
                self.showImage(qimg)
            except IndexError:
                pass #maybe there are no images in the list yet?
                
        if (idx>1):
            self.showAlignPoints=False
            self.clearImage()
        
        if idx==1:
            self.use_cursor = QtCore.Qt.CrossCursor
            self.wnd.imageViewer.setCursor(QtCore.Qt.CrossCursor)
            self.imageLabel.setCursor(QtCore.Qt.CrossCursor)
        else:
            self.use_cursor = QtCore.Qt.OpenHandCursor
            self.wnd.imageViewer.setCursor(QtCore.Qt.OpenHandCursor)
            self.imageLabel.setCursor(QtCore.Qt.OpenHandCursor)
        
        if idx==2:
            utils.trace("Setting up manual alignment controls")
            self.manual_align=True
            utils.trace("Updating list of available images")
            self.updateAlignList()
            if self.wnd.listWidgetManualAlign.count()>0:
                img=self.framelist[self.wnd.listWidgetManualAlign.item(0).original_id]
                utils.trace("Loading reference image")
                self.ref_image = utils.arrayToQImage(img.getData(asarray=True),bw_jet=self.use_colormap_jet,fit_levels=self.fit_levels)
                utils.trace("Selecting reference image")
                self.wnd.listWidgetManualAlign.setCurrentRow(0)
                self.updateImage()
        else:
            self.manual_align=False
        
        if (idx==5):
            if (self._avg != None):
                self.updateResultImage()
            if (len(self.framelist)>0):
                self.wnd.alignPushButton.setEnabled(True)
                self.wnd.avrPushButton.setEnabled(True)

        self.imageLabel.repaint()
        self._old_tab_idx=idx
        self.qapp.restoreOverrideCursor()
        
    def newProject(self):
        self.wnd.toolBox.setCurrentIndex(0)
        self.wnd.captureGroupBox.setChecked(False)
        
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

        del self._drk
        del self._avg
        del self._flt

        self._drk=None
        self._avg=None
        self._flt=None
    
        self.manual_align=False

        self.currentWidth=0
        self.currentHeight=0
        self.currentDepht=0
        
        self.result_w=0
        self.result_h=0
        self.result_d=3
        
        self.current_project_fname=None

        del self.framelist
        del self.darkframelist
        del self.flatframelist

        self.framelist=[]
        self.darkframelist=[]
        self.flatframelist=[]

        self.setZoom(1)
        self.setZoomMode(1,True)
        self.wnd.alignPushButton.setEnabled(False)
        self.wnd.avrPushButton.setEnabled(False)
        self.wnd.saveResultPushButton.setEnabled(False)
        self.wnd.levelsPushButton.setEnabled(False)
        self.wnd.alignGroupBox.setEnabled(False)
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
        
    def saveProjectAs(self):
        self.current_project_fname = str(Qt.QFileDialog.getSaveFileName(self.wnd, tr("Save the project"),
                                         os.path.join(self.current_dir,'Untitled.prj'),
                                         "Project (*.prj);;All files (*.*)",None,
                                         self._dialog_options))
        if self.current_project_fname == '':
            self.current_project_fname=None
            return
        self._save_project()

    def saveProject(self):
        if self.current_project_fname is None:
            self.saveProjectAs()
        else:
            self._save_project()

    def corruptedMsgBox(self,info=None):
            msgBox = Qt.QMessageBox(self.wnd)
            msgBox.setText(tr("The project is invalid or corrupted!"))
            if info!=None:
                msgBox.setInformativeText(str(info))
            msgBox.setIcon(Qt.QMessageBox.Critical)
            msgBox.exec_()
            return False

    def _save_project(self):
        
        self.lock(False)
        self.progress.reset()
        self.statusBar.showMessage(tr('saving project, please wait...'))
        
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
        
        total_dark = len(self.darkframelist)
        total_flat = len(self.flatframelist)
        total_imgs = len(self.framelist)
        
        self.progress.setMaximum(total_dark+total_flat+total_imgs-1)
        
        count=0
        
        #<dark-frams> section
        for i in self.darkframelist:

            self.progress.setValue(count)
            count+=1
            
            im_dark_name = i.tool_name
            im_dark_url  = i.url
            im_dark_page = i.page
            image_node = doc.createElement('image')
            image_node.setAttribute('name',im_dark_name)
            
            dark_frames_node.appendChild(image_node)
            
            url=doc.createElement('url')
            image_node.appendChild(url)
            url_txt=doc.createTextNode(im_dark_url)
            url.appendChild(url_txt)
            url.setAttribute('page',str(im_dark_page))

        #<flat-frames> section
        for i in self.flatframelist:
            
            self.progress.setValue(count)
            count+=1

            im_flat_name = i.tool_name
            im_flat_url  = i.url
            im_flat_page = i.page
            image_node = doc.createElement('image')
            image_node.setAttribute('name',im_flat_name)
            
            flat_frames_node.appendChild(image_node)
            
            url=doc.createElement('url')
            image_node.appendChild(url)
            url_txt=doc.createTextNode(im_flat_url)
            url.appendChild(url_txt)  
            url.setAttribute('page',str(im_flat_page))
            
        #<frames> section
        for img in self.framelist:
            
            self.progress.setValue(count)
            count+=1
            
            im_used = str(img.getProperty('listItem').checkState())
            im_name = str(img.tool_name)
            im_url  = img.url
            im_page = img.page
            image_node = doc.createElement('image')
            image_node.setAttribute('name',im_name)
            image_node.setAttribute('used',im_used)
            
            pict_frames_node.appendChild(image_node)

            for point in img.alignpoints:
                point_node=doc.createElement('align-point')
                point_node.setAttribute('x',str(int(point[0])))
                point_node.setAttribute('y',str(int(point[1])))
                point_node.setAttribute('id',str(point[2]))
                point_node.setAttribute('aligned',str(point[3]))
                image_node.appendChild(point_node)
            
            offset_node=doc.createElement('offset')
            offset_node.setAttribute('x',str(float(img.offset[0])))
            offset_node.setAttribute('y',str(float(img.offset[1])))
            offset_node.setAttribute('theta',str(float(img.angle)))
            image_node.appendChild(offset_node)

            url=doc.createElement('url')
            image_node.appendChild(url)
            url_txt=doc.createTextNode(im_url)
            url.appendChild(url_txt)
            url.setAttribute('page',str(im_page))

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
            self.unlock()
            return
        
        self.unlock()

    def loadProject(self):
        old_fname = self.current_project_fname
        project_fname = str(Qt.QFileDialog.getOpenFileName(self.wnd,
                                                           tr("Open a project"),
                                                           os.path.join(self.current_dir,'Untitled.prj'),
                                                           "Project (*.prj);;All files (*.*)", None,
                                                           self._dialog_options)
                           )

        if project_fname == '':
            return False

        try:
            dom = minidom.parse(project_fname)
        except Exception as err:
            return self.corruptedMsgBox(err)       

        self.statusBar.showMessage(tr('loading project, please wait...'))
        self.lock(False)

        try:
            root = dom.getElementsByTagName('project')[0]
            
            information_node = root.getElementsByTagName('information')[0]
            dark_frames_node = root.getElementsByTagName('dark-frames')[0]
            flat_frames_node = root.getElementsByTagName('flat-frames')[0]
            pict_frames_node = root.getElementsByTagName('frames')[0]
            
            total_dark = len(dark_frames_node.getElementsByTagName('image'))
            total_flat = len(flat_frames_node.getElementsByTagName('image'))
            total_imgs =len(pict_frames_node.getElementsByTagName('image'))
            
            self.progress.reset()
            self.progress.setMaximum(total_dark+total_flat+total_imgs-1)
            count=0
                
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
                        
            darkframelist=[]
            darkListWidgetElements = []    
            for node in dark_frames_node.getElementsByTagName('image'):
                self.progress.setValue(count)
                count+=1
                im_dark_name = node.getAttribute('name')
                url_dark_node = node.getElementsByTagName('url')[0]
                im_dark_url = url_dark_node.childNodes[0].data
                if url_dark_node.attributes.has_key('page'):
                    im_dark_page = url_dark_node.getAttribute('page')
                    darkfrm=utils.frame(im_dark_url,int(im_dark_page),skip_loading=True)
                else:
                    darkfrm=utils.frame(im_dark_url,0,skip_loading=True)
                darkfrm.tool_name=im_dark_name
                darkfrm.width=imw
                darkfrm.height=imh
                darkfrm.mode=dep
                darkframelist.append(darkfrm)
                q=Qt.QListWidgetItem(darkfrm.tool_name,None)
                q.setToolTip(darkfrm.long_tool_name)
                darkListWidgetElements.append(q)
                #darkfrm.addProperty("listItem",q)
                
            flatframelist=[]
            flatListWidgetElements = []    
            for node in flat_frames_node.getElementsByTagName('image'):
                self.progress.setValue(count)
                count+=1
                im_flat_name = node.getAttribute('name')
                url_flat_node = node.getElementsByTagName('url')[0]
                im_flat_url = url_flat_node.childNodes[0].data
                if url_flat_node.attributes.has_key('page'):
                    im_flat_page = url_flat_node.getAttribute('page')
                    flatfrm=utils.frame(im_flat_url,int(im_flat_page),skip_loading=True)
                else:
                    flatfrm=utils.frame(im_flat_url,0,skip_loading=True)
                flatfrm.tool_name=im_flat_name
                flatfrm.width=imw
                flatfrm.height=imh
                flatfrm.mode=dep
                flatframelist.append(flatfrm)
                q=Qt.QListWidgetItem(flatfrm.tool_name,None)
                q.setToolTip(flatfrm.long_tool_name)
                flatListWidgetElements.append(q)
                #flatfrm.addProperty("listItem",q)
                
            framelist=[]  
            listWidgetElements=[]
            for node in pict_frames_node.getElementsByTagName('image'):
                self.progress.setValue(count)
                count+=1
                im_name = node.getAttribute('name')
                im_used = int(node.getAttribute('used'))
                im_url_node  = node.getElementsByTagName('url')[0]
                im_url  = im_url_node.childNodes[0].data

                if im_url_node.attributes.has_key('page'):
                    im_page=im_url_node.getAttribute('page')
                    frm = utils.frame(im_url,int(im_page),skip_loading=True)
                else:
                    frm = utils.frame(im_url,0,skip_loading=True)


                for point in node.getElementsByTagName('align-point'):
                    point_id = point.getAttribute('id')
                    point_x  = int(point.getAttribute('x'))
                    point_y  = int(point.getAttribute('y'))
                    point_al = bool(point.getAttribute('aligned')=='True')
                    frm.alignpoints.append([point_x, point_y, point_id, point_al])
                
                offset_node=node.getElementsByTagName('offset')[0]
                offset_x=float(offset_node.getAttribute('x'))
                offset_y=float(offset_node.getAttribute('y'))

                if offset_node.attributes.has_key('theta'):
                    offset_t=float(offset_node.getAttribute('theta'))
                else:
                    offset_t=0
                
                frm.tool_name=im_name
                frm.width=imw
                frm.height=imh
                frm.mode=dep
                frm.setOffset([offset_x,offset_y])
                frm.setAngle(offset_t)
                q=Qt.QListWidgetItem(frm.tool_name,None)
                q.setToolTip(frm.long_tool_name)
                q.setCheckState(im_used)
                listWidgetElements.append(q)
                frm.addProperty("listItem",q)
                framelist.append(frm)
                
            
        except Exception as exc:
            self.current_project_fname=old_fname
            self.unlock()
            return self.corruptedMsgBox()
       
        self.newProject()
        
        self.current_project_fname=project_fname
        
        for item in flatListWidgetElements:
            self.wnd.flatListWidget.addItem(item)
            
        for item in darkListWidgetElements:
            self.wnd.darkListWidget.addItem(item)
            
        for item in listWidgetElements:
            self.wnd.listWidget.addItem(item)
        
        if 'RGB' in dep:
            self.wnd.colorBar._is_rgb=True
            self.wnd.colorBar.current_val=(0.0,0.0,0.0)
        else:
            self.wnd.colorBar._is_rgb=False
            self.wnd.colorBar.current_val=0.0     
        
        self.currentWidth=imw
        self.currentHeight=imh
        self.currentDepht=dep
        self.framelist=framelist
        self.darkframelist=darkframelist
        self.flatframelist=flatframelist
        self.image_idx=current_row
        self.master_dark_file=master_dark_url
        self.master_flat_file=master_flat_url
        self.wnd.listWidget.setCurrentRow(current_row)
        self.autoalign_rectangle=(ar_w, ar_h)
        self.max_points=max_points
        self.min_quality=min_quality
        self.auto_align_use_whole_image=use_whole_image
        
        self.current_dir=current_dir
        
        self.unlock()
        
        if (len(self.framelist)>0):
            self._unlock_cap_ctrls()

        self.wnd.masterDarkCheckBox.setCheckState(master_dark_checked)
        self.wnd.masterDarkLineEdit.setText(master_dark_url)
        self.wnd.darkMulDoubleSpinBox.setValue(master_dark_mul_factor)
        if (len(self.darkframelist)>0):
            self.wnd.darkClearPushButton.setEnabled(True)

        self.wnd.masterFlatCheckBox.setCheckState(master_flat_checked)
        self.wnd.masterFlatLineEdit.setText(master_flat_url)
        self.wnd.flatMulDoubleSpinBox.setValue(master_flat_mul_factor)
        if (len(self.flatframelist)>0):
            self.wnd.flatClearPushButton.setEnabled(True)

    def autoDetectAlignPoints(self):
        i = self.framelist[self.image_idx].getData(asarray=True)
        i = i.astype(numpy.float32)
        
        if 'RGB' in self.currentDepht:
            i=i.sum(2)/3.0
        
        rw=self.autoalign_rectangle[0]
        rh=self.autoalign_rectangle[1]
        
        hh=2*rh
        ww=2*rw
        
        g=i[hh:-hh,ww:-ww]

        del i
        
        min_dist = int(math.ceil((rw**2+rh**2)**0.5))

        if self.checked_autodetect_min_quality==2:
            self.min_quality=1
            points = []
            max_iteration=25
            while (len(points) < ((self.max_points/2)+1)) and (max_iteration>0):
                points = cv2.goodFeaturesToTrack(g,self.max_points,self.min_quality,min_dist)
                if points==None:
                    points=[]
                self.min_quality*=0.75
                max_iteration-=1

        else:
            points = cv2.goodFeaturesToTrack(g,self.max_points,self.min_quality,min_dist)
            if points==None:
                points=[]
            
        if len(points) > 0:            
            for p in points:
                self.point_idx=self.addAlignPoint()
                self.wnd.spinBoxXAlign.setValue(p[0][0]+ww)
                self.wnd.spinBoxYAlign.setValue(p[0][1]+hh)
                
        elif self.checked_autodetect_min_quality:
            msgBox = Qt.QMessageBox()
            msgBox.setText(tr("No suitable points foud!"))
            msgBox.setInformativeText(tr("Try to add them manually."))
            msgBox.setIcon(Qt.QMessageBox.Warning)
            msgBox.exec_()
        else:
            msgBox = Qt.QMessageBox()
            msgBox.setText(tr("No suitable points foud!"))
            msgBox.setInformativeText(tr("Try to modify the alignment settings."))
            msgBox.setIcon(Qt.QMessageBox.Warning)
            msgBox.exec_()

    def autoSetAlignPoint(self):
        image_idx=self.wnd.listWidget.currentRow()
        current_point=self.wnd.alignPointsListWidget.currentRow()
        self.statusBar.showMessage(tr('detecting points, please wait...'))
        
        current_frame = self.framelist[image_idx]
        
        for point_idx in range(len(current_frame.alignpoints)):
            self.point_idx=point_idx
            if not self._autoPointCv(point_idx, image_idx):
                self.wnd.alignPointsListWidget.setCurrentRow(current_point)
                return False
        self.wnd.alignPointsListWidget.setCurrentRow(current_point)
        self.point_idx=current_point

    def _autoPointCv(self, point_idx, image_idx=0):
        point = self.framelist[image_idx].alignpoints[point_idx]


        #if already detected and not moved
        skip=True   
        for i in range(len(self.framelist)):
            skip &= self.framelist[i].alignpoints[point_idx][3]

        #then skip            
        if skip:
            return True

        r_w=Int(self.autoalign_rectangle[0]/2)
        r_h=Int(self.autoalign_rectangle[1]/2)
        x1=point[0]-r_w
        x2=point[0]+r_w
        y1=point[1]-r_h
        y2=point[1]+r_h
        
        rawi = self.framelist[image_idx].getData(asarray=True)
        refi = rawi[y1:y2,x1:x2]
        del rawi
        
        cv_ref = refi.astype(numpy.float32)
        del refi
        
        self.progress.setMaximum(len(self.framelist)-1)
        self.lock()
        
        for i in range(len(self.framelist)):
            self.progress.setValue(i)

            frm = self.framelist[i]

            if self.progressWasCanceled():
                return False

            frm.alignpoints[point_idx][3]=True                

            if i == image_idx:
                continue
            self.statusBar.showMessage(tr('detecting point ')+str(point_idx+1)+tr(' of ')+str(len(self.framelist[image_idx].alignpoints))+tr(' on image ')+str(i)+tr(' of ')+str(len(self.framelist)-1))
            
            if self.auto_align_use_whole_image==2:
                rawi=frm.getData(asarray=True)
            else:
                rawi=frm.getData(asarray=True)[y1-r_h:y2+r_h,x1-r_w:x2+r_w]

            cv_im=rawi.astype(numpy.float32)
            
            del rawi
            
            min_dif = None
            min_point=(0,0)

            res = cv2.matchTemplate(cv_im,cv_ref,self.current_match_mode)
            minmax = cv2.minMaxLoc(res)
            del res            
            if self.auto_align_use_whole_image==2:
                frm.alignpoints[point_idx][0]=minmax[2][0]+r_w
                frm.alignpoints[point_idx][1]=minmax[2][1]+r_h
            else:
                frm.alignpoints[point_idx][0]=minmax[2][0]+x1
                frm.alignpoints[point_idx][1]=minmax[2][1]+y1
            
        self.unlock()
        
        return True
    
    def align(self):
        
        if self.align_dlg.exec_():
            align_derot = self.align_dlg.alignDerotateRadioButton.isChecked()
            align = align_derot or self.align_dlg.alignOnlyRadioButton.isChecked()
            derotate = align_derot or self.align_dlg.derotateOnlyRadioButton.isChecked()
        else:
            return False
        
        if self.current_align_method == 0:
            return self._alignPhaseCorrelation(align, derotate)
        elif self.current_align_method == 1:
            return self._alignAlignPoints(align, derotate)
        
    def _derotateAlignPoints(self, var_matrix):
        
        vecslist=[]   
        
        for i in self.framelist:
            _tmp = []
            
            for p in i.alignpoints:                
                _tmp.append(numpy.array(p[0:2])-i.offset[0:2])
                
            vecslist.append(_tmp)
            
        del _tmp
                    
        refs=vecslist[0]
                       
        nvecs = len(vecslist[0])
        
        angles=[0]

        for vecs in vecslist[1:]: 
            angle=0
            for i in range(nvecs):                

                x1=refs[i][0]
                y1=refs[i][1]
                x2=vecs[i][0]
                y2=vecs[i][1]
                
                vmod = (vecs[i][0]**2 + vecs[i][1]**2)**0.5
                rmod = (refs[i][0]**2 + refs[i][1]**2)**0.5
                
                if (vmod==0) or (rmod==0):
                    w[i]=0
                
                cosa=((x1*x2+y1*y2)/(vmod*rmod))
                sina=((x2*y1-x1*y2)/(vmod*rmod))
                
                if cosa>1:
                    #this should never never never occurs
                    cosa=1.0
                    
                if sina>1:
                    #this should never never never occurs
                    sina=1.0
                    
                angle+=(math.atan2(sina,cosa)*180.0/math.pi)*var_matrix[i]
        
            angle/=var_matrix.sum()

            angles.append(angle)

        for i in range(len(self.framelist)):
            self.framelist[i].angle=-angles[i]
        
    def _alignAlignPoints(self, align, derotate):
        
        if len(self.framelist) == 0:
            return False

        total_points = len(self.framelist[0].alignpoints)
        total_images = len(self.framelist)
        
        if (len(self.framelist) > 0) and (total_points>0):
            self.statusBar.showMessage(tr('Calculating image shift, please wait...'))

            self.progress.setMaximum(total_images-1)
            self.lock()
            
            mat = numpy.zeros((total_images,total_points,2))
            
            for i in range(total_images):
                for j in range(total_points):
                    p = self.framelist[i].alignpoints[j]
                    mat[i,j,0]=p[0]
                    mat[i,j,1]=p[1]
            
            x_avg = mat[...,0].mean()
            y_avg = mat[...,1].mean()
            
            mat2 = mat-[x_avg,y_avg]
            
            var = numpy.empty((len(mat[0])))
            avg = numpy.empty((len(mat[0]),2))

            for i in range(len(mat[0])):
                dist=(mat2[...,i,0]**2+mat2[...,i,1]**2)
                var[i]=dist.var()
                 
            del mat2

            w = 1/(var+0.00000001) #Added 0.00000001 to avoid division by zero
            del var
            
            if align:
                for img in self.framelist:
                    x=0
                    y=0
                    for j in range(len(img.alignpoints)):
                        x+=img.alignpoints[j][0]*w[j]
                        y+=img.alignpoints[j][1]*w[j]
                    
                    img.offset[0]=(x/w.sum())
                    img.offset[1]=(y/w.sum())

                    self.progress.setValue(i)
                    if ((i%25)==0) and self.progressWasCanceled():
                        return False
            else:
                for img in self.framelist:
                    img.offset[0]=0
                    img.offset[1]=0
                    
            self.unlock()
            self.statusBar.showMessage(tr('DONE'))
            
            if (total_points > 1) and derotate:
                self._derotateAlignPoints(w)
            
                rotation_center = (self.currentWidth/2,self.currentHeight/2)
            
                #compesate shift for rotation
                for img in self.framelist:
                    x=img.offset[0]-rotation_center[0]
                    y=img.offset[1]-rotation_center[1]
                    alpha = math.pi*img.angle/180.0

                    cosa  = math.cos(alpha)
                    sina  = math.sin(alpha)

                    #new shift
                    img.offset[0]=self.currentWidth/2+(x*cosa+y*sina)
                    img.offset[1]=self.currentWidth/2+(y*cosa-x*sina)
            else:
                for img in self.framelist:
                    img.angle=0
                    
            self.progress.setMaximum(3*len(self.framelist))
            
            if align:
                self.lock()
                self.statusBar.showMessage(tr('Calculating references, please wait...'))
                
                count=0
            
                ref_set=False
            
                for img in self.framelist:
                    self.progress.setValue(count)
                    count+=1
                    if self.progressWasCanceled():
                        return False
    
                    if img.isUsed():
                    
                        if not ref_set:
                            ref_x=img.offset[0]
                            ref_y=img.offset[1]
                            ref_set=True
                        else:
                            ref_x = min(ref_x,img.offset[0])
                            ref_y = min(ref_y,img.offset[1])
    
    
                for img in self.framelist:
                    self.progress.setValue(count)
                    count+=1

                    if self.progressWasCanceled():
                        return False
                    
                    if img.isUsed():
                        img.offset[0]=float(img.offset[0]-ref_x)
                        img.offset[1]=float(img.offset[1]-ref_y)
    
                self.progress.reset()
        
                self.unlock()
            else:
                for img in self.framelist:
                    img.setOffset([0,0])

                
    def _alignPhaseCorrelation(self, align, derotate):
        
        
        old_state = self.wnd.zoomCheckBox.checkState()
        self.wnd.zoomCheckBox.setCheckState(1)
        self.wnd.zoomCheckBox.setEnabled(False)
        
        self.statusBar.showMessage(tr('Computing phase correlation, please wait...'))
        self.clearImage()
        ref_set=False
        self.lock()
        self.progress.setMaximum(len(self.framelist))
        self.wnd.MainFrame.setEnabled(True)
        ref = None
            
        mask = utils.generateCosBell(self.currentWidth,self.currentHeight)
        old_rgb_mode = self.wnd.colorBar._is_rgb
        self.wnd.colorBar._is_rgb=False
        
        count=0
        
        sharp1=self.wnd.sharp1DoubleSpinBox.value()
        sharp2=self.wnd.sharp2DoubleSpinBox.value()
        
        for img in self.framelist:
            
            self.progress.setValue(count)
            count+=1

            if self.progressWasCanceled():
                self.wnd.colorBar._is_rgb=old_rgb_mode
                self.clearImage()
                self.unlock()
                self.wnd.zoomCheckBox.setEnabled(True)
                self.wnd.zoomCheckBox.setCheckState(old_state)
                self.statusBar.showMessage(tr('Cancelled by the user'))
                return False
            
            if img.isUsed():
                self.qapp.processEvents()
                if ref == None:
                    ref = img
                    ref_data = ref.getData(asarray=True)
                    if len(ref_data.shape)==3:
                        ref_data=ref_data.sum(2)
                    ref_data*=mask
                    ref.setOffset([0,0])
                else:
                    img_data=img.getData(asarray=True)
                    if len(img_data.shape)==3:
                        img_data=img_data.sum(2)
                    img_data*=mask
                    data=utils.register_image(ref_data,img_data,sharp1,sharp2,align,derotate)
                    self.statusBar.showMessage(tr('shift: ')+str(data[1])+', '+
                                               tr('rotation: ')+str(data[2]))
                    del img_data
                    if data[0]!=None:
                        self.showImage(utils.arrayToQImage(data[0]))
                    img.setOffset(data[1])
                    img.setAngle(data[2])
        del mask
        self.wnd.colorBar._is_rgb=old_rgb_mode
        self.clearImage()
        self.wnd.zoomCheckBox.setEnabled(True)
        self.wnd.zoomCheckBox.setCheckState(old_state)
        self.unlock()
        self.statusBar.showMessage(tr('DONE'))       
    

    def getStackingMethod(self, method, framelist, dark_image, flat_image, **args):
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
        if method==0:
            return self.average(framelist, dark_image, flat_image)
        elif method==1:
            return self.median(framelist, dark_image, flat_image)
        elif method==2:
            return self.sigmaclip(framelist, dark_image, flat_image,**args)
        elif method==3:
            return self.stddev(framelist, dark_image, flat_image)
        elif method==4:
            return self.variance(framelist, dark_image, flat_image)
        elif method==5:
            return self.maximum(framelist, dark_image, flat_image)
        elif method==6:
            return self.minimum(framelist, dark_image, flat_image)
        elif method==7:
            return self.product(framelist, dark_image, flat_image)
        else:
            #this should never happens
            utils.trace("Something that sould never happes has just happened!")
            utils.trace("An unknonw stacking method has been selected")
            return None
            
    
    def stack(self):

        del self._avg
        del self._drk
        del self._flt
        del self._old_avg
        del self._hst
                
        self._avg=None
        self._drk=None
        self._flt=None
        self._old_avg=None        
        self._oldhst=None
        self._hst=None
        
        dark_image=None
        dark_stdev=None

        """
        selecting method and setting options
        before stacking
        """
        if self.stack_dlg.exec_():
            dark_method=self.stack_dlg.darkStackingMethodComboBox.currentIndex()
            flat_method=self.stack_dlg.flatStackingMethodComboBox.currentIndex()
            lght_method=self.stack_dlg.ligthStackingMethodComboBox.currentIndex()
            
            dark_args={'lk':self.stack_dlg.darkLKappa.value(),
                       'hk':self.stack_dlg.darkHKappa.value(),
                       'iterations':self.stack_dlg.darkKIters.value()}
            
            flat_args={'lk':self.stack_dlg.flatLKappa.value(),
                       'hk':self.stack_dlg.flatHKappa.value(),
                       'iterations':self.stack_dlg.flatKIters.value()}
                       
            lght_args={'lk':self.stack_dlg.ligthLKappa.value(),
                       'hk':self.stack_dlg.ligthHKappa.value(),
                       'iterations':self.stack_dlg.ligthKIters.value()}
        else:
            return False
        
        self.lock(False)
        
        self.master_dark_file = str(self.wnd.masterDarkLineEdit.text())
        self.master_flat_file = str(self.wnd.masterFlatLineEdit.text())
        
        if (self.wnd.masterDarkCheckBox.checkState() == 2):
            if os.path.isfile(self.master_dark_file):
                drk=utils.frame(self.master_dark_file)
                self._drk=drk.getData(asarray=True, ftype=self.ftype)
            elif self.master_dark_file.replace(' ','').replace('\t','') == '':
                pass #ignore
            else:
                msgBox = Qt.QMessageBox()
                msgBox.setText(tr("Cannot open \'"+self.master_dark_file+"\':"))
                msgBox.setInformativeText(tr("the file does not exist."))
                msgBox.setIcon(Qt.QMessageBox.Critical)
                msgBox.exec_()
                return False
        elif (len(self.darkframelist)>0):
            self.statusBar.showMessage(tr('Creating master-dark, please wait...'))
            _drk=self.getStackingMethod(dark_method,self.darkframelist, None, None, **dark_args)
            if _drk==None:
                return False
            else:
                self._drk=_drk
                
        if (self.wnd.masterFlatCheckBox.checkState() == 2):
            if os.path.isfile(self.master_flat_file):
                flt=utils.frame(self.master_flat_file)
                self._flt=flt.getData(asarray=True, ftype=self.ftype)
            elif self.master_flat_file.replace(' ','').replace('\t','') == '':
                pass #ignore
            else:
                msgBox = Qt.QMessageBox()
                msgBox.setText(tr("Cannot open \'"+self.master_dark_file+"\':"))
                msgBox.setInformativeText(tr("the file does not exist."))
                msgBox.setIcon(Qt.QMessageBox.Critical)
                msgBox.exec_()
                return False
        elif (len(self.flatframelist)>0):
            self.statusBar.showMessage(tr('Creating master-flat, please wait...'))
            _flt=self.getStackingMethod(flat_method,self.flatframelist, self._drk, None,**flat_args)
            if _flt==None:
                return False
            else:
                self._flt=_flt
        
        self.statusBar.showMessage(tr('Stacking images, please wait...'))
        _avg=self.getStackingMethod(lght_method,self.framelist, self._drk, self._flt,**lght_args)
        if(_avg == None):
            self.unlock()
            return False
        else:
            self._avg=_avg
            self.statusBar.showMessage(tr('Generating histograhms...'))
            self._hst=utils.generateHistograhms(_avg,255)
            self.qapp.processEvents()
            del _avg
            self.updateResultImage()
            self.wnd.saveResultPushButton.setEnabled(True)
            self.wnd.levelsPushButton.setEnabled(True)
            self.statusBar.showMessage(tr('DONE'))
        self.unlock()
        
    def generateMasters(self, dark_image=None, flat_image=None):
        utils.trace("generating master frames\n")
        if (dark_image != None):
            master_dark=(dark_image*self.master_dark_mul_factor)
        else:
            master_dark=None
            
        if (flat_image != None):
            # this should avoid division by zero
            zero_mask = ((flat_image == 0).astype(self.ftype))*flat_image.max()
            corrected = flat_image+zero_mask
            del zero_mask
            normalizer = corrected.min()
            master_flat=((corrected/normalizer)*self.master_flat_mul_factor)
            del corrected
        else:
            master_flat=None
            
        return (master_dark, master_flat)
    
    def calibrate(self, image, master_dark=None, master_flat=None):
        if (master_dark == None) and (master_flat == None):
            utils.trace("skipping image calibration")
        else:
            utils.trace("calibrating image...")
            if master_dark!=None:
                utils.trace("calibrating image: subtracting master dark")
                image -=  master_dark
            
            if master_flat!=None:
                utils.trace("calibrating image: dividing by master flat")
                image /= master_flat  
                
        return self.debayerize(image)
            
    def registerImages(self, img, img_data):        
        if img.angle!=0:
            img_data = scipy.ndimage.interpolation.rotate(img_data,img.angle,order=0,reshape=False,mode='constant',cval=0.0)
        else:
            utils.trace("skipping rotation")
        
        shift=numpy.zeros([len(img_data.shape)])
        shift[0]=-img.offset[1]
        shift[1]=-img.offset[0]
        
        if (shift[0]!=0) or (shift[1]!=0):
            utils.trace("shifting of "+str(shift[0:2]))
            img_data = scipy.ndimage.interpolation.shift(img_data,shift,order=0,mode='constant',cval=0.0)
        else:
            utils.trace("skipping shift")
        del shift
        
        return img_data
            
    def average(self,framelist ,dark_image=None, flat_image=None):

        result=None
                
        master_dark, master_flat = self.generateMasters(dark_image,flat_image)

            
        total = len(framelist)
        
        self.statusBar.showMessage(tr('Adding images, please wait...'))
        
        self.progress.reset()
        self.progress.setMaximum(4*(total-1))
        
        count = 0
        progress_count=0
        
        for img in framelist:

            if self.progressWasCanceled():
                return None
                
            self.progress.setValue(progress_count)
            progress_count+=1
            
            if img.isUsed():
                count+=1
            else:
                progress_count+=3
                continue
            
            r=img.getData(asarray=True, ftype=self.ftype)
            
            self.progress.setValue(progress_count)
            progress_count+=1

            if self.progressWasCanceled():
                return None

            if img.isRGB() and (r.shape[2]>3):
                r = r[...,0:3]
                
            r = self.calibrate(r, master_dark, master_flat)
            
            if self.progressWasCanceled():
                return None
            self.progress.setValue(progress_count)
            progress_count+=1
            
            r = self.registerImages(img,r)
            
            if self.progressWasCanceled():
                return None
            self.progress.setValue(progress_count)
            progress_count+=1
                
            if result is None:
                result=r.copy()
            else:
                result+=r
            
            del r
            
        self.progress.setValue(4*(total-1))  
        self.statusBar.showMessage(tr('Computing final image...'))

        avg=result/count

        self.statusBar.clearMessage()

        return avg


    """
    Executes the 'operation' on each subregion of size 'subw'x'subh' of images stored in
    temporary files listed in filelist. the original shape of the images must be passed
    as 'shape'
    """
    def _operationOnSubregions(self,operation, filelist, shape, title="", subw=256, subh=256, **args):

        n_y_subs=shape[0]/subh
        n_x_subs=shape[1]/subw
        
        total_subs=(n_x_subs+1)*(n_y_subs+1)
        
        utils.trace("Executing operation splitting images in "+str(total_subs)+" sub-regions")
        self.statusBar.showMessage(tr('Computing') +' '+ str(title) + ', ' + tr('please wait...'))
        self.progress.reset
        self.progress.setMaximum(total_subs*(len(filelist)+1))
        progress_count = 0
        
        x=0
        y=0
        
        result=numpy.zeros(shape)
        
        mmaps = []
        
        if self.checked_compressed_temp==0:
            for fl in filelist:
                progress_count+=1
                self.progress.setValue(progress_count)                                
                if self.progressWasCanceled():
                    return None
                mmaps.append(utils.loadTmpArray(fl))
        
        count=0
        while y <= n_y_subs:
            x=0
            while x <= n_x_subs:
                
                xst=x*subw
                xnd=(x+1)*subw
                yst=y*subh
                ynd=(y+1)*subh
                
                lst=[]

                if self.checked_compressed_temp==2:
                    for fl in filelist:
                        progress_count+=1
                        self.progress.setValue(progress_count)                                
                        if self.progressWasCanceled():
                            return None
                        n=utils.loadTmpArray(fl)
                        sub=n[yst:ynd,xst:xnd].copy()
                        lst.append(sub)
                else:
                    for n in mmaps:
                        progress_count+=1
                        self.progress.setValue(progress_count)                                
                        if self.progressWasCanceled():
                            return None
                        sub=n[yst:ynd,xst:xnd].copy()
                        lst.append(sub)
                count+=1
                msg = tr('Computing ')+str(title)+tr(' on subregion ')+str(count)+tr(' of ')+str(total_subs)
                utils.trace(msg)
                self.statusBar.showMessage(msg)
                self.qapp.processEvents()
                if len(args)>0:
                    operation(lst, axis=0, out=result[yst:ynd,xst:xnd],**args)
                else:
                    operation(lst, axis=0, out=result[yst:ynd,xst:xnd])
                del lst
                x+=1
            y+=1
        del mmaps
        return result
    
    def sigmaClipping(self,array, axis=-1, out=None, **args):
        
        lkappa = args['lk']
        hkappa = args['hk']
        itr = args['iterations']        

        clipped = numpy.ma.masked_array(array)
        
        for i in range(itr):
            sigma = numpy.std(array, axis=axis)
            mean = numpy.mean(array, axis=axis)

            min_clip=mean-lkappa*sigma
            max_clip=mean+hkappa*sigma
            
            del sigma
            del mean
            
            clipped = numpy.ma.masked_less(clipped, min_clip)
            clipped = numpy.ma.masked_greater(clipped, max_clip)
            
            del min_clip
            del max_clip
            
        if out is None:
            return numpy.ma.average(clipped, axis=axis)
        else:
            out[...] = numpy.ma.average(clipped, axis=axis)
    
    def medianSigmaClipping(self,array, axis=-1, out=None, **args):
        
        lkappa = args['lmk']
        hkappa = args['hmk']
        itr = args['miterations']        

        clipped = numpy.ma.masked_array(array)
        
        for i in range(itr):
            sigma = numpy.std(array, axis=axis)
            mean = numpy.median(array, axis=axis)

            min_clip=mean-lkappa*sigma
            max_clip=mean+hkappa*sigma
            
            del sigma
            del mean
            
            clipped = numpy.ma.masked_less(clipped, min_clip)
            clipped = numpy.ma.masked_greater(clipped, max_clip)
            
            del min_clip
            del max_clip
            
        if out is None:
            return numpy.ma.median(clipped, axis=axis)
        else:
            out[...] = numpy.ma.median(clipped, axis=axis)
    
    
    def stddev(self,framelist, dark_image=None, flat_image=None, **args):
        return self.operationOnImages(numpy.std,tr('standard deviation'),framelist, dark_image, flat_image)
    
    def variance(self,framelist, dark_image=None, flat_image=None, **args):
        return self.operationOnImages(numpy.var,tr('variance'),framelist, dark_image, flat_image)
    
    def sigmaclip(self,framelist, dark_image=None, flat_image=None, **args):
        return self.operationOnImages(self.sigmaClipping,tr('sigma clipping'),framelist, dark_image, flat_image, **args)
    
    def median(self,framelist, dark_image=None, flat_image=None, **args):
        return self.operationOnImages(numpy.median,tr('median'),framelist, dark_image, flat_image)
    
    def mean(self,framelist, dark_image=None, flat_image=None, **args):
        return self.operationOnImages(numpy.mean,tr('average'),framelist, dark_image, flat_image)

    def maximum(self,framelist, dark_image=None, flat_image=None, **args):
        return self.operationOnImages(numpy.max,tr('maximum'),framelist, dark_image, flat_image)

    def minimum(self,framelist, dark_image=None, flat_image=None, **args):
        return self.operationOnImages(numpy.min,tr('minumium'),framelist, dark_image, flat_image)

    def product(self,framelist, dark_image=None, flat_image=None, **args):
        return self.operationOnImages(numpy.prod,tr('product'),framelist, dark_image, flat_image)

        
    def operationOnImages(self,operation, name,framelist, dark_image=None, flat_image=None, **args):

        result=None
                
        master_dark, master_flat = self.generateMasters(dark_image,flat_image)

        total = len(framelist)
        
        self.statusBar.showMessage(tr('Registering images, please wait...'))
        
        self.progress.reset()
        self.progress.setMaximum(4*(total-1))
        
        count = 0
        progress_count=0
        
        original_shape=None
        
        tmpfilelist=[]
        
        for img in framelist:

            if self.progressWasCanceled():
                return False
                
            self.progress.setValue(progress_count)
            progress_count+=1
            
            if img.isUsed():
                count+=1
            else:
                progress_count+=3
                continue
            
            r=img.getData(asarray=True, ftype=self.ftype)
            
            if original_shape == None:
                original_shape = r.shape
            
            self.progress.setValue(progress_count)
            progress_count+=1

            if self.progressWasCanceled():
                return False

            if img.isRGB() and (r.shape[2]>3):
                r = r[...,0:3]
                
            r = self.calibrate(r, master_dark, master_flat)
            
            if self.progressWasCanceled():
                return False
            self.progress.setValue(progress_count)
            progress_count+=1
                               
            r = self.registerImages(img,r)
            
            if self.progressWasCanceled():
                return False
            self.progress.setValue(progress_count)
            progress_count+=1
            
            tmpfilelist.append(utils.storeTmpArray(r,self.temp_path,self.checked_compressed_temp==2))
        
        mdn=self._operationOnSubregions(operation,tmpfilelist,original_shape,name,256,256, **args)
        
        del tmpfilelist
        
        self.statusBar.clearMessage()

        return mdn
    
    def levelsDialogButtonBoxClickedEvent(self, button):
        pushed = self.levels_dlg.buttonBox.standardButton(button)
        
        if pushed == self.levels_dlg.buttonBox.Reset:
            self.levels_dlg.dataClippingGroupBox.setChecked(False)
            self.resetLevels()
        elif pushed == self.levels_dlg.buttonBox.Apply:
            self.backUpLevels()
            self._avg=self.getNewLevels(self._old_avg)
            self.updateResultImage()
        elif pushed == self.levels_dlg.buttonBox.Discard:
            self.discardLevels()
            
    def resetLevels(self):
        self.levels_dlg.curveTypeComboBox.setCurrentIndex(0)
        self.levels_dlg.aDoubleSpinBox.setValue(0)
        self.levels_dlg.bDoubleSpinBox.setValue(1)
        self.levels_dlg.oDoubleSpinBox.setValue(0)
        self.levels_dlg.mDoubleSpinBox.setValue(1)
        self.levels_dlg.nDoubleSpinBox.setValue(2.718281828459045)
        self.updateHistograhm2()

    def discardLevels(self):
        self.levels_dlg.curveTypeComboBox.setCurrentIndex(self._old_funcidx)
        self.levels_dlg.aDoubleSpinBox.setValue(self._old_a)
        self.levels_dlg.bDoubleSpinBox.setValue(self._old_b)
        self.levels_dlg.oDoubleSpinBox.setValue(self._old_o)
        self.levels_dlg.mDoubleSpinBox.setValue(self._old_m)
        self.levels_dlg.nDoubleSpinBox.setValue(self._old_n)        
        self.updateHistograhm2()

        
    def backUpLevels(self):
        self._old_funcidx = self.levels_dlg.curveTypeComboBox.currentIndex()
        self._old_a = float(self.levels_dlg.aDoubleSpinBox.value())
        self._old_b = float(self.levels_dlg.bDoubleSpinBox.value())
        self._old_o = float(self.levels_dlg.oDoubleSpinBox.value())
        self._old_m = float(self.levels_dlg.mDoubleSpinBox.value())
        self._old_n = float(self.levels_dlg.nDoubleSpinBox.value())
    
    def editLevels(self):
        self.backUpLevels()
        
        if self._old_avg == None:
            self._oldhst=self._hst.copy()
            self._old_avg=self._avg.copy()
            self.resetLevels()
        
        if self.levels_dlg.exec_()==1:
            self._avg=self.getNewLevels(self._old_avg)

        self.updateResultImage()
    
    def getLevelsClippingRange(self):
        if self.levels_dlg.dataClippingGroupBox.isChecked():
            if self.levels_dlg.dataClipping8BitRadioButton.isChecked():
                data_max = 255
                data_min = 0
            elif self.levels_dlg.dataClipping16BitRadioButton.isChecked():
                data_max = 65535
                data_min = 0
        else:
            data_max = None
            data_min = None
        return (data_min,data_max)
    
    def getNewLevels(self, data):
        
        A = float(self.levels_dlg.aDoubleSpinBox.value())
        B = float(self.levels_dlg.bDoubleSpinBox.value())
        o = float(self.levels_dlg.oDoubleSpinBox.value())
        m = float(self.levels_dlg.mDoubleSpinBox.value())
        n = float(self.levels_dlg.nDoubleSpinBox.value())    
        
        if self.levelfunc_idx == 0: #linear
            data = A+B*data
        elif self.levelfunc_idx == 1: #logarithmic
            data = A+B*numpy.emath.logn(n,(o+m*data))
        elif self.levelfunc_idx == 2: #power
            data = A+B*((o+m*data)**n)
        elif self.levelfunc_idx == 3: #exponential
            data = A+B*(n**(o+m*data))

        if self.levels_dlg.dataClippingGroupBox.isChecked():
            if self.levels_dlg.dataClipping8BitRadioButton.isChecked():
                data_max = 255
                data_min = 0
            elif self.levels_dlg.dataClipping16BitRadioButton.isChecked():
                data_max = 65535
                data_min = 0
                
            return data.clip(data_min,data_max)
        else:
            return data
    
    def updateHistograhm(self, curve_idx):
        
        if self._ignore_histogrham_update:
            return
        
        scenablied = self.levels_dlg.dataClippingGroupBox.isChecked()
        clipping   = scenablied and self.levels_dlg.dataClippingClipDataRadioButton.isChecked()
        streching  = scenablied and self.levels_dlg.dataClippingFitDataRadioButton.isChecked()
        
        A = float(self.levels_dlg.aDoubleSpinBox.value())
        B = float(self.levels_dlg.bDoubleSpinBox.value())
        o = float(self.levels_dlg.oDoubleSpinBox.value())
        m = float(self.levels_dlg.mDoubleSpinBox.value())
        n = float(self.levels_dlg.nDoubleSpinBox.value())
    
        self.levelfunc_idx=curve_idx
        
        data_min,data_max = self.getLevelsClippingRange()
        
        if streching:
            if curve_idx == 0: #linear
                tmphst=self._oldhst[0,1]
            elif curve_idx == 1: #logarithmic
                tmphst=numpy.emath.logn(n,(o+m*self._oldhst[0,1]))
            elif curve_idx == 2: #power
                tmphst=((o+m*self._oldhst[0,1])**n)
            elif curve_idx == 3: #exponential
                tmphst=(n**(o+m*self._oldhst[0,1]))
            
            minh = min(tmphst)
            maxh = max(tmphst)
            
            B = (data_max-data_min)/(maxh-minh)
            A = -(data_max-data_min)*minh/(maxh-minh)
            
            self._ignore_histogrham_update = True
            self.levels_dlg.aDoubleSpinBox.setValue(A)
            self.levels_dlg.bDoubleSpinBox.setValue(B)
            self._ignore_histogrham_update = False
            
        
        for i in range(len(self._hst)):
            if curve_idx == 0: #linear
                self._hst[i,1]=A+B*self._oldhst[i,1]
            elif curve_idx == 1: #logarithmic
                self._hst[i,1]=A+B*numpy.emath.logn(n,(o+m*self._oldhst[i,1]))
            elif curve_idx == 2: #power
                self._hst[i,1]=A+B*((o+m*self._oldhst[i,1])**n)
            elif curve_idx == 3: #exponential
                self._hst[i,1]=A+B*(n**(o+m*self._oldhst[i,1]))

            if clipping:
                mask = (self._hst[i,1]>data_min)*(self._hst[i,1]<data_max)
                self._hst[i,0]=self._oldhst[i,0]*mask[:-1]
            else:
                self._hst[i,0]=self._oldhst[i,0]
                
        self.levels_dlg.update()
        
        
    def updateHistograhm2(self, *arg,**args):
        self.updateHistograhm(self.levelfunc_idx)
        
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

    def getDestDir(self):
        destdir = str(Qt.QFileDialog.getExistingDirectory(self.wnd,tr("Choose the output folder"),self.current_dir))
        self.save_dlg.lineEditDestDir.setText(str(destdir))
        
    def saveResult(self):
        
        if self.save_dlg.exec_() != 1:
            return False
        destdir=str(self.save_dlg.lineEditDestDir.text())
        
        while not os.path.isdir(destdir):
            msgBox = Qt.QMessageBox()
            msgBox.setText(tr("The selected output folder is not a directory\nor it does not exist!"))
            msgBox.exec_()
            if self.save_dlg.exec_() != 1:
                return False
            destdir=str(self.save_dlg.lineEditDestDir.text())

        self.lock()
        self.qapp.processEvents()
        name=str(self.save_dlg.lineEditFileName.text())

        if self.save_dlg.radioButtonJpeg.isChecked():
            frmat='jpg'
        elif self.save_dlg.radioButtonPng.isChecked():
            frmat='png'
        elif self.save_dlg.radioButtonTiff.isChecked():
            frmat='tiff'
        elif self.save_dlg.radioButtonFits.isChecked():
            frmat='fits'
        elif self.save_dlg.radioButtonNumpy.isChecked():
            frmat='numpy'
        
        if self.save_dlg.radioButton8.isChecked():
            bits=8
        elif self.save_dlg.radioButton16.isChecked():
            bits=16
        elif self.save_dlg.radioButton32.isChecked():
            bits=32
        elif self.save_dlg.radioButton64.isChecked():
            bits=64
    
        if frmat=='fits':
            self._save_fits(destdir,name,bits)
        elif frmat=='numpy':
            self._save_numpy(destdir,name,bits)
        else:
            self._save_cv2(destdir,name,frmat, bits)
        
        self.unlock()
        
    def _save_fits(self,destdir, name, bits):

        #header = pyfits

        if bits==32:
            outbits=numpy.float32
        elif bits==64:
            outbits=numpy.float64

        rgb_mode = (self.save_dlg.rgbFitsCheckBox.checkState()==2)
        
        avg_name=os.path.join(destdir,name)
        self._imwrite_fits_(avg_name,self._avg.astype(outbits),rgb_mode)
        
        if self.save_dlg.saveMastersCheckBox.checkState()==2:
            if (self._drk!=None):
                drk_name=os.path.join(destdir,name+"-master-dark")
                self._imwrite_fits_(drk_name,self._drk.astype(outbits),rgb_mode)
            
            if (self._flt!=None):
                flt_name=os.path.join(destdir,name+"-master-flat")
                self._imwrite_fits_(flt_name,self._flt.astype(outbits),rgb_mode)
    
    def _save_numpy(self,destdir, name, bits):

        #header = pyfits

        if bits==32:
            outbits=numpy.float32
        elif bits==64:
            outbits=numpy.float64
        
        avg_name=os.path.join(destdir,name)
        numpy.save(avg_name,self._avg.astype(outbits))
        
        if self.save_dlg.saveMastersCheckBox.checkState()==2:
            if (self._drk!=None):
                drk_name=os.path.join(destdir,name+"-master-dark")
                numpy.save(drk_name,self._drk.astype(outbits))
            
            if (self._flt!=None):
                flt_name=os.path.join(destdir,name+"-master-flat")
                numpy.save(flt_name,self._flt.astype(outbits))
    
    def _save_cv2(self,destdir, name, frmt, bits):
               
        if bits==8:
            rawavg=utils.normToUint8(self._avg, False)
            rawdrk=utils.normToUint8(self._drk, False)
            rawflt=utils.normToUint8(self._flt, False)
        elif bits==16:
            rawavg=utils.normToUint16(self._avg, False)
            rawdrk=utils.normToUint16(self._drk, False)
            rawflt=utils.normToUint16(self._flt, False)
        else:
            #this should never be executed!
            msgBox = Qt.QMessageBox()
            msgBox.setText(tr("Cannot save image:"))
            msgBox.setInformativeText(tr("Unsupported format ")+str(bits)+"-bit "+tr("for")+" "+str(frmt))
            msgBox.setIcon(Qt.QMessageBox.Critical)
            msgBox.exc_()
            return False
                
        avg_name=os.path.join(destdir,name+"."+frmt)
        
        if frmt=='jpg':
            flags=(cv2.cv.CV_IMWRITE_JPEG_QUALITY,int(self.save_dlg.spinBoxIQ.value()))
        elif frmt=='png':
            flags=(cv2.cv.CV_IMWRITE_PNG_COMPRESSION,int(self.save_dlg.spinBoxIC.value()))
        else:
            flags=None
            
        if not self._imwrite_cv2_(avg_name,rawavg,flags):
            return False
        
        
        if self.save_dlg.saveMastersCheckBox.checkState()==2:
            if (self._drk!=None):
                drk_name=os.path.join(destdir,name+"-master-dark."+frmt)
                self._imwrite_cv2_(drk_name,rawdrk,flags)
            
            if (self._flt!=None):
                flt_name=os.path.join(destdir,name+"-master-flat."+frmt)
                self._imwrite_cv2_(flt_name,rawflt,flags)
        
    def _imwrite_cv2_(self, name, data, flags):
        try:
            if os.path.exists(name):
                msgBox = Qt.QMessageBox()
                msgBox.setText(tr("A file named")+" \""+
                               os.path.basename(name)
                               +"\" "+tr("already exists."))
                msgBox.setInformativeText(tr("Do you want to overwite it?"))
                msgBox.setIcon(Qt.QMessageBox.Question)
                msgBox.setStandardButtons(Qt.QMessageBox.Yes | Qt.QMessageBox.No)
                if msgBox.exec_() == Qt.QMessageBox.Yes:
                    os.remove(name)
                else:
                    return False
            if len(data.shape) == 3:
                return cv2.imwrite(name,data[...,(2,1,0)],flags)
            elif len(data.shape) == 2:
                return cv2.imwrite(name,data,flags)
            else:
                #this should never happens
                raise TypeError("Cannot save "+str(len(data.shape))+"-D images")
        except Exception as exc:
            msgBox = Qt.QMessageBox()
            msgBox.setText(tr("Cannot save image due to cv2 exception:"))
            msgBox.setInformativeText(str(exc))
            msgBox.setIcon(Qt.QMessageBox.Critical)
            msgBox.exc_()
            return False
            
    def _fits_secure_imwrite(self, hdulist, url):
        if os.path.exists(url):
            msgBox = Qt.QMessageBox()
            msgBox.setText(tr("A file named")+" \""+
                           os.path.basename(url)
                           +"\" "+tr("already exists."))
            msgBox.setInformativeText(tr("Do you want to overwite it?"))
            msgBox.setIcon(Qt.QMessageBox.Question)
            msgBox.setStandardButtons(Qt.QMessageBox.Yes | Qt.QMessageBox.No)
            if msgBox.exec_() == Qt.QMessageBox.Yes:
                os.remove(url)
            else:
                return False
           
        hdulist.writeto(url)
    
    def _imwrite_fits_(self, name, data, rgb_mode=True):

        if rgb_mode and (len(data.shape) == 3):
            hdu_r = utils.pyfits.PrimaryHDU(data[...,0])
            
            hdu_g = utils.pyfits.ImageHDU(data[...,1])
            hdu_g.update_ext_name('GREN')
            
            hdu_b = utils.pyfits.ImageHDU(data[...,2])
            hdu_b.update_ext_name('BLUE')
            
            hdl = utils.pyfits.HDUList([hdu_r,hdu_g,hdu_b])
            
            self._fits_secure_imwrite(hdl,name+'-RGB.fits')
            
        elif (len(data.shape) == 3):
            hdu_r = utils.pyfits.PrimaryHDU(data[...,0])
            hdl_r = utils.pyfits.HDUList([hdu_r])
            self._fits_secure_imwrite(hdl_r,name+'-R.fits')
            
            hdu_g = utils.pyfits.ImageHDU(data[...,1])
            hdl_g = utils.pyfits.HDUList([hdu_g])
            self._fits_secure_imwrite(hdl_g,name+'-G.fits')
            
            hdu_b = utils.pyfits.ImageHDU(data[...,2])
            hdl_b = utils.pyfits.HDUList([hdu_b])
            self._fits_secure_imwrite(hdl_b,name+'-B.fits')
            
        else:    
            hdu = utils.pyfits.PrimaryHDU(data)
            hdl = utils.pyfits.HDUList([hdu])
            self._fits_secure_imwrite(hdl,name+'.fits')

loading.setValue(80)