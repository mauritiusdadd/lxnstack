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
        
        self._old_tab_idx=0
        self.__operating=False
        self._photo_time_clock=0

        self.current_match_mode=cv2.TM_SQDIFF

        self.qapp=qapp
        
        self._generateOpenStrings()

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
        self.save_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'save_dialog.ui'))
        
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
                
        self.filelist=[]
        self.offsetlist=[]
        self.darkfilelist=[]
        self.flatfilelist=[]
        
        self.alignpointlist=[]

        self.tracking_align_point=False
        self.checked_seach_dark_flat=0
        self.checked_autodetect_rectangle_size=2
        self.checked_autodetect_min_quality=2
        self.checked_colormap_jet=2
        self.checked_rgb_fits=0
        
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
        
        self.statusLabelMousePos = Qt.QLabel()
        self.statusBar = self.wnd.statusBar()
        self.setUpStatusBar()
        self.imageLabel= Qt.QLabel()
        self.imageLabel.setMouseTracking(True)
        self.imageLabel.setAlignment(QtCore.Qt.AlignTop)
        self.wnd.imageViewer.setWidget(self.imageLabel)
        self.wnd.imageViewer.setAlignment(QtCore.Qt.AlignTop)
        
        self.wnd.colorBar.current_val=None
        self.wnd.colorBar.max_val=1
        self.wnd.colorBar.min_val=0
        self.wnd.colorBar._is_rgb=False
        
        self.bw_colormap=None
        self.rgb_colormap=None
        
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
        
        # paint callback for colorBar
        self.wnd.colorBar.__paintEvent__= self.wnd.colorBar.paintEvent #base implementation
        self.wnd.colorBar.paintEvent = self.colorBarPaintEvent #new callback        

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
        self.dlg.jetCheckBox.setCheckState(2)
        
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
        self.dlg.jetCheckBox.stateChanged.connect(self.setJetmapMode)
                
        self.save_dlg.pushButtonDestDir.released.connect(self.getDestDir)
        
        self.wnd.actionOpen_files.triggered.connect(self.doLoadFiles)
        self.wnd.actionOpen_video.triggered.connect(self.doLoadVideo)
        self.wnd.actionNew_project.triggered.connect(self.doNewProject)
        self.wnd.actionSave_project_as.triggered.connect(self.doSaveProjectAs)
        self.wnd.actionSave_project.triggered.connect(self.doSaveProject)
        self.wnd.actionLoad_project.triggered.connect(self.doLoadProject)
        self.wnd.actionPreferences.triggered.connect(self.doSetPreferences)
        self.wnd.actionAbout.triggered.connect(self.doShowAbout)
        self.wnd.actionUserManual.triggered.connect(self.doShowUserMan)

        self.__resetPreferencesDlg()
                    
        if not os.path.isdir(self.save_image_dir):
            os.makedirs(self.save_image_dir)

    def _generateOpenStrings(self):
        self.supported_formats = utils.getSupportedFormats()

        self.images_extensions = ' ('
        for ext in self.supported_formats.keys():
            self.images_extensions+='*'+str(ext)+' '
        self.images_extensions += ');;'
        
        ImageTypes={}
        
        for ext in self.supported_formats.keys():
            key=str(self.supported_formats[ext])
            
            if key in ImageTypes:
                ImageTypes[key]+=' *'+str(ext)
            else:
                ImageTypes[key]=' *'+str(ext)

        for ext in ImageTypes:
            self.images_extensions+=tr('Image')+' '+ext+' : '+ImageTypes[ext]
            self.images_extensions+='('+ImageTypes[ext]+');;'

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
      
    def setJetmapMode(self,val):
        if val==0:
            self.use_colormap_jet=False
        else:
            self.use_colormap_jet=True
        
        if self.current_image != None:
            self.current_image = utils.arrayToQImage(self.current_image._original_data,bw_jet=self.use_colormap_jet)
            self.generateScaleMaps()
            self.updateImage()
        
    def openImage(self,file_name, page=0, asarray=False, asuint8=False):
        file_ext = os.path.splitext(file_name)[1].lower()
        
        if file_ext in self.supported_formats:
            file_type = self.supported_formats[file_ext]
        else:
            return None
        
        #choosing among specific loaders
        if file_type == 'FITS':

            if not utils.FITS_SUPPORT:
                #this should never happens
                return None
                
            hdu_table=utils.pyfits.open(file_name)

            RGB_mode = (self.checked_rgb_fits==2)

            #checking for 3 ImageHDU (red, green and blue components)
            if RGB_mode and (len(hdu_table) >= 3):
                layers = []
                for i in hdu_table:
                    if i.is_image and (len(i.shape)==2):
                        layers.append(i)

                if len(layers) == 3:
                    if ((layers[0].shape == layers[1].shape) and
                        (layers[0].shape == layers[2].shape)):
                        is_RGB=True
                else:
                    #if there are more or less than 3 ImageHDU
                    #then it is not an RGB fits file
                    is_RGB=False
            else:
                is_RGB=False
                

            if RGB_mode and is_RGB:
                if page!=0:
                    return None
                else:
                    imh,imw=layers[0].shape
                    img = numpy.zeros((imh,imw,len(layers)))
                
                    for j in range(len(layers)):
                        img[...,j]=layers[j].data
                    
                    if asarray:
                        if asuint8:
                            return utils.normToUint8(img)
                        else:
                            return img.astype(numpy.float)
                    else:
                        return utils.Image.fromarray(utils.normToUint8(img))

            else:
                i=0
                npages=page
                while(i>=0):
                    try:
                        imagehdu = hdu_table[i]
                    except IndexError:
                        i=-1
                        return None
                    
                    if not imagehdu.is_image:
                        i+=1
                        continue
                    
                    try: # retrieves data dimension
                        naxis=int(imagehdu.header['NAXIS'])
                    except:
                        #this should never occur since 'NAXIS' keyword
                        #should exists in each header
                        try:
                            #however if data is not corrupted
                            #this should work
                            naxis=len(imagehdu.shape)
                        except:
                            print("ERROR: corrupted data")
                            return None
                    else:
                        if naxis <= 1:
                            #cannot handle 0-D or 1-D image data!
                            print("WARNING: unsupported data format")
                        else:
                            axis=imagehdu.shape[:-2] #number of image layers
                            imh,imw=imagehdu.shape[-2:] #image size
                            
                            #computing number of layers for current ImageHDU
                            total=1
                            for x in axis:
                                total*=x

                            if npages >= total:
                                #the request layer is not in this ImageHDU
                                npages-=total
                                continue
                            else:
                                #the request layer is in this ImageHDU
                                index = []
                                #computing layer index:
                                r_axis=list(axis)
                                r_axis.reverse()
                                for x in r_axis:
                                    cidx=npages%x
                                    index[0:0]=[cidx]
                                    npages=(npages-cidx)/x
                                index=tuple(index)

                                #scaled data is automatically rescaled
                                #and BZERO and BSCALE are removed
                                data = imagehdu.data[index]
                                    
                                if asarray:
                                    if asuint8:
                                        return utils.normToUint8(data)
                                    else:
                                        return data.astype(numpy.float)
                                else:
                                    return utils.Image.fromarray(utils.normToUint8(data))
                    
                    finally:
                        i+=1
                
        elif file_type =='???':
            #New codecs will be added here
            return False
        else:   
        
            try:
                cv2img = cv2.imread(file_name,-1)
            except:
                cv2img=None
                
            if (page==0) and (cv2img!=None):
                img = numpy.empty_like(cv2img)

                if (len(cv2img.shape) == 3) and (cv2img.shape[2]==3):
                    img=cv2img[...,(2,1,0)]
                else:
                    img=cv2img
                
                if asarray:
                    if asuint8:
                        return utils.normToUint8(numpy.asarray(img))
                    else:
                        return (numpy.asarray(img)).astype(numpy.float)
                else:
                    return utils.Image.fromarray(utils.normToUint8(img))
            else:
                try:
                
                    img = utils.Image.open(file_name)
                    img.seek(page)
                    #testing decoder
                    pix = img.getpixel((0,0))
                except EOFError:
                    return None
                except IOError as err:
                    if page==0:
                        msgBox = Qt.QMessageBox(self.wnd)
                        msgBox.setText(str(err))
                        msgBox.setIcon(Qt.QMessageBox.Critical)
                        msgBox.exec_()
                    return None
           
                if asarray:
                    if asuint8:
                        return utils.normToUint8(numpy.asarray(img))
                    else:
                        return (numpy.asarray(img)).astype(numpy.float)
                else:
                    return img

    

    def showUserMan(self):
        webbrowser.open(os.path.join(paths.DOCS_PATH,'usermanual.html'))

    def lock(self):
        self.statusLabelMousePos.setText('')
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
        
        self.dlg.jetCheckBox.setCheckState(self.checked_colormap_jet)
        self.dlg.rgbFitsCheckBox.setCheckState(self.checked_rgb_fits)

        self.dlg.devComboBox.setCurrentIndex(self.current_cap_combo_idx)

        self.dlg.rWSpinBox.setValue(self.autoalign_rectangle[0])
        self.dlg.rHSpinBox.setValue(self.autoalign_rectangle[1])

        self.dlg.maxPointsSpinBox.setValue(self.max_points)
        self.dlg.minQualityDoubleSpinBox.setValue(self.min_quality)

        self.dlg.langFileLineEdit.setText(self.__current_lang)
        self.dlg.videoSaveLineEdit.setText(self.save_image_dir)
        
        self.dlg.wholeImageCheckBox.setChecked(self.auto_align_use_whole_image)
        self.dlg.autoSizeCheckBox.setChecked(self.checked_autodetect_rectangle_size)
        self.dlg.minQualitycheckBox.setCheckState(self.checked_autodetect_min_quality)

        self.dlg.autoFolderscheckBox.setCheckState(self.checked_seach_dark_flat)

    def __set_save_video_dir(self):
        self.save_image_dir = str(Qt.QFileDialog.getExistingDirectory(self.dlg,tr("Choose the detination folder"),self.save_image_dir))
        self.dlg.videoSaveLineEdit.setText(self.save_image_dir)
        
    def setPreferences(self):

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
            #update settings
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
            self.checked_autodetect_rectangle_size=int(self.dlg.autoSizeCheckBox.checkState())
            self.checked_colormap_jet=int(self.dlg.jetCheckBox.checkState())
            self.checked_rgb_fits=int(self.dlg.rgbFitsCheckBox.checkState())
            self.checked_autodetect_min_quality=int(self.dlg.minQualitycheckBox.checkState())
            self.checked_seach_dark_flat=int(self.dlg.autoFolderscheckBox.checkState())
            return True
        else:
            #discard changes
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
                        self.filelist.append((name,0))
                        self.alignpointlist.append([])
                        self.offsetlist.append([0,0])
                        
                        q=Qt.QListWidgetItem(os.path.basename(name),self.wnd.listWidget)
                        q.setCheckState(2)
                        q.setToolTip(name)
                        self.wnd.listWidget.setCurrentItem(q)
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

        if len(img.shape)==2:
            dep='L'
        elif (len(img.shape)==3) and img.shape[-1]==3:
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
        
        if len(img.shape)==3:
            self.wnd.colorBar._is_rgb=True
        else:
            self.wnd.colorBar._is_rgb=False
        
        self.showImage(utils.arrayToQImage(img,2,1,0, bw_jet=self.use_colormap_jet))
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
                    
                    self.filelist.append((name,0))
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
               i = self.openImage(master_dark_file)
               if i==None:
                   msgBox = Qt.QMessageBox(self.wnd)
                   msgBox.setText(tr("Cannot open image")+" \""+str(master_dark_file)+"\"")
                   msgBox.setIcon(Qt.QMessageBox.Critical)
                   msgBox.exec_()
                   return False
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
               i = self.openImage(master_flat_file)
               if i==None:
                   msgBox = Qt.QMessageBox(self.wnd)
                   msgBox.setText(tr("Cannot open image")+" \""+str(master_flat_file)+"\"")
                   msgBox.setIcon(Qt.QMessageBox.Critical)
                   msgBox.exec_()
                   return False
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
        settings.setValue("autodetect_rectangle", int(self.dlg.autoSizeCheckBox.checkState()))
        settings.setValue("autodetect_quality", int(self.dlg.minQualitycheckBox.checkState()))
        settings.setValue("max_align_points",int(self.max_points))
        settings.setValue("min_point_quality",float(self.min_quality))
        settings.setValue("use_whole_image", int(self.dlg.wholeImageCheckBox.checkState()))
        settings.setValue("use_colormap_jet", int(self.dlg.jetCheckBox.checkState()))
        settings.setValue("auto_rgb_fits", int(self.dlg.rgbFitsCheckBox.checkState()))
        settings.setValue("auto_search_dark_flat",int(self.dlg.autoFolderscheckBox.checkState()))
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
        self.checked_autodetect_rectangle_size=settings.value("autodetect_rectangle",None,int)
        self.dlg.autoSizeCheckBox.setCheckState(self.checked_autodetect_rectangle_size)
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
        self.generateScaleMaps()
        return val

    #mouseMoveEvent callback    
    def imageLabelMouseMoveEvent(self, event):
        val = self.imageLabel.__mouseMoveEvent__(event)
        x=Int(event.x()/self.actual_zoom)
        y=Int(event.y()/self.actual_zoom)

        if (self.current_image != None) and (not self.manual_align):
            imshape = self.current_image._original_data.shape
            if ((y>=0) and (y < imshape[0]) and
                (x>=0) and (x < imshape[1])):
                pix_val=self.current_image._original_data[y,x]
                self.wnd.colorBar.current_val=pix_val
                self.wnd.colorBar.repaint()
                self.statusLabelMousePos.setText('position=(x:'+str(x)+',y:'+str(y)+') value='+str(pix_val))
                
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
                
            if cb._is_rgb == True:
                cb.setPixmap(Qt.QPixmap.fromImage(self.rgb_colormap))
                
                xr = int(float(cb.current_val[0]-cb.min_val)/float(cb.max_val-cb.min_val)*(cb.width()-_gno))+_gpo
                xg = int(float(cb.current_val[1]-cb.min_val)/float(cb.max_val-cb.min_val)*(cb.width()-_gno))+_gpo
                xb = int(float(cb.current_val[2]-cb.min_val)/float(cb.max_val-cb.min_val)*(cb.width()-_gno))+_gpo
                
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
                    x = int(float(cb.current_val-cb.min_val)/float(cb.max_val-cb.min_val)*(cb.width()-_gno))+_gpo
                except ValueError:
                    x = -1
                
                painter.setCompositionMode(22)
                
                painter.drawLine(x,4,x,self.wnd.colorBar.height()-4)

                painter.drawText(fnt_size-4,y,str(cb.min_val))
                painter.drawText(cb.width()-(fnt_size-2)*len(max_txt),y,max_txt)

                painter.setCompositionMode(0)

            del painter
            
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
        if self._avg!=None:
            img = utils.arrayToQImage(self._avg,bw_jet=self.use_colormap_jet)
            self.showImage(img)
        else:
            self.clearImage()
        
    def showImage(self, image):
        self.current_image = image
        self.updateImage()
            
    def clearImage(self):
        self.current_image=None
        self.imageLabel.setPixmap(Qt.QPixmap())

    def generateScaleMaps(self):
        # bw or jet colormap
        data1 = numpy.arange(0,self.wnd.colorBar.width()-5)
        data2 = numpy.array([data1]*(self.wnd.colorBar.height()-8))
        qimg = utils.arrayToQImage(data2,bw_jet=self.use_colormap_jet)
        self.bw_colormap = qimg

        #rgb colormap
        data1 = numpy.arange(0,self.wnd.colorBar.width())*255/self.wnd.colorBar.width()
        data2 = numpy.array([data1]*int((self.wnd.colorBar.height()-8)/3))
        hh=len(data2)
        data3 = numpy.zeros((3*hh,len(data1),3))
       
        data3[0:hh,0:,0]=data2
        data3[hh:2*hh,0:,1]=data2
        data3[2*hh:3*hh,0:,2]=data2
        
        qimg = utils.arrayToQImage(data3,bw_jet=self.use_colormap_jet)
        self.rgb_colormap = qimg

    def updateImage(self, paint=True, overrided_image=None):
        
        if overrided_image != None:
            current_image=overrided_image
        else:
            current_image=self.current_image

        if current_image is None:
            return False
            
        if self.zoom_enabled:
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
            self.wnd.colorBar.max_val=current_image._original_data.max()
            self.wnd.colorBar.min_val=current_image._original_data.min()
            
            #this shuold avoid division by zero
            if  self.wnd.colorBar.max_val ==  self.wnd.colorBar.min_val:
                self.wnd.colorBar.max_val=self.wnd.colorBar.max_val+1
                self.wnd.colorBar.min_val=self.wnd.colorBar.min_val-1
                
            #self.generateScaleMaps()
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

        self.statusBar.showMessage(tr('Loading files, please wait...'))

        if len(self.filelist) > 0:
            imw = self.currentWidth
            imh = self.currentHeight
            dep = self.currentDepht[0:3]
        elif len(newlist) > 0:
            ref = self.openImage(str(newlist[0]))
            if ref==None:
                msgBox = Qt.QMessageBox(self.wnd)
                msgBox.setText(tr("Cannot open image")+" \""+str(newlist[0])+"\"")
                msgBox.setIcon(Qt.QMessageBox.Critical)
                msgBox.exec_()
                return False
            imw,imh = ref.size
            dep = ref.mode
            del ref            
            self.currentWidth=imw
            self.currentHeight=imh
            self.currentDepht=dep

            if self.dlg.autoSizeCheckBox.checkState()==2:
                r_w=int(imw/10)
                r_h=int(imh/10)
                r_l=max(r_w,r_h)
                self.autoalign_rectangle=(r_l,r_l)
                self.dlg.rWSpinBox.setValue(r_l)
                self.dlg.rHSpinBox.setValue(r_l)
            
            if 'RGB' in dep:
                self.wnd.colorBar._is_rgb=True
                self.wnd.colorBar.current_val=(0,0,0)
            else:
                self.wnd.colorBar._is_rgb=False
                self.wnd.colorBar.current_val=0
                
            self.wnd.colorBar.max_val=1
            self.wnd.colorBar.min_val=0
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
                page = 0
                img=self.openImage(str(i),page)
                if img==None:
                    msgBox = Qt.QMessageBox(self.wnd)
                    msgBox.setText(tr("Cannot open image")+" \""+str(i)+"\"")
                    msgBox.setIcon(Qt.QMessageBox.Critical)
                    msgBox.exec_()
                    continue
                while img != None:
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
                        self.filelist.append((str(i),page))
                        self.alignpointlist.append([])
                        self.offsetlist.append([0,0])
                        q=Qt.QListWidgetItem(os.path.basename(str(i))+'-page'+str(page))
                        q.setCheckState(2)
                        q.setToolTip(i)
                        listitemslist.append(q)
                    page+=1
                    img=self.openImage(str(i),page)
            self.progress.setValue(count)
            if self.progressWasCanceled():
                self.filelist=oldlist
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
        
        if (len(self.filelist)>0):
            self._unlock_cap_ctrls()

        self.statusBar.showMessage(tr('Ready'))

    def doAddDarkFiles(self, directory=None, ignoreErrors=False):
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
            
        self.progress.setMaximum(len(files))
        self.lock()
        count=0

        for fn in files:

            self.qapp.processEvents()
            self.progress.setValue(count)
            
            if (os.path.isfile(str(fn)) and 
               not (str(fn) in self.darkfilelist)):

               page=0
               i=self.openImage(str(fn),page)
               if i==None:
                    if not ignoreErrors:
                        msgBox = Qt.QMessageBox(self.wnd)
                        msgBox.setText(tr("Cannot open image")+" \""+str(fn)+"\"")
                        msgBox.setIcon(Qt.QMessageBox.Critical)
                        msgBox.exec_()
                    continue
               while i != None:
                   imw,imh=i.size
                   dep = i.mode
                   if ((self.currentWidth == imw) and
                       (self.currentHeight == imh) and
                       (self.currentDepht == dep)):
                       self.darkfilelist.append((str(fn),page))
                       q=Qt.QListWidgetItem(os.path.basename(str(fn))+"-page"+str(page),self.wnd.darkListWidget)
                       q.setToolTip(str(fn)+", page "+str(page))
                   page+=1
                   i=self.openImage(str(fn),page)

            if self.progressWasCanceled():
                return False
            count+=1
            
        self.unlock()
        
        if (len(self.darkfilelist) == 0):
            return False
        else:
            self.wnd.darkClearPushButton.setEnabled(True)
        return True
        
    def doClearDarkList(self):
        self.darkfilelist=[]
        self.wnd.darkListWidget.clear()
        self.wnd.darkClearPushButton.setEnabled(False)
        
    def doAddFlatFiles(self, directory=None, ignoreErrors=False):
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

        self.progress.setMaximum(len(files))
        self.lock()
        count=0
        
        for fn in files:
            
            self.qapp.processEvents()
            self.progress.setValue(count)
            
            if (os.path.isfile(fn) and 
               not (fn in self.darkfilelist)):

               page=0
               i=self.openImage(str(fn),page)
               if i==None:
                    if not ignoreErrors:
                        msgBox = Qt.QMessageBox(self.wnd)
                        msgBox.setText(tr("Cannot open image")+" \""+str(fn)+"\"")
                        msgBox.setIcon(Qt.QMessageBox.Critical)
                        msgBox.exec_()
                    continue
               while i != None:
                   imw,imh=i.size
                   dep = i.mode
                   if ((self.currentWidth == imw) and
                       (self.currentHeight == imh) and
                       (self.currentDepht == dep)):
                       self.flatfilelist.append((str(fn),page))
                       q=Qt.QListWidgetItem(os.path.basename(str(fn))+"-page"+str(page),self.wnd.flatListWidget)
                       q.setToolTip(str(fn)+", page "+str(page))
                   page+=1
                   i=self.openImage(str(fn),page)

            if self.progressWasCanceled():
                return False
            count+=1
            
        self.unlock()
        
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
        self._avg = None

    def removeImage(self):
        q = self.wnd.listWidget.takeItem(self.wnd.listWidget.currentRow())
        self.filelist.pop(self.wnd.listWidget.currentRow())
        self.offsetlist.pop(self.wnd.listWidget.currentRow())
        self.alignpointlist.pop(self.wnd.listWidget.currentRow())
        del q
        
        self._avg=None

        if (len(self.filelist)==0):
            self.wnd.manualAlignGroupBox.setEnabled(False)
            self.wnd.remPushButton.setEnabled(False)
            self.wnd.clrPushButton.setEnabled(False)
            self.wnd.listCheckAllBtn.setEnabled(False)
            self.wnd.listUncheckAllBtn.setEnabled(False)
            self.statusLabelMousePos.setText('')
            self.wnd.colorBar.setPixmap(Qt.QPixmap())
            self.clearImage()
        elif self.image_idx >= len(self.filelist):
            self.wnd.listWidget.setCurrentRow(len(self.filelist)-1)
            self.listItemChanged(self.wnd.listWidget.currentRow())

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
            img = self.openImage(self.filelist[idx][0],self.filelist[idx][1],True)
            qimg=utils.arrayToQImage(img,bw_jet=self.use_colormap_jet)
            self.showImage(qimg)
            
            self.wnd.alignGroupBox.setEnabled(True)
            self.wnd.alignDeleteAllPushButton.setEnabled(True)
            self.updateAlignPointList()
            self.wnd.manualAlignGroupBox.setEnabled(True)
        else:
            self.showImage(None)
            self.wnd.alignGroupBox.setEnabled(False)
            self.wnd.alignDeleteAllPushButton.setEnabled(False)
            self.wnd.manualAlignGroupBox.setEnabled(False)
            
        self.wnd.colorBar.repaint()
            
    def manualAlignListItemChanged(self,idx):
        item = self.wnd.listWidgetManualAlign.item(idx)
        self.dif_image_idx=item.original_id
        #self.current_image=Qt.QImage(self.filelist[item.original_id])
        img = self.openImage(self.filelist[item.original_id][0],self.filelist[item.original_id][1],True)
        self.current_image=utils.arrayToQImage(img,bw_jet=self.use_colormap_jet)
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
                #self.ref_image = Qt.QImage(self.filelist[cur_item.original_id])
                img = self.openImage(self.filelist[cur_item.original_id][0],self.filelist[cur_item.original_id][1],True)
                self.ref_image=utils.arrayToQImage(img,bw_jet=self.use_colormap_jet)
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

        if (idx!=5) and (idx!=2) and (self._old_tab_idx==5):
            img = self.openImage(self.filelist[self.image_idx][0],self.filelist[self.image_idx][1],True)
            qimg=utils.arrayToQImage(img,bw_jet=self.use_colormap_jet)
            self.showImage(qimg)
                
                
        if idx==2:
            self.manual_align=True
            self.updateAlignList()
            if len(self.filelist)>0:
                img=self.openImage(self.filelist[0][0],self.filelist[0][1],True)
                self.ref_image = utils.arrayToQImage(img,bw_jet=self.use_colormap_jet)
            self.updateImage()
        else:
            self.manual_align=False
            self.imageLabel.repaint()
        
        if (idx==5):
            if (self._avg != None):
                self.updateResultImage()
            if (len(self.filelist)>0):
                self.wnd.alignPushButton.setEnabled(True)
                self.wnd.avrPushButton.setEnabled(True)
        self._old_tab_idx=idx
    def newProject(self):

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
        self.result_d=3
        
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
                                         "Project (*.prj);;All files (*.*)"))
        if self.current_project_fname == '':
            self.current_project_fname=None
            return
        self.__save_project__()

    def saveProject(self):
        if self.current_project_fname is None:
            self.saveProjectAs()
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
            im_dark_url  = self.darkfilelist[i][0]
            im_dark_page = self.darkfilelist[i][1]
            image_node = doc.createElement('image')
            image_node.setAttribute('name',im_dark_name)
            
            dark_frames_node.appendChild(image_node)
            
            url=doc.createElement('url')
            image_node.appendChild(url)
            url_txt=doc.createTextNode(im_dark_url)
            url.appendChild(url_txt)
            url.setAttribute('page',str(im_dark_page))

        #<flat-frames> section
        for i in range(len(self.flatfilelist)):
            im_flat_name = str(self.wnd.flatListWidget.item(i).text())
            im_flat_url  = self.flatfilelist[i][0]
            im_flat_page = self.flatfilelist[i][1]
            image_node = doc.createElement('image')
            image_node.setAttribute('name',im_flat_name)
            
            flat_frames_node.appendChild(image_node)
            
            url=doc.createElement('url')
            image_node.appendChild(url)
            url_txt=doc.createTextNode(im_flat_url)
            url.appendChild(url_txt)  
            url.setAttribute('page',str(im_flat_page))
            
        #<frames> section
        for i in range(len(self.filelist)):
            im_used = str(self.wnd.listWidget.item(i).checkState())
            im_name = str(self.wnd.listWidget.item(i).text())
            im_url  = self.filelist[i][0]
            im_page = self.filelist[i][1]
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
            return

    def loadProject(self):
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
                url_dark_node = node.getElementsByTagName('url')[0]
                im_dark_url = url_dark_node.childNodes[0].data
                q=Qt.QListWidgetItem(im_dark_name,None)
                q.setToolTip(im_dark_url)
                darkListWidgetElements.append(q)
                if url_dark_node.attributes.has_key('page'):
                    im_dark_page = url_dark_node.getAttribute('page')
                    darkfilelist.append((im_dark_url,int(im_dark_page)))
                else:
                    darkfilelist.append((im_dark_url,0))
                
            flatfilelist=[]
            flatListWidgetElements = []    
            for node in flat_frames_node.getElementsByTagName('image'):
                im_flat_name = node.getAttribute('name')
                url_flat_node = node.getElementsByTagName('url')[0]
                im_flat_url = url_flat_node.childNodes[0].data
                q=Qt.QListWidgetItem(im_flat_name,None)
                q.setToolTip(im_flat_url)
                flatListWidgetElements.append(q)
                if url_flat_node.attributes.has_key('page'):
                    im_flat_page = url_flat_node.getAttribute('page')
                    flatfilelist.append((im_flat_url,int(im_flat_page)))
                else:
                    flatfilelist.append((im_flat_url,0))

                
            alignpointlist=[]
            offsetlist=[]
            filelist=[]  
            listWidgetElements=[]
            for node in pict_frames_node.getElementsByTagName('image'):
                im_name = node.getAttribute('name')
                im_used = int(node.getAttribute('used'))
                im_url_node  = node.getElementsByTagName('url')[0]
                im_url  = im_url_node.childNodes[0].data
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
                if im_url_node.attributes.has_key('page'):
                    im_page=im_url_node.getAttribute('page')
                    filelist.append((im_url,int(im_page)))
                else:
                    filelist.append((im_url,0))
            
        except Exception as exc:
            self.current_project_fname=old_fname
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
            self.wnd.colorBar.current_val=(0,0,0)
        else:
            self.wnd.colorBar._is_rgb=False
            self.wnd.colorBar.current_val=0                
        
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
        i = self.openImage(self.filelist[self.image_idx][0],self.filelist[self.image_idx][1],True)
        i = i.astype(numpy.float32)
        
        if 'RGB' in self.currentDepht:
            i = cv2.cvtColor(i,cv2.cv.CV_BGR2GRAY)
        
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
                self.wnd.spinBoxXAlign.setValue(p[0][0]+hh)
                self.wnd.spinBoxYAlign.setValue(p[0][1]+ww)
                
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
        
        rawi = self.openImage(self.filelist[image_idx][0],self.filelist[image_idx][1],True)
        #refi = rawi.crop((x1,y1,x2,y2))
        refi = rawi[y1:y2,x1:x2]
        del rawi
        
        cv_ref = refi.astype(numpy.float32)
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
                rawi=self.openImage(self.filelist[i][0],self.filelist[i][1],True)
            else:
                rawi=self.openImage(self.filelist[i][0],self.filelist[i][1],True)[y1-r_h:y2+r_h,x1-r_w:x2+r_w]

            cv_im=rawi.astype(numpy.float32)
            
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
                drk=self.openImage(self.master_dark_file,asarray=True)
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
                flt=self.openImage(str(self.master_flat_file),asarray=True)
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
            
            mat=((numpy.array(self.alignpointlist)[...,0:2]).astype('float'))
            
            x_avg = mat[...,0].mean()
            y_avg = mat[...,1].mean()
            
            mat2 = mat-[x_avg,y_avg]
            
            var = numpy.empty((len(mat[0]),2))
            avg = numpy.empty((len(mat[0]),2))

            for i in range(len(mat[0])):
                var[i][0]=(mat2[...,i,0].var())
                var[i][1]=(mat2[...,i,1].var())
                 
            del mat2

            w = 1/(var+0.00000001) #Added 0.00000001 to avoid division by zero
            del var
            
            wx=w[...,0].sum()
            wy=w[...,1].sum()
            
            for i in range(len(self.alignpointlist)):
                x=0
                y=0
                for j in range(len(self.alignpointlist[i])):
                    x+=self.alignpointlist[i][j][0]*w[j,0]
                    y+=self.alignpointlist[i][j][1]*w[j,1]
                            
                self.offsetlist[i][0]=(x/wx)
                self.offsetlist[i][1]=(y/wy)

                self.progress.setValue(i)
                if ((i%25)==0) and self.progressWasCanceled():
                    return False

            self.unlock()
            self.statusBar.showMessage(tr('DONE'))
        else:
            self.statusBar.showMessage(tr('No align points: using manual alignment, DONE'))
        
        

    def __average_dark__(self):
        result=None
        total = len(self.darkfilelist)
        self.statusBar.showMessage(tr('Creating master-dark, please wait...'))
        
        self.progress.setMaximum(total-1)
        self.lock()
        for i in range(total):
            self.progress.setValue(i)

            if self.progressWasCanceled():
                return None

            raw=self.openImage(self.darkfilelist[i][0],self.darkfilelist[i][1],True)
                        
            if ('RGB' in self.currentDepht) and (len(raw[0][0]) > 3):
                raw = raw[...,0:3]
                            
            if result is None:
                result = raw
            else:
                result += raw
            del raw
            
        self.unlock()
               
        self.statusBar.showMessage(tr('Computing final image...'))

        result=result/total
        self.statusBar.showMessage(tr('DONE'))
        
        return result
    
    def __average_flat__(self,dark_image=None):
        result=None

        if (dark_image != None):
            use_dark = True
        else:
            use_dark = False

        total = len(self.flatfilelist)
        
        self.statusBar.showMessage(tr('Creating master-flatfield, please wait...'))
        
        self.progress.setMaximum(total-1)
        self.lock()

        for i in range(total):
            self.progress.setValue(i)

            if self.progressWasCanceled():
                return None
                
            raw=self.openImage(self.flatfilelist[i][0],self.flatfilelist[i][1],True)
                        
            if ('RGB' in self.currentDepht) and (len(raw[0][0]) > 3):
                raw = raw[...,0:3]
                
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

        result=result/total
        
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
            normalizer = float(flat_image.sum()/float(flat_image.size))
            #added 10^-8 to  avoid master_flat[i,j] = 0 for some i,j
            master_flat=((flat_image/normalizer)*self.master_flat_mul_factor)+0.00000001
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
            
            rawi_unc=self.openImage(self.filelist[i][0],self.filelist[i][1],True)

            raw=rawi_unc[y_start:y_start+self.result_h,x_start:x_start+self.result_w]

            if use_dark:
                rad = master_dark[y_start:y_start+self.result_h,x_start:x_start+self.result_w]
                
            self.progress.setValue((4*i)+1)

            if self.progressWasCanceled():
                return False
                
            if use_flat:
                raf = master_flat[y_start:y_start+self.result_h,x_start:x_start+self.result_w]

            self.progress.setValue((4*i)+2)

            if ('RGB' in self.currentDepht) and (len(raw[0][0]) > 3):
                raw = raw[...,0:3]
                
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

        self._avg=result/count

        self.statusBar.clearMessage()
        self.updateResultImage()
        self.unlock()
        self.statusBar.showMessage(tr('DONE'))
        
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
        self._imwrite_fit_(avg_name,self._avg.astype(outbits),rgb_mode)
        
        if self.save_dlg.saveMastersCheckBox.checkState()==2:
            if (self._drk!=None):
                drk_name=os.path.join(destdir,name+"-maste-dark")
                self._imwrite_fit_(drk_name,self._drk.astype(outbits),rgb_mode)
            
            if (self._flt!=None):
                flt_name=os.path.join(destdir,name+"-maste-flat")
                self._imwrite_fit_(flt_name,self._flt.astype(outbits),rgb_mode)
    
    def _save_cv2(self,destdir, name, frmt, bits):
               
        if bits==8:
            rawavg=utils.normToUint8(self._avg)
            rawdrk=utils.normToUint8(self._drk)
            rawflt=utils.normToUint8(self._flt)
        elif bits==16:
            rawavg=utils.normToUint16(self._avg)
            rawdrk=utils.normToUint16(self._drk)
            rawflt=utils.normToUint16(self._flt)
        else:
            #this should neve be executed!
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
                drk_name=os.path.join(destdir,name+"-maste-dark."+frmt)
                self._imwrite_cv2_(drk_name,rawdrk,flags)
            
            if (self._flt!=None):
                flt_name=os.path.join(destdir,name+"-maste-flat."+frmt)
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
            
    def __fits_secure_imwrite(self, hdulist, url):
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
    
    def _imwrite_fit_(self, name, data, rgb_mode=True):

        if rgb_mode and (len(data.shape) == 3):
            hdu_r = utils.pyfits.PrimaryHDU(data[...,0])
            
            hdu_g = utils.pyfits.ImageHDU(data[...,1])
            hdu_g.update_ext_name('GREN')
            
            hdu_b = utils.pyfits.ImageHDU(data[...,2])
            hdu_b.update_ext_name('BLUE')
            
            hdl = utils.pyfits.HDUList([hdu_r,hdu_g,hdu_b])
            
            self.__fits_secure_imwrite(hdl,name+'-RGB.fits')
            
        elif (len(data.shape) == 3):
            hdu_r = utils.pyfits.PrimaryHDU(data[...,0])
            hdl_r = utils.pyfits.HDUList([hdu_r])
            self.__fits_secure_imwrite(hdl_r,name+'-R.fits')
            
            hdu_g = utils.pyfits.ImageHDU(data[...,1])
            hdl_g = utils.pyfits.HDUList([hdu_g])
            self.__fits_secure_imwrite(hdl_g,name+'-G.fits')
            
            hdu_b = utils.pyfits.ImageHDU(data[...,2])
            hdl_b = utils.pyfits.HDUList([hdu_b])
            self.__fits_secure_imwrite(hdl_b,name+'-B.fits')
            
        else:    
            hdu = utils.pyfits.PrimaryHDU(data)
            hdl = utils.pyfits.HDUList([hdu])
            self.__fits_secure_imwrite(hdl,name+'.fits')

