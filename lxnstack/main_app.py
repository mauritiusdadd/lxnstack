#lxnstack is a program to align and stack atronomical images
#Copyright (C) 2013-2014  Maurizio D'Addona <mauritiusdadd@gmail.com>

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
import argparse
from xml.dom import minidom
import paths
import logging

from PyQt4 import uic, Qt, QtCore, QtGui

import log
import videocapture
import utils
import imgfeatures
import mappedimage
import guicontrols
import colormaps as cmaps
import numpy as np
import scipy as sp
import cv2

def tr(s):
    return utils.tr(s)

def Int(val):
    i = math.floor(val)
    if ((val-i)<0.5):
        return int(i)
    else:
        return int(math.ceil(val))
    
def dist(x1,y1,x2,y2):
    return (((x2-x1)**2)+((y2-y1)**2))**0.5


class theApp(Qt.QObject):

    def __init__(self,lang='',args=[]):
        
        Qt.QObject.__init__(self)
        
        self._fully_loaded=False
        self.verbose=False
        
        self.parseArguments(args)

        log.log(repr(self),'Starting lxnstack...',level=logging.INFO)
        
        self._old_tab_idx=0
        self.__operating=False          #this will be used to avoid recursion loop
        self.__updating_mdi_ctrls=False #this will be used to avoid recursion loop
        self._photo_time_clock=0
        self._phase_align_data=None
        
        self.current_match_mode=cv2.TM_SQDIFF #TODO: Add selection box
        
        self._generateOpenStrings()

        if not os.path.isdir(paths.TEMP_PATH):
            os.makedirs(paths.TEMP_PATH)
        
        if not os.path.isdir(paths.HOME_PATH):
            os.makedirs(paths.HOME_PATH)
            
        if not os.path.isdir(paths.CAPTURED_PATH):
            os.makedirs(paths.CAPTURED_PATH)
            
        self.temp_path=paths.TEMP_PATH
                
        self.__current_lang=lang
        self.zoom = 1
        self.min_zoom = 0
        self.actual_zoom=1
        self.exposure=0
        self.zoom_enabled=False
        self.zoom_fit=False
        self.current_dir='~'
        
        self.colors=[(QtCore.Qt.red,tr('red')),
                     (QtCore.Qt.green,tr('green')),
                     (QtCore.Qt.blue,tr('blue')),
                     (QtCore.Qt.yellow,tr('yellow')),
                     (QtCore.Qt.cyan,tr('cyan')),
                     (QtCore.Qt.magenta,tr('magenta')),
                     (QtCore.Qt.darkRed,tr('dark red')),
                     (QtCore.Qt.gray,tr('gray')),
                     (QtCore.Qt.darkYellow,tr('dark yellow')),
                     (QtCore.Qt.darkGreen,tr('dark green')),
                     (QtCore.Qt.darkCyan,tr('dark cyan')),
                     (QtCore.Qt.darkBlue,tr('dark blue')),
                     (QtCore.Qt.darkMagenta,tr('dark magenta')),
                     (QtCore.Qt.black,tr('black'))]
        
        self.wasCanceled=False
        self.__video_capture_stopped=False
        self.__video_capture_started=False
        self.isPreviewing=False
        self.shooting=False
        
        self.current_align_method=0
        self.is_aligning=False
        
        self.showAlignPoints = True
        self.showStarPoints = True
        
        self.image_idx=-1
        self.ref_image_idx=-1
        self.dif_image_idx=-1
        self.point_idx=-1
        self.star_idx=-1

        self._bas=None
        self._drk=None
        self._stk=None
        self._flt=None
                
        self._preview_data=None
        self._preview_image=None
        
        self._old_stk=None
        self._oldhst=None
        
        self.autoalign_rectangle=(256,256)
        self.auto_align_use_whole_image=0
        
        self.manual_align=False

        self.ftype=np.float32
        
        self.mdi_windows={}
        
        self.framelist=[]
        self.biasframelist=[]
        self.darkframelist=[]
        self.flatframelist=[]
        self.starslist=[]
        self.lightcurve={}

        self.wnd = uic.loadUi(os.path.join(paths.UI_PATH,'main.ui'))
        self.dlg = uic.loadUi(os.path.join(paths.UI_PATH,'option_dialog.ui'))
        self.about_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'about_dialog.ui'))
        self.save_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'save_dialog.ui'))
        self.stack_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'stack_dialog.ui'))
        self.align_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'align_dialog.ui'))
        self.video_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'video_dialog.ui'))
        
        self.dlg.refreshPushButton.setIcon(utils.getQIcon("view-refresh"))
        
        self.statusBar = self.wnd.statusBar()
        self.statusLabelMousePos = Qt.QLabel()
                
        self.mdi = self.wnd.mdiArea
        
        self.videoCaptureScheduler = videocapture.CaptureScheduler()
        
        self.buildMenus()
        self.setUpStatusBar()
        self.setUpToolBars()
                        
        self.currentWidth=0
        self.currentHeight=0
        self.currentDepht=0
        
        self.current_colormap = 0

        self.result_w=0
        self.result_h=0
        self.result_d=3
        
        self.current_project_fname=None
        
        self.average_save_file='average'
        self.master_bias_save_file='master-bias'
        self.master_dark_save_file='master-dark'
        self.master_flat_save_file='master-flat'
        
        self.master_bias_file=None
        self.master_dark_file=None
        self.master_flat_file=None
        
        self.master_bias_mul_factor=1.0
        self.master_dark_mul_factor=1.0
        self.master_flat_mul_factor=1.0
                        
        self.tracking_align_point=False
        self.tracking_star_point=False
        
        self.panning=False
        self.panning_startig=(0,0)
        self.panning_ending=(0,0)
        self.checked_seach_dark_flat=0
        self.checked_autodetect_rectangle_size=2
        self.checked_autodetect_min_quality=2
        self.checked_colormap_jet=2
        self.checked_custom_temp_dir=2
        self.custom_chkstate=0
        self.ftype_idx=0
        self.checked_compressed_temp=0
        self.custom_temp_path=os.path.join(paths.HOME_PATH,'.temp')
        self.checked_show_phase_img=2
        self.phase_interpolation_order=0
        self.interpolation_order=0
        self.use_image_time=True        
        
        self.progress_dialog = Qt.QProgressDialog()        
        self.progress_dialog.canceled.connect(self.canceled)
        
        self.frame_open_args={'rgb_fits_mode':True,
                              'convert_cr2':False,
                              'progress_bar':self.progress_dialog}
        
        self.fit_levels=False
        
        self.current_cap_device=None
        self.current_cap_device_title=""
        self.video_writer = cv2.VideoWriter()
        self.video_url=''
        self.writing=False
        self.captured_frames=0
        self.max_captured_frames=0
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
                
        # exit callback
        self.wnd.__closeEvent__= self.wnd.closeEvent #base implementation
        self.wnd.closeEvent = self.mainWindowCloseEvent #new callback
        
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
        
        self.save_dlg.radioButtonFits.setEnabled(utils.FITS_SUPPORT)
        
        self.wnd.addPushButton.clicked.connect(self.doLoadFiles)
        self.wnd.remPushButton.clicked.connect(self.removeImage)
        self.wnd.clrPushButton.clicked.connect(self.clearLightList)
        self.wnd.biasAddPushButton.clicked.connect(self.doAddBiasFiles)
        self.wnd.biasClearPushButton.clicked.connect(self.doClearBiasList)
        self.wnd.darkAddPushButton.clicked.connect(self.doAddDarkFiles)
        self.wnd.darkClearPushButton.clicked.connect(self.doClearDarkList)
        self.wnd.flatAddPushButton.clicked.connect(self.doAddFlatFiles)
        self.wnd.flatClearPushButton.clicked.connect(self.doClearFlatList)
        self.wnd.listCheckAllBtn.clicked.connect(self.checkAllListItems)
        self.wnd.listUncheckAllBtn.clicked.connect(self.uncheckAllListItems)
        self.wnd.alignDeleteAllPushButton.clicked.connect(self.clearAlignPoinList)
        self.wnd.starsDeleteAllPushButton.clicked.connect(self.clearStarsList)
        self.wnd.lightListWidget.currentRowChanged.connect(self.listItemChanged)
        self.wnd.lightListWidget.currentItemChanged.connect(self.showFrameItemInCurrentTab)
        self.wnd.darkListWidget.currentItemChanged.connect(self.showDarkFrameItemInCurrentTab)
        self.wnd.flatListWidget.currentItemChanged.connect(self.showFlatFrameItemInCurrentTab)
        self.wnd.biasListWidget.currentItemChanged.connect(self.showBiasFrameItemInCurrentTab)
        self.wnd.lightListWidget.itemDoubleClicked.connect(self.showFrameItemInNewTab)
        self.wnd.darkListWidget.itemDoubleClicked.connect(self.showDarkFrameItemInNewTab)
        self.wnd.flatListWidget.itemDoubleClicked.connect(self.showFlatFrameItemInNewTab)
        self.wnd.biasListWidget.itemDoubleClicked.connect(self.showBiasFrameItemInNewTab)
        self.wnd.listWidgetManualAlign.currentRowChanged.connect(self.manualAlignListItemChanged)
        self.wnd.listWidgetManualAlign.itemChanged.connect(self.currentManualAlignListItemChanged)
        self.wnd.starsListWidget.itemChanged.connect(self.starsListItemChanged)
        self.wnd.alignPointsListWidget.currentRowChanged.connect(self.alignListItemChanged)
        self.wnd.starsListWidget.currentRowChanged.connect(self.currentStarsListItemChanged)
        self.wnd.toolBox.currentChanged.connect(self.updateToolBox)
        self.wnd.spinBoxXAlign.valueChanged.connect(self.shiftX)
        self.wnd.spinBoxYAlign.valueChanged.connect(self.shiftY)
        self.wnd.spinBoxXStar.valueChanged.connect(self.shiftStarX)
        self.wnd.spinBoxYStar.valueChanged.connect(self.shiftStarY)
        self.wnd.innerRadiusDoubleSpinBox.valueChanged.connect(self.setInnerRadius)
        self.wnd.middleRadiusDoubleSpinBox.valueChanged.connect(self.setMiddleRadius)
        self.wnd.outerRadiusDoubleSpinBox.valueChanged.connect(self.setOuterRadius)
        self.wnd.magDoubleSpinBox.valueChanged.connect(self.setMagnitude)
        self.wnd.doubleSpinBoxOffsetX.valueChanged.connect(self.shiftOffsetX)
        self.wnd.doubleSpinBoxOffsetY.valueChanged.connect(self.shiftOffsetY)
        self.wnd.spinBoxOffsetT.valueChanged.connect(self.rotateOffsetT)
        self.wnd.addPointPushButton.clicked.connect(self.addAlignPoint)
        self.wnd.removePointPushButton.clicked.connect(self.removeAlignPoint)
        self.wnd.addStarPushButton.clicked.connect(self.addStar)
        self.wnd.removeStarPushButton.clicked.connect(self.removeStar)
        self.wnd.autoSetPushButton.clicked.connect(self.autoSetAlignPoint)
        self.wnd.autoDetectPushButton.clicked.connect(self.autoDetectAlignPoints)
        self.wnd.masterBiasCheckBox.stateChanged.connect(self.useMasterBias)
        self.wnd.masterDarkCheckBox.stateChanged.connect(self.useMasterDark)
        self.wnd.masterFlatCheckBox.stateChanged.connect(self.useMasterFlat)
        self.wnd.masterBiasPushButton.clicked.connect(self.loadMasterBias)
        self.wnd.masterDarkPushButton.clicked.connect(self.loadMasterDark)
        self.wnd.masterFlatPushButton.clicked.connect(self.loadMasterFlat)
        self.wnd.biasMulDoubleSpinBox.valueChanged.connect(self.setBiasMul)
        self.wnd.darkMulDoubleSpinBox.valueChanged.connect(self.setDarkMul)
        self.wnd.flatMulDoubleSpinBox.valueChanged.connect(self.setFlatMul)
        self.wnd.alignMethodComboBox.currentIndexChanged.connect(self.changeAlignMethod)
        
        self.dlg.devComboBox.currentIndexChanged.connect(self.setCurrentCaptureDevice)
        #self.dlg.videoSaveDirPushButton.clicked.connect(self._set_save_video_dir)
        self.dlg.refreshPushButton.clicked.connect(self.updateCaptureDevicesList)
        self.dlg.jetCheckBox.setCheckState(2)
        self.dlg.fTypeComboBox.currentIndexChanged.connect(self.setFloatPrecision)
        self.dlg.jetCheckBox.setCheckState(2)
        self.dlg.tempPathPushButton.clicked.connect(self._set_temp_path)
        self.dlg.phaseIntOrderSlider.valueChanged.connect(self.setPhaseInterpolationOrder)
        self.dlg.intOrderSlider.valueChanged.connect(self.setInterpolationOrder)
        self.dlg.showPhaseImgCheckBox.stateChanged.connect(self.setShowPhaseIamge)
        
        self.save_dlg.radioButtonJpeg.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButtonPng.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButtonTiff.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButtonFits.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButtonNumpy.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButtonInt.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButtonFloat.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButton8.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButton16.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButton32.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButton64.toggled.connect(self.updateSaveOptions)
        self.save_dlg.checkBoxUnsigned.stateChanged.connect(self.updateSaveOptions)
        self.save_dlg.pushButtonDestDir.clicked.connect(self.getDestDir)
        
        self._resetPreferencesDlg()
        
        if not os.path.isdir(self.save_image_dir):
            os.makedirs(self.save_image_dir)
        
        if not os.path.isdir(self.custom_temp_path):
            os.makedirs(self.custom_temp_path)
            
        self.updateCaptureDevicesList()
        
        self.newProject()
                
        log.log(repr(self),'Program started',level=logging.INFO)
    
    def setFullyLoaded(self):
        self._fully_loaded=True
    
    def fullyLoaded(self):
        return self._fully_loaded
    
    def __reload_modules__(self): #debug purpose only
        reload(videocapture)
        reload(utils)
        reload(imgfeatures)
        reload(mappedimage)
        reload(guicontrols)
    
    #TODO: switch to argparse module
    def parseArguments(self,args):
                
        lproject=[None,'']
        sproject=[None,'']
        stacking=[None,'']
        align=[None,[False,False,False]]
        images=[None,[]]
        light=False
        
        parser = argparse.ArgumentParser(description=tr('lxnstack is aprogram usefull to align and stack the astronomical images.'))
        
        parser.add_argument("-a","--align", nargs='?', const='align-derotate',
                            choices=['align-only', 'derotate-only', 'align-derotate','reset'],
                            metavar='METHOD',
                            help=tr('''execute the phase correlation alignment
                                    with the given %(metavar)s. The values allowed
                                    for %(metavar)s are: align-only, derotate-only,
                                    align-derotate, reset. If no %(metavar)s is
                                    specified then  %(const)s is used by
                                    default.'''))
        
        parser.add_argument("-i","--add-images", nargs='+',
                            metavar='FILES',
                            help=tr('''load the images from the files %(metavar)s.'''))
        
        parser.add_argument("-m","--user-manual", action='store_true',
                            help=tr('''show the use manual in a web browser
                                    and exit.'''))
        
        parser.add_argument("-l","--load-project", nargs='?',
                            metavar='FILE',
                            help=tr('''load the project from the file %(metavar)s.'''))
        
        parser.add_argument("-s","--save-project", nargs='?',
                            metavar='FILE',default="False",
                            help=tr('''save the project to the file %(metavar)s
                                    If %(metavar)s is not given and a project is alrady
                                    loaded then the current project will be
                                    overwritten. If %(metavar)s is not given and no
                                    project is loaded, then an error is raised.'''))
        
        parser.add_argument("-S","--stack", nargs='?', const='average',
                            choices=['average','median','sigma-clipping',
                                     'minimum','maximum','stddev','variance',
                                     'product'],
                            metavar='MODE',
                            help=tr('''stack the images using the mode %(metavar)s.
                                    The values allowed for %(metavar)s are:
                                    average, median, sigma-clipping, minimum,
                                    maximum, stddev, variance, product.
                                    If no %(metavar)s is given then the %(const)s is
                                    be computed.'''))
        
        parser.add_argument("--lightcurve", action='store_true',
                            help=tr('''generate the lightcurves (a project with
                                    lightcurve informations must be loaded).'''))
        
        parser.add_argument("-v","--version", action='store_true',
                            help=tr('''print the version of the program and exit.'''))
        
        parser.add_argument("--verbose", action='store_true',
                            help=tr('''increase output verbosity'''))
        
        self.args = vars(parser.parse_args(args))
        
        self.verbose=self.args['verbose']
        
        #default values for project name
        if self.args['save_project'] is None:
            if self.args['load_project'] is not None:
                self.args['save_project']=self.args['load_project']
            else:
                self.criticalError('No project name specified!\nPlease use --help for more informations\n',False)
        
    def executeCommads(self):
        
        if self.args['load_project'] is not None:
            self.loadProject(self.args['load_project'])
            
        if self.args['add_images'] is not None:
            self.loadFiles(self.args['add_images'])
            
        if self.args['align'] is not None:
            self.wnd.toolBox.setCurrentIndex(1)
            
            if self.args['align']=='align-only':
                self.align(False,True,False)
            elif self.args['align']=='derotate-only':
                self.align(False,False,True)
            elif self.args['align']=='align-derotate':
                self.align(False,True,True)
            elif self.args['align']=='reset':
                self.align(True,False,False)
            
        if self.args['save_project'] is not None:
            self.current_project_fname=self.args['save_project']
            self._save_project()
            
        if self.args['stack'] is not None:
            val=self.args['stack']
            self.wnd.toolBox.setCurrentIndex(7)
                        
            if val=='average':
                stacking_mode=0
            elif val=='median':
                stacking_mode=1
            elif val=='sigma-clipping':
                stacking_mode=2
            elif val=='stddev':
                stacking_mode=3
            elif val=='variance':
                stacking_mode=4
            elif val=='maximum':
                stacking_mode=5
            elif val=='minimum':
                stacking_mode=6
            elif val=='maximum':
                stacking_mode=7
            
            self.stack(stacking_mode)
            
        if self.args['lightcurve']:
            self.wnd.toolBox.setCurrentIndex(6)
            self.generateLightCurves(0)
        
        self.setFullyLoaded()
        
    
    def criticalError(self,msg,msgbox=True):
        if msgbox:
            utils.showErrorMsgBox(msg)
        else:
            log.log(repr(self),msg,level=logging.ERROR)
        sys.exit(1)
        
    def clearResult(self):
        
        del self._stk
        del self._drk
        del self._flt
        del self._preview_data
        
        self._stk=None
        self._bas=None
        self._drk=None
        self._flt=None
        self._preview_data=None
        self._preview_image=None
        
    
    def activateResultControls(self):
        self.action_save_result.setEnabled(True)
        
    def deactivateResultControls(self):
        self.action_save_result.setEnabled(False)
    
    def updateChartColors(self):
        self.wnd.colorADUComboBox.clear ()
        for i in range(len(self.colors)):
            self.wnd.colorADUComboBox.addItem(self.colors[i][1])
            self.wnd.colorMagComboBox.addItem(self.colors[i][1])
            
    
    def updateSaveOptions(self, *args):       
        
        if self.save_dlg.radioButtonJpeg.isChecked():
            self.save_dlg.groupBoxImageQuality.setEnabled(True)
            self.save_dlg.groupBoxImageCompression.setEnabled(False)
            self.save_dlg.radioButtonFloat.setEnabled(False)
            self.save_dlg.checkBoxUnsigned.setEnabled(False)
            self.save_dlg.checkBoxUnsigned.setCheckState(2)
            self.save_dlg.radioButtonInt.setChecked(True)
            self.save_dlg.radioButton32.setEnabled(False)
            self.save_dlg.radioButton64.setEnabled(False)
            self.save_dlg.comprFitsCheckBox.setEnabled(False)
            self.save_dlg.rgbFitsCheckBox.setEnabled(False)
            
            if (self.save_dlg.radioButton32.isChecked() or
                self.save_dlg.radioButton64.isChecked()):
                self.save_dlg.radioButton8.setChecked(True)
            
        elif self.save_dlg.radioButtonPng.isChecked():
            self.save_dlg.groupBoxImageQuality.setEnabled(False)
            self.save_dlg.groupBoxImageCompression.setEnabled(True)
            self.save_dlg.radioButtonFloat.setEnabled(False)
            self.save_dlg.checkBoxUnsigned.setEnabled(False)
            self.save_dlg.checkBoxUnsigned.setCheckState(2)
            self.save_dlg.radioButtonInt.setChecked(True)
            self.save_dlg.radioButton32.setEnabled(False)
            self.save_dlg.radioButton64.setEnabled(False)
            self.save_dlg.comprFitsCheckBox.setEnabled(False)
            self.save_dlg.rgbFitsCheckBox.setEnabled(False)
            
            if (self.save_dlg.radioButton32.isChecked() or
                self.save_dlg.radioButton64.isChecked()):
                self.save_dlg.radioButton8.setChecked(True)
            
        elif self.save_dlg.radioButtonTiff.isChecked():
            self.save_dlg.groupBoxImageQuality.setEnabled(False)
            self.save_dlg.groupBoxImageCompression.setEnabled(False)
            self.save_dlg.radioButtonFloat.setEnabled(False)
            self.save_dlg.checkBoxUnsigned.setEnabled(False)
            self.save_dlg.checkBoxUnsigned.setCheckState(2)
            self.save_dlg.radioButtonInt.setChecked(True)
            self.save_dlg.radioButton8.setEnabled(True)
            self.save_dlg.radioButton16.setEnabled(True)
            self.save_dlg.radioButton32.setEnabled(False)
            self.save_dlg.radioButton64.setEnabled(False)
            self.save_dlg.comprFitsCheckBox.setEnabled(False)
            self.save_dlg.rgbFitsCheckBox.setEnabled(False)
            if (self.save_dlg.radioButton32.isChecked() or
                self.save_dlg.radioButton64.isChecked()):
                self.save_dlg.radioButton8.setChecked(True)
            
        elif self.save_dlg.radioButtonFits.isChecked():
            self.save_dlg.groupBoxImageQuality.setEnabled(False)
            self.save_dlg.groupBoxImageCompression.setEnabled(False)
            self.save_dlg.radioButtonFloat.setEnabled(False)
            self.save_dlg.radioButtonInt.setEnabled(False)
            self.save_dlg.checkBoxUnsigned.setEnabled(False)        
            self.save_dlg.radioButton8.setEnabled(True)
            self.save_dlg.radioButton16.setEnabled(True)
            self.save_dlg.radioButton32.setEnabled(True)
            self.save_dlg.radioButton64.setEnabled(True)
            self.save_dlg.comprFitsCheckBox.setEnabled(True)
            self.save_dlg.rgbFitsCheckBox.setEnabled(True)
            
            if self.save_dlg.radioButton8.isChecked():
                self.save_dlg.radioButtonInt.setChecked(True)
                self.save_dlg.checkBoxUnsigned.setCheckState(2)
            elif self.save_dlg.radioButton16.isChecked():
                self.save_dlg.radioButtonInt.setChecked(True)
                self.save_dlg.checkBoxUnsigned.setCheckState(0)
            elif self.save_dlg.radioButton32.isChecked():
                self.save_dlg.radioButtonFloat.setChecked(True)
                self.save_dlg.checkBoxUnsigned.setCheckState(0)
            elif self.save_dlg.radioButton64.isChecked():
                self.save_dlg.radioButtonFloat.setChecked(True)
                self.save_dlg.checkBoxUnsigned.setCheckState(0)
            else:
                pass #should never happen
            
        elif self.save_dlg.radioButtonNumpy.isChecked():
            self.save_dlg.groupBoxImageQuality.setEnabled(False)
            self.save_dlg.groupBoxImageCompression.setEnabled(False)
            self.save_dlg.radioButtonFloat.setEnabled(True)
            self.save_dlg.radioButtonInt.setEnabled(True)
            self.save_dlg.checkBoxUnsigned.setEnabled(True)
            self.save_dlg.radioButton32.setEnabled(True)
            self.save_dlg.radioButton64.setEnabled(True)
            self.save_dlg.comprFitsCheckBox.setEnabled(False)
            self.save_dlg.rgbFitsCheckBox.setEnabled(False)
            
            if self.save_dlg.radioButtonFloat.isChecked():
                self.save_dlg.checkBoxUnsigned.setCheckState(0)
                self.save_dlg.checkBoxUnsigned.setEnabled(False)
            else:
                self.save_dlg.checkBoxUnsigned.setEnabled(True)
            
        else:
            pass #should never happen
        
            
        self.save_dlg.radioButtonFloat.toggled.connect(self.updateSaveOptions)
    
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
        
    def setPhaseInterpolationOrder(self,val):
        self.phase_interpolation_order=val
        
    def setInterpolationOrder(self,val):
        self.interpolation_order=val
        
    def setShowPhaseIamge(self, val):
        self.checked_show_phase_img=val

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
        self.current_align_method=idx
        
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
            self.ftype=np.float32
        elif idx==1:
            self.ftype=np.float64
        
        log.log(repr(self),"setting float precision to " + str(self.ftype),level=logging.INFO)
        
    def showUserMan(self):
        webbrowser.open(os.path.join(paths.DOCS_PATH,'usermanual.html'))

    def setBiasMul(self,val):
        self.master_bias_mul_factor=val

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
        self.dlg.rgbFitsCheckBox.setCheckState(int(self.frame_open_args['rgb_fits_mode'])*2)
        self.dlg.decodeCR2CheckBox.setCheckState(int(self.frame_open_args['convert_cr2'])*2)

        self.dlg.devComboBox.setCurrentIndex(self.current_cap_combo_idx)

        self.dlg.rWSpinBox.setValue(self.autoalign_rectangle[0])
        self.dlg.rHSpinBox.setValue(self.autoalign_rectangle[1])

        self.dlg.maxPointsSpinBox.setValue(self.max_points)
        self.dlg.minQualityDoubleSpinBox.setValue(self.min_quality)
        
        self.dlg.autoSizeCheckBox.setCheckState(self.checked_autodetect_rectangle_size)
        
        self.dlg.langFileLineEdit.setText(self.__current_lang)
        #self.dlg.videoSaveLineEdit.setText(self.save_image_dir)
        
        self.dlg.wholeImageCheckBox.setChecked(self.auto_align_use_whole_image)
        self.dlg.autoSizeCheckBox.setChecked(self.checked_autodetect_rectangle_size)
        self.dlg.minQualitycheckBox.setCheckState(self.checked_autodetect_min_quality)

        self.dlg.autoFolderscheckBox.setCheckState(self.checked_seach_dark_flat)
        
        self.dlg.tempPathCheckBox.setCheckState(self.checked_custom_temp_dir)
        self.dlg.tempPathLineEdit.setText(self.custom_temp_path)
        self.dlg.compressedTempCheckBox.setCheckState(self.checked_compressed_temp)
        
        self.dlg.showPhaseImgCheckBox.setCheckState(self.checked_show_phase_img)
        self.dlg.phaseIntOrderSlider.setValue(self.phase_interpolation_order)
        self.dlg.intOrderSlider.setValue(self.interpolation_order)
        
        if self.checked_custom_temp_dir==2:
            self.temp_path=os.path.expandvars(self.custom_temp_path)
        else:
            self.temp_path=paths.TEMP_PATH
            
        
    def _set_save_video_dir(self):
        self.save_image_dir = str(Qt.QFileDialog.getExistingDirectory(self.dlg,
                                                                      tr("Choose the detination folder"),
                                                                      self.save_image_dir,
                                                                      utils.DIALOG_OPTIONS))
        #self.dlg.videoSaveLineEdit.setText(self.save_image_dir)
        
    def _set_temp_path(self):
        self.custom_temp_path = str(Qt.QFileDialog.getExistingDirectory(self.dlg,
                                                                        tr("Choose the temporary folder"),
                                                                        self.temp_path,
                                                                        utils.DIALOG_OPTIONS))
        self.dlg.tempPathLineEdit.setText(self.custom_temp_path)
    
    def showCaptureProperties(self):
        
        self.dlg.tabWidget.setCurrentIndex(2)
        
        if self.isPreviewing:
            self.dlg.tabWidget.setCurrentIndex(2)
            self.dlg.show()
        else:
            current_tab_idx=self.dlg.tabWidget.currentIndex()
            self.dlg.exec_()
            self.dlg.tabWidget.setCurrentIndex(current_tab_idx)
    
    def setCurrentCaptureDevice(self,index):
        
        if self.current_cap_device is not None:
            if not self.current_cap_device.close():
                return False    
            else:
                self.current_cap_device.lockStateChanged.disconnect(self.dlg.refreshPushButton.setDisabled)
                self.dlg.controlsLayout.removeWidget(self.current_cap_device.getControlUI())
                self.current_cap_device.getControlUI().setParent(None)
                self.current_cap_device.getControlUI().hide()
        
        self.current_cap_combo_idx=index
        self.current_cap_device=self.devices[index]['device']
        self.current_cap_device_title=self.dlg.devComboBox.currentText()
        self.current_cap_device.lockStateChanged.connect(self.dlg.refreshPushButton.setDisabled)
        
        for action in self.capture_devices_menu._video_action_group.actions():
            if index == action.index:
                action.setChecked(True)
                
        #adding the device's controls widget
        self.dlg.controlsLayout.addWidget(self.current_cap_device.getControlUI())
        self.current_cap_device.getControlUI().show()
        
        self.videoCaptureScheduler.setCaptureDevice(self.current_cap_device)
        
        if self.isPreviewing:
            self.current_cap_device.open()
        
    def _setCurrentCaptureDeviceFromActions(self,checked):
        for action in self.capture_devices_menu._video_action_group.actions():
            if action.isChecked():
                self.dlg.devComboBox.setCurrentIndex(action.index)            
        
    def updateCaptureDevicesList(self):
        self.devices=tuple(videocapture.listVideoDevices())
        
        self.dlg.devComboBox.clear()
        self.capture_devices_menu._video_action_group=QtGui.QActionGroup(self.capture_devices_menu)
        self.capture_devices_menu.clear()
        for device in self.devices:
            index=self.devices.index(device)
            name = "[{0: ^6s}] {1}".format(device['interface'],device['name'])
            self.dlg.devComboBox.insertItem(index,name)
            action = self.capture_devices_menu.addAction(name)
            action.index=index
            action.setCheckable(True)
            action.toggled.connect(self._setCurrentCaptureDeviceFromActions)
            self.capture_devices_menu._video_action_group.addAction(action)

        
    def setPreferences(self):

        qtr = Qt.QTranslator()
        self.dlg.langComboBox.clear()
        for qmf in os.listdir(paths.LANG_PATH):
            fl = os.path.join(paths.LANG_PATH,qmf)
            if qtr.load(fl):
                self.dlg.langComboBox.addItem(qmf,fl)
        self._resetPreferencesDlg()
        
        #self.updateCaptureDevicesList()        
            
        if self.current_cap_combo_idx < 0:
            self.current_cap_combo_idx=0

        self.dlg.devComboBox.setCurrentIndex(self.current_cap_combo_idx)

        if self.isPreviewing:
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
            #self.save_image_dir = str(self.dlg.videoSaveLineEdit.text())
            self.current_cap_combo_idx=int(self.dlg.devComboBox.currentIndex())
            self.auto_align_use_whole_image=int(self.dlg.wholeImageCheckBox.checkState())
            self.checked_autodetect_rectangle_size=int(self.dlg.autoSizeCheckBox.checkState())
            self.checked_colormap_jet=int(self.dlg.jetCheckBox.checkState())
            self.frame_open_args['rgb_fits_mode']=(int(self.dlg.rgbFitsCheckBox.checkState())==2)
            self.frame_open_args['convert_cr2']=(int(self.dlg.decodeCR2CheckBox.checkState())==2)
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
                utils.showErrorMsgBox(tr("Frame size or number of channels does not match.\n"),
                                      tr('current size=')+
                                      str(self.currentWidth)+'x'+str(self.currentHeight)+
                                      tr(' image size=')+
                                      str(imw)+'x'+str(imh)+'\n'+
                                      tr('current channels=')+str(self.currentDepht)+
                                      tr(' image channels=')+str(dep),
                                      parent=self.wnd)
                return True
            else:
                return False
        else:
            self.currentWidth=imw
            self.currentHeight=imh
            self.currentDepht=dep
            return False
            
    def unlockSidebar(self):
        if len(self.framelist)>0:
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
                self.wnd.toolBox.setItemEnabled(i,True)
            
        if len(self.framelist) == 0:
            self.action_enable_rawmode.setEnabled(False)
        elif self.framelist[0].isRGB():
            self.action_enable_rawmode.setEnabled(False)
        else:
            self.action_enable_rawmode.setEnabled(True)
    
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
        self.deactivateResultControls()
        self.action_enable_rawmode.setChecked(False)
        self.action_enable_rawmode.setEnabled(False)
        
        self.wnd.toolBox.setItemEnabled(0,True)
        for i in xrange(self.wnd.toolBox.count()-1):
            self.wnd.toolBox.setItemEnabled(i+1,False)        
        
    def lockRecording(self):
        self.lockSidebar()
        self.wnd.addPushButton.setEnabled(False)
        self.action_add_files.setEnabled(False)
        self.action_load_project.setEnabled(False)
        self.action_new_project.setEnabled(False)
        self.action_save_project.setEnabled(False)
        self.action_save_project_as.setEnabled(False)
        self.action_save_video.setEnabled(False)
        self.action_edit_pan.setEnabled(False)
        self.action_edit_select.setEnabled(False)
        self.action_take_shot.setEnabled(False)
        self.action_stop_capture.setEnabled(True)
        self.action_start_capture.setEnabled(False)
        
        self.directVideoCaptureTypeComboBox.setEnabled(False)
        self.dlg.refreshPushButton.setEnabled(False)
        
        self.__video_capture_stopped=False
        self.__video_capture_started=True
    
    def unlockRecording(self):
        self.unlockSidebar()
        self.wnd.addPushButton.setEnabled(True)
        self.action_add_files.setEnabled(True)
        self.action_load_project.setEnabled(True)
        self.action_new_project.setEnabled(True)
        self.action_save_project.setEnabled(True)
        self.action_save_project_as.setEnabled(True)
        self.action_save_video.setEnabled(True)
        self.action_edit_pan.setEnabled(True)
        self.action_edit_select.setEnabled(True)
        self.action_take_shot.setEnabled(True)
        self.action_stop_capture.setEnabled(False)
        self.action_start_capture.setEnabled(True)
        
        self.directVideoCaptureTypeComboBox.setEnabled(True)
        self.dlg.refreshPushButton.setEnabled(True)
        
        self.__video_capture_stopped=True
        self.__video_capture_started=False
    
    
    def oneShot(self):
        self.shooting=True
    
    def stopDirectVideoCapture(self):
        self.videoCaptureScheduler.stop()   
        self.videoCaptureScheduler._controlgui.jobPropGroupBox.setEnabled(True)
        self.videoCaptureScheduler._controlgui.jobListWidget.setEnabled(True)
        self.videoCaptureScheduler._controlgui.buttonsWidget.setEnabled(True)
        self.videoCaptureScheduler._controlgui.confirmPushButton.setEnabled(True)
        
        self.videoCaptureScheduler.deleteAllJobs()
        self.unlockRecording()
        try:
            self.videoCaptureScheduler.addJobs(self.videoCaptureScheduler.oldjoblist)
            del self.videoCaptureScheduler.oldjoblist
        except:
            pass

    def startDirectVideoCapture(self):
        
        self.videoCaptureScheduler.oldjoblist = self.videoCaptureScheduler.jobs
        
        self.videoCaptureScheduler.deleteAllJobs()
        
        jid="direct-video-capturing-"+time.strftime("%Y%m%d-%H%M%S")
        
        direct_video_capture_job = self.videoCaptureScheduler.getJob(self.videoCaptureScheduler.addJob(jobid=jid))
        self.lockRecording()
        
        direct_video_capture_job.setType(self.directVideoCaptureTypeComboBox.currentIndex())
        direct_video_capture_job._end_type=2
        direct_video_capture_job.setNumberOfFrames(-1)
        
        self.videoCaptureScheduler.setCurrentJob(None)
        
        self.videoCaptureScheduler._controlgui.jobPropGroupBox.setEnabled(False)
        self.videoCaptureScheduler._controlgui.jobListWidget.setEnabled(False)
        self.videoCaptureScheduler._controlgui.buttonsWidget.setEnabled(False)
        self.videoCaptureScheduler._controlgui.confirmPushButton.setEnabled(False)
        self.videoCaptureScheduler.start()
        
    def enableVideoPreview(self, enabled=False, origin=None):
        
        if self.current_cap_device is not None:
            
            if enabled:
                
                if not self.current_cap_device.open():
                    return False
                
                self.action_start_capture.setEnabled(True)
                
                self.isPreviewing=True
                
                self.dlg.refreshPushButton.setEnabled(False)
                old_tooltip=str(self.dlg.refreshPushButton.toolTip())
                self.dlg.refreshPushButton.setToolTip(tr("Cannot refresh devices list")+": "+tr("current device is in use"))
                log.log(repr(self),"Starting live preview from device "+str(self.current_cap_device),level=logging.INFO)
                
                # preview main loop
                self.lockSidebar()
                
                while (self.isPreviewing):
                    QtGui.QApplication.instance().processEvents()
                    if self.current_cap_device.isLocked():
                        ndimage = self.current_cap_device.getLastFrame()
                    else:
                        ndimage = self.current_cap_device.getFrame()
                    self.showImage(ndimage,title=self.current_cap_device_title,override_cursor=False)
                
                self.current_cap_device.close()
                self.dlg.refreshPushButton.setEnabled(True)
                self.dlg.refreshPushButton.setToolTip(old_tooltip)
                self.stopDirectVideoCapture()
                self.action_start_capture.setEnabled(False)
                
            else:
                self.isPreviewing=False
                log.log(repr(self),"Stopping live preview",level=logging.INFO)
    
    def useMasterBias(self,state):        
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
        open_str=tr("All supported images")+self.images_extensions+";;"+tr("All files *.* (*.*)")
        master_bias_file = str(Qt.QFileDialog.getOpenFileName(self.wnd,
                                                              tr("Select master-dark file"),
                                                              self.current_dir,
                                                              open_str,
                                                              None,
                                                              utils.DIALOG_OPTIONS
                                                              )
                              )
        if os.path.isfile(master_bias_file):
           try:
               i = utils.Frame(master_bias_file, **self.frame_open_args)
               if not i.is_good:
                   utils.showErrorMsgBox(tr("Cannot open image")+" \""+str(i.url)+"\"",parent=self.wnd)
                   return False
               imw = i.width
               imh = i.height
               dep = i.mode
               if ((self.currentWidth == imw) and
                   (self.currentHeight == imh) and
                   (self.currentDepht == dep)):
                   self.master_bias_file=i.url
                   self.wnd.masterBiasLineEdit.setText(i.url)
               else:
                   utils.showErrorMsgBox(tr("Cannot use this file:")+tr(" size or number of channels does not match!"),
                                         tr('current size=')+
                                         str(self.currentWidth)+'x'+str(self.currentHeight)+'\n'+
                                         tr('image size=')+
                                         str(imw)+'x'+str(imh)+'\n'+
                                         tr('current channels=')+str(self.currentDepht)+'\n'+
                                         tr('image channels=')+str(dep),
                                         parent=self.wnd)
                                                     
               del i
           except Exception as exc:
               log.log(repr(self),str(exc),level=logging.ERROR)
               utils.showErrorMsgBox("",exc)

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
                                                              utils.DIALOG_OPTIONS
                                                              )
                              )
        if os.path.isfile(master_dark_file):
           try:
               i = utils.Frame(master_dark_file, **self.frame_open_args)
               if not i.is_good:
                   utils.showErrorMsgBox(tr("Cannot open image")+" \""+str(i.url)+"\"",parent=self.wnd)
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
                   utils.showErrorMsgBox(tr("Cannot use this file:")+tr(" size or number of channels does not match!"),
                                         tr('current size=')+
                                         str(self.currentWidth)+'x'+str(self.currentHeight)+'\n'+
                                         tr('image size=')+
                                         str(imw)+'x'+str(imh)+'\n'+
                                         tr('current channels=')+str(self.currentDepht)+'\n'+
                                         tr('image channels=')+str(dep),
                                         parent=self.wnd)
               del i
           except Exception as exc:
               log.log(repr(self),str(exc),level=logging.ERROR)
               utils.showErrorMsgBox("",exc)
            
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
                                                              utils.DIALOG_OPTIONS
                                                              )
                              )
        if os.path.isfile(master_flat_file):
           try:
               i = utils.Frame(master_flat_file, **self.frame_open_args)
               if not i.is_good:
                   utils.showErrorMsgBox(tr("Cannot open image")+" \""+str(i.url)+"\"",parent=self.wnd)
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
                   utils.showErrorMsgBox(tr("Cannot use this file:")+tr(" size or number of channels does not match!"),
                                         tr('current size=')+
                                         str(self.currentWidth)+'x'+str(self.currentHeight)+'\n'+
                                         tr('image size=')+
                                         str(imw)+'x'+str(imh)+'\n'+
                                         tr('current channels=')+str(self.currentDepht)+'\n'+
                                         tr('image channels=')+str(dep),
                                         parent=self.wnd)
               del i
           except Exception as exc:
               log.log(repr(self),str(exc),level=logging.ERROR)
               utils.showErrorMsgBox("",exc)
               
        
    #closeEvent callback
    def mainWindowCloseEvent(self, event):
        if self._fully_loaded:
            val = utils.showYesNoMsgBox(tr("Do you really want to quit?"),
                                        tr("All unsaved changes will be lost!"),
                                        parent=self.wnd)
            
            if val == Qt.QMessageBox.Yes:
                self.stopDirectVideoCapture()
                self.canceled()
                self.saveSettings()
                if os.path.exists(paths.TEMP_PATH):
                    shutil.rmtree(paths.TEMP_PATH)
                return self.wnd.__closeEvent__(event)
            elif val == Qt.QMessageBox.No:
                event.ignore()
            else:
                return self.wnd.__closeEvent__(event)
        else:
            event.ignore()
    
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
        settings.setValue("current_colormap", int(self.current_colormap))
        settings.setValue("toolbar_locked", bool(self.action_lock_toolbars.isChecked()))
        settings.setValue("auto_rgb_fits", int(self.dlg.rgbFitsCheckBox.checkState()))
        settings.setValue("auto_convert_cr2", int(self.dlg.decodeCR2CheckBox.checkState()))
        settings.setValue("auto_search_dark_flat",int(self.dlg.autoFolderscheckBox.checkState()))
        settings.setValue("sharp1",float(self.wnd.sharp1DoubleSpinBox.value()))
        settings.setValue("sharp2",float(self.wnd.sharp2DoubleSpinBox.value()))
        settings.setValue("phase_image",int(self.dlg.showPhaseImgCheckBox.checkState()))
        settings.setValue("phase_order",int(self.dlg.phaseIntOrderSlider.value()))
        settings.setValue("interpolation_order",int(self.dlg.intOrderSlider.value()))
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
        current_colormap=settings.value("current_colormap",None,int)
        self.action_lock_toolbars.setChecked(settings.value("toolbar_locked",None,bool))
        self.dlg.jetCheckBox.setCheckState(self.checked_colormap_jet)
        self.dlg.decodeCR2CheckBox.setCheckState(settings.value("auto_convert_cr2",None,int))
        self.dlg.rgbFitsCheckBox.setCheckState(settings.value("auto_rgb_fits",None,int))
        self.checked_seach_dark_flat=settings.value("auto_search_dark_flat",None,int)
        self.dlg.autoFolderscheckBox.setCheckState(self.checked_seach_dark_flat)
        self.max_points=int(settings.value("max_align_points",None,int))
        self.min_quality=float(settings.value("min_point_quality",None,float))
        sharp1=float(settings.value("sharp1",None,float))
        self.wnd.sharp1DoubleSpinBox.setValue(sharp1)
        sharp2=float(settings.value("sharp1",None,float))
        self.wnd.sharp2DoubleSpinBox.setValue(sharp2)
        self.checked_show_phase_img=int(settings.value("phase_image",None,int))
        self.phase_interpolation_order=int(settings.value("phase_order",None,int))
        self.interpolation_order=int(settings.value("interpolation_order",None,int))
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
        
    def saveADUChart(self,clicked):
        self.saveChart( self.wnd.aduListWidget, 'adu_chart',name='ADU', y_inverted=False)
        
    def saveMagChart(self,clicked):
        self.saveChart( self.wnd.magListWidget, 'mag_chart',name='Mag', y_inverted=True)
    
    def saveChart(self, widget, title, name, y_inverted=False):
        chart = Qt.QImage(1600,1200,Qt.QImage.Format_ARGB32)
        fname=str(Qt.QFileDialog.getSaveFileName(self.wnd, tr("Save the chart"),
                                         os.path.join(self.current_dir,title+'.jpg'),
                                         "JPEG (*.jpg *.jpeg);;PNG (*.png);;PPM (*.ppm);;TIFF (*.tiff *.tif);;All files (*.*)",None,
                                         utils.DIALOG_OPTIONS))
        self.simplifiedLightCurvePaintEvent( widget,chart, name, y_inverted)
        chart.save(fname,quality=100)
        
    def aduLabelPaintEvent(self, obj):
        return self.simplifiedLightCurvePaintEvent(self.wnd.aduListWidget,self.wnd.aduLabel,'ADU',False)
    
    def magLabelPaintEvent(self, obj):
        return self.simplifiedLightCurvePaintEvent(self.wnd.magListWidget,self.wnd.magLabel,'Mag',True)
    
    def simplifiedLightCurvePaintEvent(self, lwig, lbl, name, inv):
        if self.use_image_time:
            return self.lightCurvePaintEvent( lwig, lbl, ('time',name), utils.getTimeStr, inverted=inv)
        else:
            return self.lightCurvePaintEvent( lwig, lbl, ('index',name), str, inverted=inv)
            
    def lightCurvePaintEvent(self, listWidget, surface, aname, xStrFunc=str, yStrFunc=utils.getSciStr, inverted=False):

        painter = Qt.QPainter(surface)
        painter.setBrush(QtCore.Qt.white)
        painter.drawRect(painter.window())
        painter.setBrush(QtCore.Qt.NoBrush)
        
        x_off=60
        y_off=50
        
        if ('time' in self.lightcurve) and (False in self.lightcurve):
             
            data_x=np.array(self.lightcurve['time'],dtype=np.float64)

            if len(data_x)<2:
                return

            ymin=None
            ymax=None
            
            there_is_at_least_one_chart=False
            for i in range(listWidget.count()):
                q = listWidget.item(i)
                if q is None:
                    continue
                if q.checkState()==2:
                    there_is_at_least_one_chart=True
                    data_y=np.array(self.lightcurve[q.listindex[0]][q.listindex[1]]['data'])
                    errors_y=np.array(self.lightcurve[q.listindex[0]][q.listindex[1]]['error'])
                    
                    emax=2.0*errors_y.max()
                    
                    if data_y.shape[0]==0:
                        continue
                    
                    if len(data_y.shape)>1:
                        data_y=data_y[:,q.listindex[2]]
                
                    if ymin is None:
                        ymin=data_y.min()-emax
                    else:
                        ymin=min(ymin,data_y.min()-emax)
                
                    if ymax is None:
                        ymax=data_y.max()+emax
                    else:
                        ymax=max(ymax,data_y.max()+emax)
            
            
            if there_is_at_least_one_chart:
                utils.drawAxis(painter, (data_x.min(),data_x.max()), (ymin,ymax), x_offset=x_off, y_offset=y_off, axis_name=aname,
                               x_str_func=xStrFunc, y_str_func=yStrFunc, inverted_y=inverted)
            else:
                utils.drawAxis(painter, (0,1), (0,1), x_offset=x_off, y_offset=y_off, axis_name=aname,
                               x_str_func=xStrFunc, y_str_func=yStrFunc, inverted_y=inverted)
            
            count = 0;
            
            for i in range(listWidget.count()):
                q = listWidget.item(i)
                if q is None:
                    continue
                if q.checkState()==2:
                    data_y=np.array(self.lightcurve[q.listindex[0]][q.listindex[1]]['data'])
                    errors_y=np.array(self.lightcurve[q.listindex[0]][q.listindex[1]]['error'])
                    
                    if data_y.shape[0]==0:
                        continue
                    
                    if len(data_y.shape)>1:
                        data_y=data_y[:,q.listindex[2]]
                        errors_y=errors_y[:,q.listindex[2]]
                    utils.drawCurves(painter, data_x, data_y, (ymin,ymax), inverted_y=inverted,
                                     x_offset=x_off, y_offset=y_off,
                                     errors=errors_y,
                                     bar_type=q.chart_properties['bars'],
                                     line_type=q.chart_properties['line'],
                                     point_type=q.chart_properties['points'],
                                     color=q.chart_properties['color'],
                                     int_param=q.chart_properties['smoothing'],
                                     point_size=q.chart_properties['point_size'],
                                     line_width=q.chart_properties['line_width'])
    
    
        else:
            utils.drawAxis(painter, (0,1), (0,1),  x_offset=x_off, y_offset=y_off, axis_name=aname,
                               x_str_func=xStrFunc, y_str_func=yStrFunc, inverted_y=inverted)
            
    def getChartPoint(self,index):
        return utils.POINTS_TYPE[1+index%(len(utils.POINTS_TYPE)-1)]
            
    def getChartColor(self,index):
        try:
            return self.colors[index%len(self.colors)][0]
        except Exception:
            for i in self.colors:
                if i[1]==str(index):
                    return i[0]
                else:
                    raise ValueError('cannot find chart color '+str(index))
        
    def getChartColorIndex(self, color):
        for i in self.colors:
            if i[0]==color:
                return self.colors.index(i)
        raise ValueError('cannot find chart color '+str(color))


    def setCurrentADUCurveColor(self, idx):
        return self.setCurrentCurveColor(idx, self.wnd.aduListWidget, self.wnd.aduLabel) 
    
    def setCurrentMagCurveColor(self, idx):
        return self.setCurrentCurveColor(idx, self.wnd.magListWidget, self.wnd.magLabel) 
        
    def setCurrentCurveColor(self, idx, listWidget, surface):
        q = listWidget.currentItem()
        
        if q is None:
            return
        
        q.chart_properties['color']=self.getChartColor(idx)
        surface.repaint()

    def setCurrentADUCurveLineType(self, idx):
        return self.setCurrentCurveLineType(idx, self.wnd.aduListWidget, self.wnd.aduLabel) 
    
    def setCurrentMagCurveLineType(self, idx):
        return self.setCurrentCurveLineType(idx, self.wnd.magListWidget, self.wnd.magLabel) 
        
        
    def setCurrentCurveLineType(self, idx, listWidget, surface):
        q = listWidget.currentItem()

        if q is None:
            return
        
        try:
            linetype=utils.LINES_TYPE[idx]
        except:
            linetype=utils.LINES_TYPE[0]
            
        q.chart_properties['line']=linetype
        surface.repaint()

    def setCurrentADUCurvePointsType(self, idx):
        return self.setCurrentCurvePointsType(idx, self.wnd.aduListWidget, self.wnd.aduLabel) 
    
    def setCurrentMagCurvePointsType(self, idx):
        return self.setCurrentCurvePointsType(idx, self.wnd.magListWidget, self.wnd.magLabel) 
        
    
    def setCurrentCurvePointsType(self, idx, listWidget, surface):
        q = listWidget.currentItem()

        if q is None:
            return
        try:
            pointstype=utils.POINTS_TYPE[idx]
        except:
            pointstype=utils.POINTS_TYPE[0]
            
        q.chart_properties['points']=pointstype
        surface.repaint()

    def setCurrentADUCurveBarsType(self, idx):
        return self.setCurrentCurveBarsType(idx, self.wnd.aduListWidget, self.wnd.aduLabel) 
    
    def setCurrentMagCurveBarsType(self, idx):
        return self.setCurrentCurveBarsType(idx, self.wnd.magListWidget, self.wnd.magLabel) 
    
    def setCurrentCurveBarsType(self, idx, listWidget, surface):
        q = listWidget.currentItem()
        
        if q is None:
            return
        
        try:
            barstype=utils.BARS_TYPE[idx]
        except:
            barstype=utils.BARS_TYPE[0]          
            
        q.chart_properties['bars']=barstype
        surface.repaint()
        

    def setCurrentADUCurveSmooting(self, idx):
        return self.setCurrentCurveSmooting(idx, self.wnd.aduListWidget, self.wnd.aduLabel) 
    
    def setCurrentMagCurveSmooting(self, idx):
        return self.setCurrentCurveSmooting(idx, self.wnd.magListWidget, self.wnd.magLabel) 
    
    def setCurrentCurveSmooting(self, val, listWidget, surface):
        q = listWidget.currentItem()
        
        if q is None:
            return
        
        q.chart_properties['smoothing']=val
        surface.repaint()
        
    def setCurrentADUPointSize(self, idx):
        return self.setCurrentPointSize(idx, self.wnd.aduListWidget, self.wnd.aduLabel) 
    
    def setCurrentMagPointSize(self, idx):
        return self.setCurrentPointSize(idx, self.wnd.magListWidget, self.wnd.magLabel) 
    
    def setCurrentPointSize(self, val, listWidget, surface):
        q = listWidget.currentItem()
        
        if q is None:
            return
        
        q.chart_properties['point_size']=val
        surface.repaint()
        
    def setCurrentADULineWidth(self, idx):
        return self.setCurrentLineWidth(idx, self.wnd.aduListWidget, self.wnd.aduLabel) 
    
    def setCurrentMagLineWidth(self, idx):
        return self.setCurrentLineWidth(idx, self.wnd.magListWidget, self.wnd.magLabel) 
    
    def setCurrentLineWidth(self, val, listWidget, surface):
        q = listWidget.currentItem()
        
        if q is None:
            return
        
        q.chart_properties['line_width']=val
        surface.repaint()
            
    def _drawAlignPoints(self, painter):
        if(len(self.framelist) == 0) or (not self.showAlignPoints):
            return False
        painter.setFont(Qt.QFont("Arial", 8))  
        for i in self.framelist[self.image_idx].alignpoints:
                      
            x=i[0]+0.5
            y=i[1]+0.5
            
            painter.setCompositionMode(28)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtCore.Qt.white)
            utils.drawMarker(painter,x,y)
            painter.setCompositionMode(0)
            rect=Qt.QRectF(x+8,y+10,45,15)
            painter.setBrush(QtCore.Qt.blue)
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRect(rect)
            painter.setPen(QtCore.Qt.yellow)
            painter.drawText(rect,QtCore.Qt.AlignCenter,i[2])
            rect=Qt.QRectF(x-self.autoalign_rectangle[0]/2,
                           y-self.autoalign_rectangle[1]/2,
                           self.autoalign_rectangle[0],
                           self.autoalign_rectangle[1])
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRect(rect)
    
    def deselectAllListWidgetsItems(self):
        self.wnd.lightListWidget.setCurrentItem(None)
        self.wnd.biasListWidget.setCurrentItem(None)
        self.wnd.darkListWidget.setCurrentItem(None)
        self.wnd.flatListWidget.setCurrentItem(None)
    
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
           
    def setCurrentColorMap(self,cmapid):
        if self.__updating_mdi_ctrls:
            return
        sw = self.mdi.activeSubWindow()
        if sw is None:
            log.log(repr(self),"An operation that requires an active mdi window has been executed without any mdi windows opend!",level=logging.ERROR)
            return False
        elif not sw in self.mdi_windows:
            log.log(repr(self),"Untraced mdi window detected!",level=logging.ERROR)
            return False
        elif self.mdi_windows[sw]['type']!=guicontrols.IMAGEVIEWER:
            log.log(repr(self),"Operation not permitted on current mdi window!",level=logging.ERROR)
            return False
        else:
            cmap=cmaps.COLORMAPS[cmapid]
            self.mdi_windows[sw]['widget'].setColorMap(cmap)
        return True
            
    def showResultImage(self, newtab=True):
        if self._stk is not None:
            self.showImage(self._stk,title="stacking result", newtab=newtab)
    
    def showImage(self, image, title=None, newtab=False, mdisubwindow=None, activate_sw=True,override_cursor=True,context_subtitle=None):
        if override_cursor:
            QtGui.QApplication.instance().setOverrideCursor(QtCore.Qt.WaitCursor)
        
        if title is None:
            try:
                title = image.tool_name
            except:
                title = ""
        
        original_title=title
        
        if context_subtitle is not None:
            title="["+str(context_subtitle)+"] "+title
            
        if mdisubwindow is None:
            sw=None
            for swnd in self.mdi_windows:
                if swnd.windowTitle() == title:
                    sw = swnd
                    break
        else:
            sw = mdisubwindow
            newtab = False
        
        if ((sw is None) or (not (sw in self.mdi_windows.keys())) or
            (self.mdi_windows[sw]['type'] != guicontrols.IMAGEVIEWER)):
                newtab=True
        else:
            self.mdi_windows[sw]['status']  = guicontrols.UPDATED
            
        if newtab:
            existing_titles=[]
            for swnd in self.mdi_windows:
                existing_titles.append(swnd.windowTitle())            
            sw_title=title
            title_idx=1            
            while sw_title in existing_titles:
                sw_title=title+" <"+str(title_idx)+">"
                title_idx+=1                
            sw = self.newMdiImageViewer(sw_title)
            self.mdi_windows[sw]['status']  = guicontrols.READY
        elif activate_sw:
            self.mdi.setActiveSubWindow(sw)
        
        iv = self.mdi_windows[sw]['widget']
        
        if type(image) == utils.Frame:
            iv.showImage(self.debayerize(image.getData(asarray=True)))
            self.mdi_windows[sw]['references']=[image,]
            iv.image_features=image.alignpoints
        else:
            iv.showImage(image)
                
        self.mdi_windows[sw]['widget']  = iv
        self.mdi_windows[sw]['context'] = context_subtitle
        self.mdi_windows[sw]['name']    = original_title
                
        if override_cursor:
            QtGui.QApplication.instance().restoreOverrideCursor()
        
        return sw
    
    def showDifference(self, image=None, reference=None, newtab=False, mdisubwindow=None, reload_images=True):
        QtGui.QApplication.instance().setOverrideCursor(QtCore.Qt.WaitCursor)
        
        if mdisubwindow is None:
            swlist=self.getMdiWindowsByType(guicontrols.DIFFERENCEVIEWER)
            if len(swlist)>0:
                sw = swlist[0]
            else:
                sw = self.mdi.activeSubWindow()
        else:
            sw = mdisubwindow
            newtab = False
        
        if ((not (sw in self.mdi_windows.keys())) or
            (self.mdi_windows[sw]['type'] != guicontrols.DIFFERENCEVIEWER)):
                newtab=True
                
        if (not newtab) and (sw is not None):
            sw.setWindowTitle("manual alignment")
        else:
            sw = self.newMdiDifferenceViewer("manual alignment")
        
        iv = self.mdi_windows[sw]['widget']
        
        if (reference is None):
            reference = self.framelist[self.ref_image_idx]
        if (image is None):
            image = self.framelist[self.dif_image_idx]
            
        if  reload_images:
            iv.setRefImage(self.debayerize(reference.getData(asarray=True)))
            iv.showImage(self.debayerize(image.getData(asarray=True)))
        
        try:
            iv.setOffset(image.offset[0],image.offset[1],image.angle)
            iv.setRefShift(reference.offset[0],reference.offset[1],reference.angle)
        except:
            pass
        
        self.mdi_windows[sw]['widget']     = iv
        self.mdi_windows[sw]['references'] = [image,reference]
        self.mdi_windows[sw]['context']    = None
        self.mdi_windows[sw]['name']       = "manual alignment"
        
        QtGui.QApplication.instance().restoreOverrideCursor()
        
    #
    # MDI CONTROL FUNCTIONS
    #
    
    def updateMdiControls(self, mdisw):
        
        if mdisw is None:
            return
        
        self.__updating_mdi_ctrls=True
        
        sw_type = self.mdi_windows[mdisw]['type']
        
        log.log(repr(self),"Updating mdi subwindow "+str(mdisw)+" type="+str(sw_type),level=logging.DEBUG)
        
        if sw_type == guicontrols.IMAGEVIEWER:
            iv = self.mdi_windows[mdisw]['widget']
            cmapid = cmaps.getColormapId(iv.getColorMap())
            
            self.deselectAllListWidgetsItems()
            
            try:
                frametype = self.mdi_windows[mdisw]['references'][0].getProperty('frametype')
                
                if frametype == utils.LIGHT_FRAME_TYPE:
                    listwidget=self.wnd.lightListWidget
                elif frametype == utils.BIAS_FRAME_TYPE:
                    listwidget=self.wnd.biasListWidget
                elif frametype == utils.DARK_FRAME_TYPE:
                    listwidget=self.wnd.darkListWidget
                elif frametype == utils.FLAT_FRAME_TYPE:
                    listwidget=self.wnd.flatListWidget
                
                try:
                    listwidget.setCurrentItem(self.mdi_windows[mdisw]['references'][0].getProperty('listItem'))
                except:
                    listwidget.setCurrentItem(None)
                else:
                    if self.mdi_windows[mdisw]['status']==guicontrols.NEEDSUPDATE:
                        self.showImage(image=self.mdi_windows[mdisw]['references'][0],
                                       title=self.mdi_windows[mdisw]['name'],
                                       mdisubwindow=mdisw,
                                       context_subtitle=self.mdi_windows[mdisw]['context'])
            except:
                pass
        else:
            self.deselectAllListWidgetsItems()
        
        self.__updating_mdi_ctrls=False
        
    def newMdiWindow(self, widget=None, wtype='unknown', title=""):
        sw = self.mdi.addSubWindow(widget)
        sw.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        sw.setWindowTitle(str(title))
        self.mdi_windows[sw]={}
        self.mdi_windows[sw]['references']=[]
        self.mdi_windows[sw]['widget']=widget
        self.mdi_windows[sw]['type']=wtype
        return sw    
    
    def getParentMdiWindow(self, widget):
        for sw in self.mdi_windows.keys():
            if self.mdi_windows[sw]['widget'] == widget:
                return widget
        
        return None
    
    def getMdiWindowsByType(self, wtype):
        swlist=[]
        for sw in self.mdi_windows.keys():
            if self.mdi_windows[sw]['type'] == wtype:
                swlist.append(sw)
        return swlist
    
    def showInMdiWindow(self, widget, wtype, title=""):
        sw = self.newMdiWindow(widget, wtype, title)
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
    
    
    def newMdiImageViewer(self,title=""):
        iv = guicontrols.ImageViewer(self.statusLabelMousePos)
        sw = self.newMdiWindow(iv, guicontrols.IMAGEVIEWER, title)
        sw.destroyed.connect(self.clearMdiImageViewer)
        sw.show()
        return sw
    
    def newMdiDifferenceViewer(self,title=""):
        iv = guicontrols.DifferenceViewer()
        sw = self.newMdiWindow(iv, guicontrols.DIFFERENCEVIEWER, title)
        sw.destroyed.connect(self.clearMdiImageViewer)
        sw.show()
        return sw
        
    def clearGenericMdiWindow(self, swnd):
        self.mdi_windows.pop(swnd)
        
    def clearMdiImageViewer(self, swnd):
        return self.clearGenericMdiWindow(swnd)
        
    #
    #
    #
    
    
    def setUpStatusBar(self):    
        log.log(repr(self),"Setting up statusbar...",level=logging.DEBUG)
        self.progress = Qt.QProgressBar()
        self.progress.setRange(0,100)
        self.progress.setMaximumSize(400,25)
        self.cancelProgress=Qt.QPushButton(tr('cancel'))
        self.cancelProgress.clicked.connect(self.canceled)
        self.statusBar.addPermanentWidget(self.statusLabelMousePos)
        self.statusBar.addPermanentWidget(self.cancelProgress)
        self.statusBar.addPermanentWidget(self.progress)
        self.progress.hide()
        self.cancelProgress.hide()
        self.statusBar.showMessage(tr('Welcome!'))

    
    def buildMenus(self):
        
        self.mainMenuBar = self.wnd.menuBar()
        
        if self.mainMenuBar is None:
            log.log(repr(self),"Creating menu bar...",level=logging.DEBUG)
            self.mainMenuBar = Qt.QMenuBar()
            self.wnd.setMenuBar(self.mainMenuBar)
        
        log.log(repr(self),"Setting up menus...",level=logging.DEBUG)
        
        self.action_exit = QtGui.QAction(utils.getQIcon("application-exit"), tr('exit'), self)
        self.action_exit.triggered.connect(self.wnd.close)
        
        self.action_load_project = QtGui.QAction(utils.getQIcon("document-open"), tr('Load project'), self)
        self.action_load_project.triggered.connect(self.doLoadProject)
        
        self.action_new_project = QtGui.QAction(utils.getQIcon("document-new"), tr('New project'), self)
        self.action_new_project.triggered.connect(self.doNewProject)
        
        self.action_save_project = QtGui.QAction(utils.getQIcon("document-save"), tr('Save project'), self)
        self.action_save_project.triggered.connect(self.doSaveProject)
        
        self.action_save_project_as = QtGui.QAction(utils.getQIcon("document-save-as"), tr('Save project as'), self)
        self.action_save_project_as.triggered.connect(self.doSaveProjectAs)
        
        self.action_add_files = QtGui.QAction(utils.getQIcon("insert-image"), tr('Add images/videos'), self)
        self.action_add_files.triggered.connect(self.doLoadFiles)
        
        self.action_lock_toolbars = QtGui.QAction(utils.getQIcon(None), tr('Lock tool-bars'), self)
        self.action_lock_toolbars.toggled.connect(self.setToolBarsLock)
        self.action_lock_toolbars.setCheckable(True)
                
        self.action_show_preferences = QtGui.QAction(utils.getQIcon(), tr('Show preferences'), self)
        self.action_show_preferences.triggered.connect(self.doSetPreferences)
        
        self.action_show_about = QtGui.QAction(utils.getQIcon("help-about"), tr('About lxnstack'), self)
        self.action_show_about.triggered.connect(self.doShowAbout)
        
        self.action_show_manual = QtGui.QAction(utils.getQIcon("help-contents"), tr('Show User\'s Manual'), self)
        self.action_show_manual.triggered.connect(self.doShowUserMan)
        
        self.action_align = QtGui.QAction(utils.getQIcon("align-images"), tr('Align images'), self)
        self.action_align.triggered.connect(self.doAlign)
        
        self.action_stack = QtGui.QAction(utils.getQIcon("stack-images"), tr('Stack images'), self)
        self.action_stack.triggered.connect(self.doStack)
        
        self.action_edit_select = QtGui.QAction(utils.getQIcon("edit-select"), tr('Select'), self)
        #self.action_edit_select.triggered.connect(self.doSetModeSelect)
        
        self.action_edit_pan = QtGui.QAction(utils.getQIcon("edit-pan"), tr('Pan'), self)
        #self.action_edit_pan.triggered.connect(self.doSetModePan)
                
        self.action_save_result = QtGui.QAction(utils.getQIcon("save-image"), tr('Save resulting image'), self)
        self.action_save_result.triggered.connect(self.doSaveResult)
        
        self.action_save_video = QtGui.QAction(utils.getQIcon("video-x-generic"), tr('Export images sequence as a video'), self)
        self.action_save_video.triggered.connect(self.doSaveVideo)
        
        self.action_gen_lightcurves = QtGui.QAction(utils.getQIcon("generate-lightcurves"), tr('Generate lightcurves'), self)
        self.action_gen_lightcurves.triggered.connect(self.doGenerateLightCurves)

        self.action_enable_rawmode = QtGui.QAction(utils.getQIcon("bayer-mode"), tr('Enable raw-mode'), self)
        self.action_enable_rawmode.triggered.connect(self.updateBayerMatrix)
        self.action_enable_rawmode.setCheckable(True)
        
        self.action_enable_video = QtGui.QAction(utils.getQIcon(""), tr('Enable preview'), self)
        self.action_enable_video.setCheckable(True)
        self.action_enable_video.toggled.connect(self.enableVideoPreview)
        
        self.action_start_capture = QtGui.QAction(utils.getQIcon("video-recording-start"), tr('Start capturing'), self)
        self.action_start_capture.triggered.connect(self.startDirectVideoCapture)
        self.action_start_capture.setEnabled(False)
        
        self.action_stop_capture = QtGui.QAction(utils.getQIcon("video-recording-stop"), tr('Stop capturing'), self)
        self.action_stop_capture.triggered.connect(self.stopDirectVideoCapture)
        self.action_stop_capture.setEnabled(False)
        
        self.action_sched_capture = QtGui.QAction(utils.getQIcon("video.scheduler"), tr('open scheduler'), self)
        self.action_sched_capture.triggered.connect(self.videoCaptureScheduler.show)
        
        self.action_take_shot = QtGui.QAction(utils.getQIcon("video-single-shot"), tr('Take single shot'), self)
        self.action_take_shot.triggered.connect(self.oneShot)
        
        log.log(repr(self),"Bulding menu trees...",level=logging.DEBUG)

        menu_files = self.mainMenuBar.addMenu(tr("Files"))
        menu_video = self.mainMenuBar.addMenu(tr("Video capture"))
        menu_edit = self.mainMenuBar.addMenu(tr("Edit"))
        menu_stacking = self.mainMenuBar.addMenu(tr("Stacking"))
        menu_lightcurves = self.mainMenuBar.addMenu(tr("Lightcurves"))
        menu_settings = self.mainMenuBar.addMenu(tr("Settings"))
        menu_about = self.mainMenuBar.addMenu("?")
        
        #Files menu
        menu_files.addAction(self.action_add_files)
        menu_files.addSeparator()
        menu_files.addAction(self.action_new_project)
        menu_files.addAction(self.action_load_project)
        menu_files.addAction(self.action_save_project)
        menu_files.addAction(self.action_save_project_as)
        menu_files.addSeparator()
        menu_files.addAction(self.action_exit)
        
        #Video menu
        menu_video.addAction(self.action_enable_video)
        menu_video.addAction(self.action_sched_capture)
        menu_video.addAction(self.action_take_shot)
        menu_video.addAction(self.action_start_capture)
        menu_video.addAction(self.action_stop_capture)
        self.capture_devices_menu=menu_video.addMenu("capture devices")
        
        #Edit menu
        menu_edit.addAction(self.action_edit_select)
        menu_edit.addAction(self.action_edit_pan)
        menu_edit.addSeparator()
        
        #Stacking menu
        menu_stacking.addAction(self.action_align)
        menu_stacking.addAction(self.action_stack)
        menu_stacking.addAction(self.action_save_result)        
        menu_stacking.addAction(self.action_save_video)
        
        #Ligthcurves menu
        
        menu_lightcurves.addAction(self.action_gen_lightcurves)
        
        #Settings menu
        menu_settings.addAction(self.action_show_preferences)
        menu_settings.addAction(self.action_lock_toolbars)
        
        #About menu
        menu_about.addAction(self.action_show_manual)
        menu_about.addSeparator()
        menu_about.addAction(self.action_show_about)
    
    
    def _setUpMainToolBar(self):
        maintoolbar = Qt.QToolBar('Main')
        
        maintoolbar.setObjectName("Main ToolBar")
        
        #TODO: complete this seciton
                                        
        maintoolbar.addAction(self.action_new_project)
        maintoolbar.addAction(self.action_load_project)
        maintoolbar.addAction(self.action_add_files)
        maintoolbar.addAction(self.action_save_project)
        maintoolbar.addAction(self.action_save_project_as)
        
                                        
        return maintoolbar
    
    def _setUpStackingToolBar(self):
        toolbar = Qt.QToolBar('Stacking')
        
        toolbar.setObjectName("Stacking ToolBar")
        
        #TODO: complete this seciton
                                
        
        toolbar.addAction(self.action_align)
        toolbar.addAction(self.action_stack)
        toolbar.addAction(self.action_save_result)
                                        
        return toolbar
    
    def _setUpMiscToolBar(self):
        
        toolbar = Qt.QToolBar('Misc')
        
        toolbar.setObjectName("Misc ToolBar")
                
        self.bayerComboBox=guicontrols.ToolComboBox(tr("matrix type:"),tooltip=tr("Specify the type of bayer matrix used"))
        self.bayerComboBox.setEnabled(False)
        self.bayerComboBox.currentIndexChanged.connect(self.updateBayerMatrix)
        
        self.bayerComboBox.addItem(utils.getQIcon("bayer-rggb"),"RGGB")
        self.bayerComboBox.addItem(utils.getQIcon("bayer-grgb"),"GRGB")
        self.bayerComboBox.addItem(utils.getQIcon("bayer-gbrg"),"GBRG")
        self.bayerComboBox.addItem(utils.getQIcon("bayer-bggr"),"BGGR")
        
        toolbar.addAction(self.action_enable_rawmode)
        self.action_bayer=toolbar.addWidget(self.bayerComboBox)
        
        self.action_bayer.setVisible(self.action_enable_rawmode.isChecked())
        
        self.action_enable_rawmode.toggled.connect(self.action_bayer.setVisible)
        
        return toolbar
    
    def _setUpVideoCaptureToolBar(self):
        toolbar = Qt.QToolBar('Video')
        
        toolbar.setObjectName("VideoCapture ToolBar")
        
        devices_button = QtGui.QToolButton()
        devices_button.setMenu(self.capture_devices_menu)
        devices_button.setPopupMode(QtGui.QToolButton.InstantPopup)
        
        toolbar.addWidget(devices_button)
        
        toolbar.addAction(self.action_enable_video)
        toolbar.addAction(self.action_start_capture)
        toolbar.addAction(self.action_stop_capture)        
        
        self.directVideoCaptureTypeComboBox=guicontrols.ToolComboBox(tr("output:"),tooltip=tr("Specify how to save the captured images"))
        self.directVideoCaptureTypeComboBox.addItem(utils.getQIcon("type-video-file"),"video file")
        self.directVideoCaptureTypeComboBox.addItem(utils.getQIcon("type-frame-sequence"),"frame sequence")
        self.directVideoCaptureTypeComboBox.setEnabled(False)
        toolbar.addWidget(self.directVideoCaptureTypeComboBox)
        
        return toolbar
    
    
    def addToolBar(self,toolbar,area=QtCore.Qt.TopToolBarArea,newline=False):
        self.wnd.addToolBar(area,toolbar)
        self.toolbars.append(toolbar)
        
        if newline:
            self.wnd.insertToolBarBreak(toolbar)
    
    def setUpToolBars(self):
        
        log.log(repr(self),"Setting up toolbars...",level=logging.DEBUG)
        
        self.toolbars=[]
        
        self.addToolBar(self._setUpMainToolBar())
        self.addToolBar(self._setUpMiscToolBar())
        self.addToolBar(self._setUpVideoCaptureToolBar(),True)
        self.addToolBar(self._setUpStackingToolBar())
        
        self.setToolBarsLock(self.action_lock_toolbars.isChecked())
                            
    def setToolBarsLock(self,locked):

        for tb in self.toolbars:
            tb.setFloatable(False)
            tb.setMovable(not locked)
            
    def lock(self, show_cancel = True):
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
        #self.wnd.MainFrame.setEnabled(False)
        self.wnd.menubar.setEnabled(False)
        
    def unlock(self):
        self.statusBar.clearMessage()
        self.progress.hide()
        self.cancelProgress.hide()
        self.progress.reset()
        self.wnd.toolBox.setEnabled(True)
        for tb in self.toolbars:
            tb.setEnabled(True)
        #self.wnd.MainFrame.setEnabled(True)
        self.wnd.menubar.setEnabled(True)
        QtGui.QApplication.instance().restoreOverrideCursor()

    def canceled(self):
        self.wasCanceled=True
    
    def loadFiles(self, newlist=None):

        oldlist=self.framelist[:]

        if newlist is None:
            open_str=tr("All supported images")+self.images_extensions+";;"+tr("All files *.* (*.*)")
            newlist=list(Qt.QFileDialog.getOpenFileNames(self.wnd,
                                                         tr("Select one or more files"),
                                                         self.current_dir,
                                                         open_str,
                                                         None,
                                                         utils.DIALOG_OPTIONS)
                        )

        self.statusBar.showMessage(tr('Loading files, please wait...'))
        
        if len(newlist) == 0:
            return
        
        if len(self.framelist) > 0:
            imw = self.currentWidth
            imh = self.currentHeight
            dep = self.currentDepht[0:3]
        else:
            ref = utils.Frame(str(newlist[0]), **self.frame_open_args)
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
               
        
        self.current_dir=os.path.dirname(str(newlist[0]))
        rejected=''
        
        self.progress.setMaximum(len(newlist))
        self.lock()
        self.statusBar.showMessage(tr('Analyzing images, please wait...'))
        count=0
        warnings=False
        listitemslist=[]
        for i in newlist:
            count+=1
            if not (i in self.framelist): #TODO:fix here: string must be compared to string
                page = 0
                img=utils.Frame(str(i),page, **self.frame_open_args)
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
                        q=Qt.QListWidgetItem(img.tool_name)
                        q.setCheckState(2)
                        q.exif_properties=img.properties
                        q.setToolTip(img.long_tool_name)
                        listitemslist.append(q)
                        img.addProperty('listItem',q)
                        img.addProperty('frametype',utils.LIGHT_FRAME_TYPE)
                        self.framelist.append(img)
                    page+=1
                    img=utils.Frame(str(i),page,  **self.frame_open_args)
                    if self.progressWasCanceled():
                        break
                    
            self.progress.setValue(count)
            if self.progressWasCanceled():
                self.framelist=oldlist
                return False
        self.unlock()
        
        for item in listitemslist:
            self.wnd.lightListWidget.addItem(item)
            
        newlist=[]

        if warnings:
            msgBox = Qt.QMessageBox(self.wnd)
            msgBox.setText(tr("Some images have different size or number of channels and will been ignored.\n"))
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
            if not self.addDarkFiles(self.dark_dir, ignoreErrors=True):
                pass

            self.flat_dir = os.path.join(self.current_dir,'flat')
            self.statusBar.showMessage(tr('Searching for flatfiled frames, please wait...'))
            if not self.addFlatFiles(self.flat_dir, ignoreErrors=True):
                pass

        self.statusBar.showMessage(tr('DONE'))
        
        if (len(self.framelist)>0):
            self.unlockSidebar()

        self.statusBar.showMessage(tr('Ready'))

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
        while listwidget.count()>0:
            q = listwidget.takeItem(0)
            self.closeAllMdiWindows(framelist.pop(listwidget.currentRow()))
            del q
        framelist=[]
        listwidget.clear()
        clearbutton.setEnabled(False)

    def addFrameFiles(self, frametype, framelistwidget, framelist, clearbutton, directory=None, ignoreErrors=False):
        if directory is None:
            open_str=tr("All supported images")+self.images_extensions+";;"+tr("All files *.* (*.*)")
            files = list(Qt.QFileDialog.getOpenFileNames(self.wnd,
                                                         tr("Select one or more files"),
                                                         self.current_dir,
                                                         open_str,
                                                         None,
                                                         utils.DIALOG_OPTIONS)
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

            QtGui.QApplication.instance().processEvents()
            self.progress.setValue(count)
            
            
            if (os.path.isfile(str(fn))): #TODO: check for duplicates

                page=0
                i=utils.Frame(str(fn),page, **self.frame_open_args)
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
                        framelist.append(i)
                        q=Qt.QListWidgetItem(i.tool_name,framelistwidget)
                        q.setToolTip(i.long_tool_name)
                        q.setCheckState(2)
                        i.addProperty('listItem',q)
                        i.addProperty('frametype',str(frametype))
                    else:
                        warnings=True
                        rejected+=(i.url+"\n")
                        break
                    page+=1
                    i=utils.Frame(str(fn),page, **self.frame_open_args)
                    
            if self.progressWasCanceled():
                return False
            count+=1
            
        self.unlock()
        
        if warnings:
            msgBox = Qt.QMessageBox(self.wnd)
            msgBox.setText(tr("Some images have different size or number of channels and will been ignored.\n"))
            msgBox.setInformativeText(tr("All images must have the same size and number of channels.\n\n")+
                                      tr("Click the \'Show Details' button for more information.\n"))
            msgBox.setDetailedText (rejected)
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
        
        self.framelist=[]
        self.wnd.lightListWidget.clear()
        self.ref_image_idx=-1
        self.dif_image_idx=-1
        self.wnd.lightListWidget.clear()
        self.wnd.alignPointsListWidget.clear()
        self.wnd.manualAlignGroupBox.setEnabled(False)
        self.lockSidebar()
    
    def removeImage(self, clicked):
        
        self.clearResult()
        
        q = self.wnd.lightListWidget.takeItem(self.wnd.lightListWidget.currentRow())
        self.closeAllMdiWindows(self.framelist.pop(self.wnd.lightListWidget.currentRow()))
        del q
                
        if (len(self.framelist)==0):
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
        self.aligned_dark=[]
        
    def clearAlignPoinList(self):
        for frm in self.framelist:
           while len(frm.alignpoints) > 0: # flush the list and
               frm.alignpoints.pop()       # force the deletion
        self.wnd.alignPointsListWidget.clear()
        self.wnd.removePointPushButton.setEnabled(False)
        
    def clearStarsList(self):
        while len(self.starslist) > 0:       # flush the list and
            self.starslist.alignpoints.pop() # force the deletion
        self.wnd.starsListWidget.clear()
        self.wnd.removeStarPushButton.setEnabled(False)
        self.action_gen_lightcurves.setEnabled(False)

    def setAllListItemsCheckState(self, state):
        for i in range(self.wnd.lightListWidget.count()):
            self.wnd.lightListWidget.item(i).setCheckState(state)

    def isBayerUsed(self):
        print self.currentDepht
        if (self.currentDepht in '1LPIF') and self.action_enable_rawmode.isChecked():
            return True
        else:
            return False

    def debayerize(self, data):
        
        if (data is not None) and (len(data.shape)==2) and self.isBayerUsed():
            log.log(repr(self),"Debayering raw image",level=logging.INFO)
            bayer = self.bayerComboBox.currentIndex()
            
            correction_factors=[1.0,1.0,1.0]
            
            #NOTE: Cv2 uses BRG images, so we must us the
            #complementery bayer matrix type. For example if
            #you want to convert form a RGGB matrix, the
            #BGGR model (BR2RGB) must be used.
            
            if bayer == 0:
                mode = cv2.cv.CV_BayerBG2RGB
                log.log(repr(self),"using bayer matrix RGGB",level=logging.DEBUG)
            elif bayer == 1:
                mode = cv2.cv.CV_BayerGB2RGB
                log.log(repr(self),"using bayer matrix GRGB",level=logging.DEBUG)
            elif bayer == 2:
                mode = cv2.cv.CV_BayerRG2RGB
                log.log(repr(self),"using bayer matrix BGGR",level=logging.DEBUG)
            else: # this shuold be only bayer == 3
                log.log(repr(self),"using bayer matrix GBGR",level=logging.DEBUG)
                mode = cv2.cv.CV_BayerGR2RGB
            
            #TODO: Create a native debayerizing algorithm
            
            new_data=cv2.cvtColor((data-data.min()).astype(np.uint16),mode).astype(self.ftype)*correction_factors
            
            return new_data
        else:
            log.log(repr(self),"Skipping debayerig",level=logging.DEBUG)
            return data

    def updateBayerMatrix(self, *arg):
        # we are forced to ignore *arg because this
        # function is connected  to multiple signals
        if len(self.framelist) == 0:
            return
                
        if self.action_enable_rawmode.isChecked():
            self.bayerComboBox.setEnabled(True)
            log.log(repr(self),"RAW-bayer mode ebabled",level=logging.DEBUG)
        else:
            self.bayerComboBox.setEnabled(False)
            log.log(repr(self),"RAW-bayer mode disabled",level=logging.DEBUG)
        
        log.log(repr(self),"Forcing update of displayed images",level=logging.DEBUG)
        for sw in self.mdi_windows:
            self.mdi_windows[sw]['status']=guicontrols.NEEDSUPDATE
        
        # update the current mdi subwindow
        curr_mdsw=self.mdi.activeSubWindow()
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
        self.wnd.colorADUComboBox.setCurrentIndex(self.getChartColorIndex(q.chart_properties['color'])) 
        
        pointstype=q.chart_properties['points']
        linetype=q.chart_properties['line']
        barstype=q.chart_properties['bars']
        smoothing=q.chart_properties['smoothing']
        pointsize=q.chart_properties['point_size']
        linewidth=q.chart_properties['line_width']
        
        try:
            pnt_index=utils.POINTS_TYPE.index(pointstype)
            self.wnd.pointsADUComboBox.setCurrentIndex(pnt_index)
        except:
            self.wnd.pointsADUComboBox.setCurrentIndex(1)
            
        try:
            ln_index=utils.LINES_TYPE.index(linetype)
            self.wnd.lineADUComboBox.setCurrentIndex(ln_index)
        except:
            self.wnd.lineADUComboBox.setCurrentIndex(0)

        try:
            bar_index=utils.BARS_TYPE.index(barstype)
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
        self.wnd.colorMagComboBox.setCurrentIndex(self.getChartColorIndex(q.chart_properties['color'])) 
        
        pointstype=q.chart_properties['points']
        linetype=q.chart_properties['line']
        barstype=q.chart_properties['bars']
        smoothing=q.chart_properties['smoothing']
        pointsize=q.chart_properties['point_size']
        linewidth=q.chart_properties['line_width']
                
        try:
            pnt_index=utils.POINTS_TYPE.index(pointstype)
            self.wnd.pointsMagComboBox.setCurrentIndex(pnt_index)
        except:
            self.wnd.pointsMagComboBox.setCurrentIndex(1)
            
        try:
            ln_index=utils.LINES_TYPE.index(linetype)
            self.wnd.lineMagComboBox.setCurrentIndex(ln_index)
        except:
            self.wnd.lineMagComboBox.setCurrentIndex(0)

        try:
            bar_index=utils.BARS_TYPE.index(barstype)
            self.wnd.barsMagComboBox.setCurrentIndex(bar_index)
        except:
            self.wnd.barsMagComboBox.setCurrentIndex(1)
    
        self.wnd.smoothingMagDoubleSpinBox.setValue(smoothing)
        self.wnd.pointSizeMagDoubleSpinBox.setValue(pointsize)
        self.wnd.lineWidthMagDoubleSpinBox.setValue(linewidth)
    
    def showFrameItemInNewTab(self, item, *arg):
        return self.showItemInMdiTab(item, self.framelist, self.wnd.lightListWidget, True, 'light')
    
    def showDarkFrameItemInNewTab(self, item, *arg):
        return self.showItemInMdiTab(item, self.darkframelist, self.wnd.darkListWidget, True, 'dark')
    
    def showFlatFrameItemInNewTab(self, item, *arg):
        return self.showItemInMdiTab(item, self.flatframelist, self.wnd.flatListWidget, True, 'flat')
    
    def showBiasFrameItemInNewTab(self, item, *arg):
        return self.showItemInMdiTab(item, self.biasframelist, self.wnd.biasListWidget, True, 'bias')
    
    def showFrameItemInCurrentTab(self, item, *arg):
        return self.showItemInMdiTab(item, self.framelist, self.wnd.lightListWidget, False, 'light')
    
    def showDarkFrameItemInCurrentTab(self, item, *arg):
        return self.showItemInMdiTab(item, self.darkframelist, self.wnd.darkListWidget, False, 'dark')
    
    def showFlatFrameItemInCurrentTab(self, item, *arg):
        return self.showItemInMdiTab(item, self.flatframelist, self.wnd.flatListWidget, False, 'flat')
    
    def showBiasFrameItemInCurrentTab(self, item, *arg):
        return self.showItemInMdiTab(item, self.biasframelist, self.wnd.biasListWidget, False, 'bias')
    
    def showItemInMdiTab(self, item, framelist, listwidget, innewtab,context_label=None):
        if not self.__updating_mdi_ctrls:
            row = listwidget.row(item)
            if (row >= 0) and (len(framelist)>0):
                frame = framelist[row]
                self.updateMdiControls(self.showImage(frame, newtab=innewtab,context_subtitle=context_label))
        
    def listItemChanged(self, idx):
        if self.__video_capture_started:
            return
        
        self.image_idx = self.wnd.lightListWidget.currentRow()
        
        if idx >= 0:            
            self.wnd.alignGroupBox.setEnabled(True)
            self.wnd.alignDeleteAllPushButton.setEnabled(True)
            self.updateAlignPointList()
        else:
            self.wnd.alignGroupBox.setEnabled(False)
            self.wnd.alignDeleteAllPushButton.setEnabled(False)            
        
    def manualAlignListItemChanged(self,idx):
        item = self.wnd.listWidgetManualAlign.item(idx)
        if item is None:
            return        
        self.dif_image_idx=item.original_id
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
        elif cur_item.checkState()==2:
            if not self.__operating:
                self.__operating=True
                self.ref_image_idx=cur_item.original_id
                for i in range(self.wnd.listWidgetManualAlign.count()):
                    item = self.wnd.listWidgetManualAlign.item(i)
                    if (item != cur_item) and (item.checkState() == 2):
                        item.setCheckState(0)
                self.__operating=False
        elif cur_item.checkState()==0:
            if not self.__operating:
                cur_item.setCheckState(2)
                
        if not self.__operating:
            self.showDifference()
            
    def updateAlignList(self):
        if self.ref_image_idx == -1:
            self.ref_image_idx=0
        self.wnd.listWidgetManualAlign.clear()
        count=0
        self.__operating=True
        for i in range(self.wnd.lightListWidget.count()):
            if self.wnd.lightListWidget.item(i).checkState()==2:
                item = self.wnd.lightListWidget.item(i)
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
            self.wnd.spinBoxXAlign.setValue(pnt.x)
            self.wnd.spinBoxYAlign.setValue(pnt.y)
        else:
            self.wnd.spinBoxXAlign.setEnabled(False)
            self.wnd.spinBoxYAlign.setEnabled(False)
            self.wnd.removePointPushButton.setEnabled(False)
            self.wnd.spinBoxXAlign.setValue(0)
            self.wnd.spinBoxYAlign.setValue(0)
    
    def updateCurrentAlignPoint(self, pid, pname):
        pntitem = self.wnd.alignPointsListWidget.findItems(pname,QtCore.Qt.MatchExactly)[0]
        self.wnd.alignPointsListWidget.setCurrentItem(pntitem)
        
    def updateAlignPointPosition(self, x, y, pid, pname):
        pntitem = self.wnd.alignPointsListWidget.findItems(pname,QtCore.Qt.MatchExactly)[0]
        self.wnd.alignPointsListWidget.setCurrentItem(pntitem)
        self.wnd.spinBoxXAlign.setValue(x)
        self.wnd.spinBoxYAlign.setValue(y)
                

    def starsListItemChanged(self,q):
        if q.checkState()==0:
            self.starslist[q.original_id].reference=False
            self.wnd.magDoubleSpinBox.setEnabled(False)
        else:
            self.starslist[q.original_id].reference=True
            self.wnd.magDoubleSpinBox.setEnabled(True)
        
        
    def currentStarsListItemChanged(self, idx):
        self.star_idx=idx

        if idx >= 0:
            self.wnd.spinBoxXStar.setEnabled(True)
            self.wnd.spinBoxYStar.setEnabled(True)
            self.wnd.innerRadiusDoubleSpinBox.setEnabled(True)
            self.wnd.middleRadiusDoubleSpinBox.setEnabled(True)
            self.wnd.outerRadiusDoubleSpinBox.setEnabled(True)
            self.wnd.magDoubleSpinBox.setEnabled(True)
            self.wnd.removeStarPushButton.setEnabled(True)
            pnt=self.starslist[idx]
            
            if pnt[6]==True:
                self.wnd.magDoubleSpinBox.setEnabled(True)
            else:
                self.wnd.magDoubleSpinBox.setEnabled(False)
                
            self.wnd.spinBoxXStar.setValue(pnt.x)
            self.wnd.spinBoxYStar.setValue(pnt.y)
            self.wnd.innerRadiusDoubleSpinBox.setValue(pnt.r1)
            self.wnd.middleRadiusDoubleSpinBox.setValue(pnt.r2)
            self.wnd.outerRadiusDoubleSpinBox.setValue(pnt.r3)
            self.wnd.magDoubleSpinBox.setValue(pnt.magnitude)
        else:
            self.wnd.spinBoxXStar.setEnabled(False)
            self.wnd.spinBoxYStar.setEnabled(False)
            self.wnd.innerRadiusDoubleSpinBox.setEnabled(False)
            self.wnd.middleRadiusDoubleSpinBox.setEnabled(False)
            self.wnd.outerRadiusDoubleSpinBox.setEnabled(False)
            self.wnd.removeStarPushButton.setEnabled(False)
            self.wnd.magDoubleSpinBox.setEnabled(False)
            self.wnd.spinBoxXStar.setValue(0)
            self.wnd.spinBoxYStar.setValue(0)
            self.wnd.innerRadiusDoubleSpinBox.setValue(0)
            self.wnd.middleRadiusDoubleSpinBox.setValue(0)
            self.wnd.outerRadiusDoubleSpinBox.setValue(0)
            self.wnd.magDoubleSpinBox.setValue(0)
            
    def addAlignPoint(self):
        
        if self.dlg.autoSizeCheckBox.checkState()==2:
            r_w=int(self.currentWidth/10)
            r_h=int(self.currentHeight/10)
            r_l=max(r_w,r_h)
            self.autoalign_rectangle=(r_l,r_h)
            self.dlg.rWSpinBox.setValue(r_l)
            self.dlg.rHSpinBox.setValue(r_l)
        
        imagename=self.wnd.lightListWidget.item(self.image_idx).text()
        idx=1
        for i in range(self.wnd.alignPointsListWidget.count()):
            pname='#{0:05d}'.format(i+1)
            if self.framelist[0].alignpoints[i].name != pname:
                idx=i+1
                break
            else:
                idx=i+2
                
        pname='#{0:05d}'.format(idx)
        q=Qt.QListWidgetItem(pname)
        q.setToolTip(tr('image')+' '+imagename+" \n"+tr('alignment-point')+' '+pname)
        self.wnd.alignPointsListWidget.insertItem(idx-1,q)
        
        if(len(self.framelist[self.image_idx].alignpoints)==0):
            self.wnd.removePointPushButton.setEnabled(False)
            
        for frm in self.framelist:
            alpnt = imgfeatures.AlignmentPoint(0,0,pname)
            alpnt.moved.connect(self.updateAlignPointPosition)
            frm.alignpoints.insert(idx-1, alpnt)
        
        self.wnd.alignPointsListWidget.setCurrentRow(idx-1)
        return (idx-1)
    
    def addStar(self):
                
        idx=1
        for i in range(self.wnd.starsListWidget.count()):
            pname='star#{0:05d}'.format(i+1)
            if self.starslist[i][2] != pname:
                idx=i+1
                break
            else:
                idx=i+2
                
        pname='star#{0:05d}'.format(idx)
        q=Qt.QListWidgetItem(pname)
        q.setCheckState(0)
        q.original_id=idx-1
        self.wnd.starsListWidget.insertItem(idx-1,q)
        
        if(len(self.starslist)>0):
            self.wnd.removeStarPushButton.setEnabled(True)
        
        self.starslist.insert(idx-1,[0,0,pname,7,10,15,False,0])
        
        self.imageLabel.repaint()
        self.wnd.starsListWidget.setCurrentRow(idx-1)
        
        if (not self.action_gen_lightcurves.isEnabled() and 
            (self.wnd.starsListWidget.count()>0)):
            self.action_gen_lightcurves.setEnabled(True)
        
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

    def removeStar(self):
        
        star_idx=self.wnd.starsListWidget.currentRow()
        
        self.starslist.pop(star_idx)
            
        self.wnd.starsListWidget.setCurrentRow(-1) #needed to avid bugs
        item = self.wnd.starsListWidget.takeItem(star_idx)
        
        if(len(self.starslist)==0):
            self.wnd.removeStarPushButton.setEnabled(False)
            self.action_gen_lightcurves.setEnabled(False)
            
        del item
        
    def updateAlignPointList(self):
        self.wnd.alignPointsListWidget.clear()
        crow = self.wnd.lightListWidget.currentRow()
        
        if crow < 0: # no item selected!
            return
        
        imagename=self.wnd.lightListWidget.item(crow).text()
        for pnt in self.framelist[self.image_idx].alignpoints:
            q=Qt.QListWidgetItem(pnt.name,self.wnd.alignPointsListWidget)
            q.setToolTip(tr('image')+' '+imagename+" \n"+tr('alignment-point')+' '+pnt.name)

    def shiftX(self,val):
        if (self.point_idx >= 0):
            pnt = self.framelist[self.image_idx].alignpoints[self.point_idx]
            pnt.x=val
            if pnt.aligned==True:
                pnt.aligned=False

    def shiftY(self,val):
        if (self.point_idx >= 0):
            pnt = self.framelist[self.image_idx].alignpoints[self.point_idx]
            pnt.y=val
            if pnt.aligned==True:
                pnt.aligned=False            
    
    def shiftStarX(self,val):
        if (self.star_idx >= 0):
            pnt = self.starslist[self.star_idx]
            pnt.x=val
            
    def shiftStarY(self,val):
        if (self.star_idx >= 0):
            pnt = self.starslist[self.star_idx]
            pnt.yval
            
    def setInnerRadius(self,val):
        if (self.star_idx >= 0):
            pnt = self.starslist[self.star_idx]
            pnt.r1=val
            if (pnt.r2-pnt.r2 < 2):
                self.wnd.middleRadiusDoubleSpinBox.setValue(pnt.r1+2)
            
    def setMiddleRadius(self,val):
        if (self.star_idx >= 0):
            pnt = self.starslist[self.star_idx]
            pnt.r2=val
            if (pnt.r2-pnt[3] < 2):
                self.wnd.innerRadiusDoubleSpinBox.setValue(pnt.r2-2)
            if (pnt.r3-pnt.r2 < 2):
                self.wnd.outerRadiusDoubleSpinBox.setValue(pnt.r2+2)
            
    def setOuterRadius(self,val):
        if (self.star_idx >= 0):
            pnt = self.starslist[self.star_idx]
            pnt.r3=val
            if (pnt.r3-pnt.r2 < 2):
                self.wnd.middleRadiusDoubleSpinBox.setValue(pnt.r3-2)
    
    def setMagnitude(self,val):
        self.starslist[self.star_idx][7]=val
    
    def shiftOffsetX(self,val):
        if (self.dif_image_idx >= 0):
            img = self.framelist[self.dif_image_idx]
            img.offset[0]=val
            self.showDifference(reload_images=False)
        
    def shiftOffsetY(self,val):
        if (self.dif_image_idx >= 0):
            img = self.framelist[self.dif_image_idx]
            img.offset[1]=val
            self.showDifference(reload_images=False)
            
    def rotateOffsetT(self, val):
        if (self.dif_image_idx >= 0):
            img = self.framelist[self.dif_image_idx]
            img.angle=val
            self.showDifference(reload_images=False)
            
    def updateToolBox(self, idx):
        self.ref_image_idx=-1
        QtGui.QApplication.instance().setOverrideCursor(QtCore.Qt.WaitCursor)
        
        self.showAlignPoints=False
        self.showStarPoints=False
                
        if idx==0:
            self.showStarPoints=True
        
        if idx==1:
            self.showAlignPoints=True
                    
        if idx==2:
            log.log(repr(self),"Setting up manual alignment controls",level=logging.DEBUG)
            self.manual_align=True
            log.log(repr(self),"Updating list of available images",level=logging.DEBUG)
            self.updateAlignList()
            if self.wnd.listWidgetManualAlign.count()>0:
                
                log.log(repr(self),"Selecting reference image",level=logging.DEBUG)
                self.wnd.listWidgetManualAlign.setCurrentRow(0)
                self.showDifference()
                            
        if (idx==6):
            self.showStarPoints=True
            try:
                if self.image_idx>=0:
                    # the first enabled frame must be used
                    for i in range(len(self.framelist)):
                        if self.framelist[i].isUsed():
                            self.image_idx=i
                            break
                    self.wnd.lightListWidget.setCurrentRow(self.image_idx)
                    img = self.framelist[self.image_idx]
                    self.showImage(self.debayerize(img.getData(asarray=True)))
            except IndexError:
                pass #maybe there are no images in the list yet?             
        
            
        if (idx==7):
            pass #self.showResultImage()
        
        self._old_tab_idx=idx
        QtGui.QApplication.instance().restoreOverrideCursor()
        
    def newProject(self):
        
        self.closeAllMdiWindows()
        
        self.wnd.toolBox.setCurrentIndex(0)
        self.action_enable_video.setChecked(False)
        self.bayerComboBox.setCurrentIndex(0)
        
        self.wnd.setWindowTitle(str(paths.PROGRAM_NAME)+' [Untitled Project]')
        
        self.zoom = 1
        self.min_zoom = 0
        self.actual_zoom=1
        self.exposure=0

        self.image_idx=-1
        self.ref_image_idx=-1
        self.dif_image_idx=-1
        self.point_idx=-1
        self.star_idx=-1

        self.clearResult()
    
        self.manual_align=False

        self.currentWidth=0
        self.currentHeight=0
        self.currentDepht=0
        
        self.result_w=0
        self.result_h=0
        self.result_d=3
        
        self.current_project_fname=None

        del self.framelist
        del self.biasframelist
        del self.darkframelist
        del self.flatframelist

        del self.master_bias_file
        del self.master_dark_file
        del self.master_flat_file
        
        self.master_bias_file=None
        self.master_dark_file=None
        self.master_flat_file=None

        self.framelist=[]
        self.biasframelist=[]     
        self.darkframelist=[]
        self.flatframelist=[]
        self.starslist=[]
        self.lightcurve={}
        
        self.lockSidebar()
        
        self.action_align.setEnabled(False)
        self.action_stack.setEnabled(False)
        self.deactivateResultControls()
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
        self.current_project_fname = str(Qt.QFileDialog.getSaveFileName(self.wnd, tr("Save the project"),
                                         os.path.join(self.current_dir,'Untitled.lxn'),
                                         "Project (*.lxn);;All files (*.*)", None,
                                         utils.DIALOG_OPTIONS))
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
            if info is not None:
                msgBox.setInformativeText(str(info))
            msgBox.setIcon(Qt.QMessageBox.Critical)
            msgBox.exec_()
            return False

    def _save_project(self):
        
        self.lock(False)
        self.progress.reset()
        self.statusBar.showMessage(tr('saving project, please wait...'))
        
        if self.action_enable_rawmode.isChecked():
            bayer_mode=self.bayerComboBox.currentIndex()
        else:
            bayer_mode=-1
        
        doc = minidom.Document()
        
        root=doc.createElement('project')
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
        
        #<information> section
        information_node.setAttribute('width',str(int(self.currentWidth)))
        information_node.setAttribute('height',str(int(self.currentHeight)))
        information_node.setAttribute('mode',str(self.currentDepht))
        information_node.setAttribute('bayer-mode',str(int(bayer_mode)))
        
        current_dir_node = doc.createElement('current-dir')
        current_row_node = doc.createElement('current-row')
        master_bias_node = doc.createElement('master-bias')
        master_dark_node = doc.createElement('master-dark')
        master_flat_node = doc.createElement('master-flat')
        align_rect_node  = doc.createElement('align-rect')
        max_points_node  = doc.createElement('max-align-points')
        min_quality_node = doc.createElement('min-point-quality')
        
        
        information_node.appendChild(current_dir_node)
        information_node.appendChild(current_row_node)
        information_node.appendChild(master_bias_node)
        information_node.appendChild(master_dark_node)
        information_node.appendChild(master_flat_node)
        information_node.appendChild(align_rect_node)
        information_node.appendChild(max_points_node)
        information_node.appendChild(min_quality_node)
        
        current_dir_node.setAttribute('url',str(self.current_dir))
        current_row_node.setAttribute('index',str(self.image_idx))
        master_bias_node.setAttribute('checked',str(self.wnd.masterBiasCheckBox.checkState()))
        master_bias_node.setAttribute('mul',str(self.master_bias_mul_factor))
        master_dark_node.setAttribute('checked',str(self.wnd.masterDarkCheckBox.checkState()))
        master_dark_node.setAttribute('mul',str(self.master_dark_mul_factor))
        master_flat_node.setAttribute('checked',str(self.wnd.masterFlatCheckBox.checkState()))
        master_flat_node.setAttribute('mul',str(self.master_flat_mul_factor))
        align_rect_node.setAttribute('width',str(self.autoalign_rectangle[0]))
        align_rect_node.setAttribute('height',str(self.autoalign_rectangle[1]))
        align_rect_node.setAttribute('whole-image',str(self.auto_align_use_whole_image))
        max_points_node.setAttribute('value',str(self.max_points))
        min_quality_node.setAttribute('value',str(self.min_quality))

        url=doc.createElement('url')
        master_bias_node.appendChild(url)
        url_txt=doc.createTextNode(str(self.wnd.masterBiasLineEdit.text()))
        url.appendChild(url_txt)

        url=doc.createElement('url')
        master_dark_node.appendChild(url)
        url_txt=doc.createTextNode(str(self.wnd.masterDarkLineEdit.text()))
        url.appendChild(url_txt)
        
        url=doc.createElement('url')
        master_flat_node.appendChild(url)
        url_txt=doc.createTextNode(str(self.wnd.masterFlatLineEdit.text()))
        url.appendChild(url_txt)
        
        total_bias = len(self.biasframelist)
        total_dark = len(self.darkframelist)
        total_flat = len(self.flatframelist)
        total_imgs = len(self.framelist)
        total_strs = len(self.starslist)
        
        self.progress.setMaximum(total_bias+total_dark+total_flat+total_imgs+total_strs-1)
        
        count=0
        
        #<bias-frams> section
        for i in self.biasframelist:

            self.progress.setValue(count)
            count+=1
            im_bias_used = str(i.isUsed())
            im_bias_name = str(i.tool_name)
            im_bias_url  = i.url
            im_bias_page = i.page
            image_node = doc.createElement('image')
            image_node.setAttribute('name',im_bias_name)
            image_node.setAttribute('used',im_bias_used)
            
            bias_frames_node.appendChild(image_node)
            
            url=doc.createElement('url')
            image_node.appendChild(url)
            url_txt=doc.createTextNode(im_bias_url)
            url.appendChild(url_txt)
            url.setAttribute('page',str(im_bias_page))
        
        #<dark-frams> section
        for i in self.darkframelist:

            self.progress.setValue(count)
            count+=1
            im_dark_used = str(i.isUsed())
            im_dark_name = str(i.tool_name)
            im_dark_url  = i.url
            im_dark_page = i.page
            image_node = doc.createElement('image')
            image_node.setAttribute('name',im_dark_name)
            image_node.setAttribute('used',im_dark_used)
            
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
            im_flat_used = str(i.isUsed())
            im_flat_name = str(i.tool_name)
            im_flat_url  = i.url
            im_flat_page = i.page
            image_node = doc.createElement('image')
            image_node.setAttribute('name',im_flat_name)
            image_node.setAttribute('used',im_flat_used)
            
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
            im_used = str(img.isUsed())
            im_name = str(img.tool_name)
            im_url  = img.url
            im_page = img.page
            image_node = doc.createElement('image')
            image_node.setAttribute('name',im_name)
            image_node.setAttribute('used',im_used)
            
            pict_frames_node.appendChild(image_node)

            for point in img.alignpoints:
                point_node=doc.createElement('align-point')
                point_node.setAttribute('x',str(int(point.x)))
                point_node.setAttribute('y',str(int(point.y)))
                point_node.setAttribute('id',str(point.id))
                point_node.setAttribute('name',str(point.name))
                point_node.setAttribute('aligned',str(point.aligned))
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

        #photometry section
        photometry_node.setAttribute('time_type',str(int(self.use_image_time)))
        for i in range(len(self.starslist)):
            s=self.starslist[i]
            self.progress.setValue(count)
            count+=1
            star_node = doc.createElement('star')
            star_node.setAttribute('x',str(int(s.x)))
            star_node.setAttribute('y',str(int(s.y)))
            star_node.setAttribute('name',str(s.name))
            star_node.setAttribute('id',str(s.id))
            star_node.setAttribute('inner_radius',str(float(s.r1)))
            star_node.setAttribute('middle_radius',str(float(s.r2)))
            star_node.setAttribute('outer_radius',str(float(s.r3)))
            star_node.setAttribute('reference',str(int(s.reference)))
            star_node.setAttribute('magnitude',str(float(s.magnitude)))
            star_node.setAttribute('idx',str(int(i)))
            photometry_node.appendChild(star_node)
            
        try:
            f = open(self.current_project_fname,'w')
            f.write(doc.toprettyxml(' ','\n'))
            f.close()
        except IOError as err:
            log.log(repr(self),"Cannot save the project: " + str(err),level=logging.ERROR)
            msgBox = Qt.QMessageBox(self.wnd)
            msgBox.setText(tr("Cannot save the project: ")+ str(err))
            msgBox.setInformativeText(tr("Assure you have the permissions to write the file."))
            msgBox.setIcon(Qt.QMessageBox.Critical)
            msgBox.exec_()
            del msgBox
            self.unlock()
            return
        
        self.wnd.setWindowTitle(str(paths.PROGRAM_NAME)+' ['+self.current_project_fname+']')
        self.unlock()
    
    def loadProject(self,pname=None):
        
        log.log(repr(self),'loading project, please wait...',level=logging.INFO)
        old_fname = self.current_project_fname
        
        if pname is None:
            project_fname = str(Qt.QFileDialog.getOpenFileName(self.wnd,
                                                            tr("Open a project"),
                                                            os.path.join(self.current_dir,'Untitled.lxn'),
                                                            "Project (*.lxn *.prj);;All files (*.*)", None,
                                                            utils.DIALOG_OPTIONS)
                            )
        else:
            project_fname=pname
            
        if project_fname.replace(' ','') == '':
            log.log(repr(self),' no project selected, retvert to previous state',level=logging.INFO) 
            return False
        else:
            log.log(repr(self),' project name: \''+str(project_fname)+'\'',level=logging.DEBUG) 
            
        try:
            dom = minidom.parse(project_fname)
        except Exception as err:
            log.log(repr(self),'failed to parse project, xml formatting error',level=logging.ERROR) 
            return self.corruptedMsgBox(err)       

        self.statusBar.showMessage(tr('loading project, please wait...'))
        self.lock(False)

        try:
            root = dom.getElementsByTagName('project')[0]
            
            information_node = root.getElementsByTagName('information')[0]
            dark_frames_node = root.getElementsByTagName('dark-frames')[0]
            flat_frames_node = root.getElementsByTagName('flat-frames')[0]
            pict_frames_node = root.getElementsByTagName('frames')[0]
            
            try: #backward compatibility
                bias_frames_node = root.getElementsByTagName('bias-frames')[0]
                total_bias =len(bias_frames_node.getElementsByTagName('image'))
                master_bias_node = information_node.getElementsByTagName('master-bias')[0]
                master_bias_checked=int(master_bias_node.getAttribute('checked'))
                master_bias_mul_factor=float(master_bias_node.getAttribute('mul'))
                _bias_section=True
            except Exception as exc:
                log.log(repr(self),'no bias section',level=logging.DEBUG)
                total_bias=0
                master_bias_node=None
                _bias_section=False
            
            try:
                photometry_node = root.getElementsByTagName('photometry')[0]
                _fotometric_section=True
            except Exception as exc:
                log.log(repr(self),'no fotometric section, skipping star loading',level=logging.DEBUG)
                _fotometric_section=False
                                
            total_dark = len(dark_frames_node.getElementsByTagName('image'))
            total_flat = len(flat_frames_node.getElementsByTagName('image'))
            total_imgs =len(pict_frames_node.getElementsByTagName('image'))
            
            self.progress.reset()
            self.progress.setMaximum(total_bias+total_dark+total_flat+total_imgs-1)
            count=0
            
            log.log(repr(self),'loading project information',level=logging.DEBUG)
            
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
            
            try:
                bayer_mode=int(information_node.getAttribute('bayer-mode'))
            except:
                bayer_mode=-1
                
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
                master_bias_url=master_bias_node.getElementsByTagName('url')[0].childNodes[0].data
            except:
                master_bias_url = ''

            try:
                master_dark_url=master_dark_node.getElementsByTagName('url')[0].childNodes[0].data
            except:
                master_dark_url = ''

            try:
                master_flat_url=master_flat_node.getElementsByTagName('url')[0].childNodes[0].data
            except:
                master_flat_url = ''
                        
            biasframelist=[]
            biasListWidgetElements = []    
            if _bias_section:
                log.log(repr(self),'reading bias-frames section',level=logging.DEBUG)
                for node in bias_frames_node.getElementsByTagName('image'):
                    if self.progressWasCanceled():
                        return False
                    self.progress.setValue(count)
                    count+=1
                    im_bias_name = node.getAttribute('name')
                    try:
                        im_bias_used = int(node.getAttribute('used'))
                    except Exception as exc:
                        try:
                            st_im_used=str(node.getAttribute('used')).lower()
                            if st_im_used=='false':
                                im_bias_used=0
                            elif st_im_used=='true':
                                im_bias_used=2
                            else:
                                raise exc
                        except:
                            im_bias_used=2
                            
                    url_bias_node = node.getElementsByTagName('url')[0]
                    im_bias_url = url_bias_node.childNodes[0].data
                    if url_bias_node.attributes.has_key('page'):
                        im_bias_page = url_bias_node.getAttribute('page')
                        biasfrm=utils.Frame(im_bias_url,int(im_bias_page),skip_loading=False, **self.frame_open_args)
                    else:
                        biasfrm=utils.Frame(im_bias_url,0,skip_loading=False, **self.frame_open_args)
                    biasfrm.tool_name=im_bias_name
                    biasfrm.width=imw
                    biasfrm.height=imh
                    biasfrm.mode=dep
                    biasframelist.append(biasfrm)
                    q=Qt.QListWidgetItem(biasfrm.tool_name,None)
                    q.setToolTip(biasfrm.long_tool_name)
                    q.setCheckState(im_bias_used)
                    biasfrm.addProperty('listItem',q)
                    biasfrm.addProperty('frametype',utils.BIAS_FRAME_TYPE)
                    biasListWidgetElements.append(q)
            
            log.log(repr(self),'reading dark-frames section',level=logging.DEBUG)
            
            darkframelist=[]
            darkListWidgetElements = []    
            for node in dark_frames_node.getElementsByTagName('image'):
                if self.progressWasCanceled():
                    return False
                self.progress.setValue(count)
                count+=1
                im_dark_name = node.getAttribute('name')
                try:
                    im_dark_used = int(node.getAttribute('used'))
                except Exception as exc:
                    try:
                        st_im_used=str(node.getAttribute('used')).lower()
                        if st_im_used=='false':
                            im_dark_used=0
                        elif st_im_used=='true':
                            im_dark_used=2
                        else:
                            raise exc
                    except:
                        im_dark_used=2
                        
                url_dark_node = node.getElementsByTagName('url')[0]
                im_dark_url = url_dark_node.childNodes[0].data
                if url_dark_node.attributes.has_key('page'):
                    im_dark_page = url_dark_node.getAttribute('page')
                    darkfrm=utils.Frame(im_dark_url,int(im_dark_page),skip_loading=False, **self.frame_open_args)
                else:
                    darkfrm=utils.Frame(im_dark_url,0,skip_loading=False, **self.frame_open_args)
                darkfrm.tool_name=im_dark_name
                darkfrm.width=imw
                darkfrm.height=imh
                darkfrm.mode=dep
                darkframelist.append(darkfrm)
                q=Qt.QListWidgetItem(darkfrm.tool_name,None)
                q.setToolTip(darkfrm.long_tool_name)
                q.setCheckState(im_dark_used)
                darkfrm.addProperty('listItem',q)
                darkfrm.addProperty('frametype',utils.DARK_FRAME_TYPE)
                darkListWidgetElements.append(q)
            
            log.log(repr(self),'reading flatfield-frames section',level=logging.DEBUG)
            
            flatframelist=[]
            flatListWidgetElements = []    
            for node in flat_frames_node.getElementsByTagName('image'):
                if self.progressWasCanceled():
                    return False
                self.progress.setValue(count)
                count+=1
                im_flat_name = node.getAttribute('name')
                try:
                    im_flat_used = int(node.getAttribute('used'))
                except Exception as exc:
                    try:
                        st_im_used=str(node.getAttribute('used')).lower()
                        if st_im_used=='false':
                            im_flat_name=0
                        elif st_im_used=='true':
                            im_flat_name=2
                        else:
                            raise exc
                    except:
                        im_flat_name=2
                        
                url_flat_node = node.getElementsByTagName('url')[0]
                im_flat_url = url_flat_node.childNodes[0].data
                if url_flat_node.attributes.has_key('page'):
                    im_flat_page = url_flat_node.getAttribute('page')
                    flatfrm=utils.Frame(im_flat_url,int(im_flat_page),skip_loading=False, **self.frame_open_args)
                else:
                    flatfrm=utils.Frame(im_flat_url,0,skip_loading=False, **self.frame_open_args)
                flatfrm.tool_name=im_flat_name
                flatfrm.width=imw
                flatfrm.height=imh
                flatfrm.mode=dep
                flatframelist.append(flatfrm)
                q=Qt.QListWidgetItem(flatfrm.tool_name,None)
                q.setToolTip(flatfrm.long_tool_name)
                q.setCheckState(im_flat_used)
                flatfrm.addProperty('listItem',q)
                flatfrm.addProperty('frametype',utils.FLAT_FRAME_TYPE)
                flatListWidgetElements.append(q)
                
            log.log(repr(self),'reading light-frames section',level=logging.DEBUG)
            
            framelist=[]  
            listWidgetElements=[]
            for node in pict_frames_node.getElementsByTagName('image'):
                if self.progressWasCanceled():
                        return False
                self.progress.setValue(count)
                count+=1
                im_name = node.getAttribute('name')
                try:
                    im_used = int(node.getAttribute('used'))
                except Exception as exc:
                    st_im_used=str(node.getAttribute('used')).lower()
                    if st_im_used=='false':
                        im_used=0
                    elif st_im_used=='true':
                        im_used=2
                    else:
                        raise exc
                    
                im_url_node  = node.getElementsByTagName('url')[0]
                im_url  = im_url_node.childNodes[0].data

                if im_url_node.attributes.has_key('page'):
                    im_page=im_url_node.getAttribute('page')
                    frm = utils.Frame(im_url,int(im_page),skip_loading=False, **self.frame_open_args)
                else:
                    frm = utils.Frame(im_url,0,skip_loading=False, **self.frame_open_args)


                for point in node.getElementsByTagName('align-point'):
                    point_id = point.getAttribute('id')
                    point_x  = int(point.getAttribute('x'))
                    point_y  = int(point.getAttribute('y'))
                    point_al = bool(point.getAttribute('aligned')=='True')
                    pnt = imgfeatures.AlignmentPoint(point_x, point_y, point_id, point_id)
                    pnt.aligned = point_al
                    frm.alignpoints.append(pnt)
                
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
                q.exif_properties=frm.properties
                listWidgetElements.append(q)
                frm.addProperty('listItem',q)
                frm.addProperty('frametype',utils.LIGHT_FRAME_TYPE)
                framelist.append(frm)
            
            starslist=[]
            starsListWidgetElements=[]
            if _fotometric_section:
                log.log(repr(self),'reading stars section',level=logging.DEBUG)
                use_image_time=bool(int(photometry_node.getAttribute('time_type')))
                #photometry section
                for star_node in photometry_node.getElementsByTagName('star'):
                    if self.progressWasCanceled():
                        return False
                    s= imgfeatures.Star()
                    s.x=int(star_node.getAttribute('x'))
                    s.y=int(star_node.getAttribute('y'))
                    s.name=str(star_node.getAttribute('name'))
                    s.r1=float(star_node.getAttribute('inner_radius'))
                    s.r2=float(star_node.getAttribute('middle_radius'))
                    s.r3=float(star_node.getAttribute('outer_radius'))
                    s.reference=bool(int(star_node.getAttribute('reference')))
                    s.magnitude=float(star_node.getAttribute('magnitude'))
                    s.id=int(star_node.getAttribute('idx'))
                                        
                    q=Qt.QListWidgetItem(s.name,None)
                    q.setCheckState(int(2*s.reference))
                    q.original_id=oid
                    starsListWidgetElements.append(q)
                    starslist.append(s)
            else:
                use_image_time=self.use_image_time
                
        except Exception as exc:
            self.current_project_fname=old_fname
            self.unlock()
            log.log(repr(self),'An error has occurred while reading the project:\"'+str(exc)+'\"',level=logging.ERROR)
            return self.corruptedMsgBox(str(exc))
       
        self.newProject()
        
        self.current_project_fname=project_fname
                
        log.log(repr(self),'setting up project environment',level=logging.DEBUG)
        
        for item in starsListWidgetElements:
            self.wnd.starsListWidget.addItem(item)
        
        for item in biasListWidgetElements:
            self.wnd.biasListWidget.addItem(item)
        
        for item in flatListWidgetElements:
            self.wnd.flatListWidget.addItem(item)
            
        for item in darkListWidgetElements:
            self.wnd.darkListWidget.addItem(item)
            
        for item in listWidgetElements:
            self.wnd.lightListWidget.addItem(item)
         
        
        self.currentWidth=imw
        self.currentHeight=imh
        self.currentDepht=dep
        self.framelist=framelist
        self.biasframelist=biasframelist
        self.darkframelist=darkframelist
        self.flatframelist=flatframelist
        self.starslist=starslist
        self.image_idx=current_row
        self.master_bias_file=master_bias_url
        self.master_dark_file=master_dark_url
        self.master_flat_file=master_flat_url
        self.wnd.lightListWidget.setCurrentRow(current_row)
        self.autoalign_rectangle=(ar_w, ar_h)
        self.max_points=max_points
        self.min_quality=min_quality
        self.auto_align_use_whole_image=use_whole_image
        self.wnd.imageDateCheckBox.setCheckState(2*use_image_time)
        self.current_dir=current_dir
        
        if (len(self.framelist)>0):
            self.unlockSidebar()
            
            if bayer_mode >= 0:
                self.action_enable_rawmode.setChecked(True)
                self.bayerComboBox.setCurrentIndex(bayer_mode)
            else:
                self.action_enable_rawmode.setChecked(False)
            
        if _bias_section:
            self.wnd.masterBiasCheckBox.setCheckState(master_bias_checked)
            self.wnd.masterBiasLineEdit.setText(master_bias_url)
            self.wnd.biasMulDoubleSpinBox.setValue(master_bias_mul_factor)
            if (len(self.biasframelist)>0):
                self.wnd.biasClearPushButton.setEnabled(True)

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
        log.log(repr(self),'project fully loaded',level=logging.INFO)
        self.wnd.setWindowTitle(str(paths.PROGRAM_NAME)+' ['+self.current_project_fname+']')    
        self.unlock()
        
    def autoDetectAlignPoints(self):
        i = self.framelist[self.image_idx].getData(asarray=True)
        i = i.astype(np.float32)
        
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
                if points is None:
                    points=[]
                self.min_quality*=0.75
                max_iteration-=1

        else:
            points = cv2.goodFeaturesToTrack(g,self.max_points,self.min_quality,min_dist)
            if points is None:
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
        image_idx=self.wnd.lightListWidget.currentRow()
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
            skip &= self.framelist[i].alignpoints[point_idx].aligned

        #then skip
        if skip:
            return True

        r_w=Int(self.autoalign_rectangle[0]/2)
        r_h=Int(self.autoalign_rectangle[1]/2)
        x1=point.x-r_w
        x2=point.x+r_w
        y1=point.y-r_h
        y2=point.y+r_h
        
        rawi = self.framelist[image_idx].getData(asarray=True)
        refi = rawi[y1:y2,x1:x2]
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
            self.statusBar.showMessage(tr('detecting point ')+str(point_idx+1)+tr(' of ')+str(len(self.framelist[image_idx].alignpoints))+tr(' on image ')+str(i)+tr(' of ')+str(len(self.framelist)-1))
            
            if self.auto_align_use_whole_image==2:
                rawi=frm.getData(asarray=True)
            else:
                rawi=frm.getData(asarray=True)[y1-r_h:y2+r_h,x1-r_w:x2+r_w]

            cv_im=rawi.astype(np.float32)
            
            del rawi
            
            min_dif = None
            min_point=(0,0)
            #TODO: fix error occurring when align-rectangle is outside the image
            res = cv2.matchTemplate(cv_im,cv_ref,self.current_match_mode)
            minmax = cv2.minMaxLoc(res)
            del res            
            if self.auto_align_use_whole_image==2:
                frm.alignpoints[point_idx].x=minmax[2][0]+r_w
                frm.alignpoints[point_idx].y=minmax[2][1]+r_h
            else:
                frm.alignpoints[point_idx].x=minmax[2][0]+x1
                frm.alignpoints[point_idx].y=minmax[2][1]+y1
            
        self.unlock()
        
        return True
    
    def doAlign(self, clicked):
        return self.align()
        
    def align(self,do_reset=None,do_align=None,do_derot=None):
        
        result=None
        
        if (do_reset is not None) or (do_align is not None) or (do_derot is not None):
            align=(do_align==True)
            derotate=(do_derot==True)
            reset=(do_reset==True)
        elif self.align_dlg.exec_():
            align_derot = self.align_dlg.alignDerotateRadioButton.isChecked()
            align = align_derot or self.align_dlg.alignOnlyRadioButton.isChecked()
            derotate = align_derot or self.align_dlg.derotateOnlyRadioButton.isChecked()
            reset = self.align_dlg.resetRadioButton.isChecked()
        else:
            return False
        
        if reset:
            log.log(repr(self),'Resetting alignment...',level=logging.DEBUG)
            self.progress.setMaximum(len(self.framelist))
            self.lock()
            count=0
            for i in self.framelist:
                count+=1
                self.progress.setValue(count)
                if i.isUsed():
                    log.log(repr(self),'Image ' + i.name +' -> shift = (0.0, 0.0)  angle=0.0',level=logging.INFO)
                    self.statusBar.showMessage(tr('Resetting alignment for image')+' '+i.name)
                    i.setAngle(0)
                    i.setOffset((0,0))
                else:
                    log.log(repr(self),' Skipping image ' + i.name,level=logging.INFO)
            self.unlock()
        else:
            self.is_aligning = True
            log.log(repr(self),' Beginning alignment process...',level=logging.INFO)
            if self.current_align_method == 0:
                result = self._alignPhaseCorrelation(align, derotate)
            elif self.current_align_method == 1:
                result = self._alignAlignPoints(align, derotate)
            self.is_aligning = False
            
        return result
    
    def _derotateAlignPoints(self, var_matrix):
        
        vecslist=[]   
        
        for i in self.framelist:
            _tmp = []
            
            for p in i.alignpoints:                
                _tmp.append(np.array([p.x,p.y])-i.offset[0:2])
                
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
                    continue
                
                cosa=((x1*x2+y1*y2)/(vmod*rmod))
                sina=((x2*y1-x1*y2)/(vmod*rmod))
                
                if cosa>1:
                    #this should never never never occur
                    cosa=1.0
                    
                if sina>1:
                    #this should never never never occur
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
            
            mat = np.zeros((total_images,total_points,2))
            
            for i in range(total_images):
                for j in range(total_points):
                    p = self.framelist[i].alignpoints[j]
                    mat[i,j,0]=p.x
                    mat[i,j,1]=p.y
            
            x_stk = mat[...,0].mean()
            y_stk = mat[...,1].mean()
            
            mat2 = mat-[x_stk,y_stk]
            
            var = np.empty((len(mat[0])))
            avg = np.empty((len(mat[0]),2))

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
                        x+=img.alignpoints[j].x*w[j]
                        y+=img.alignpoints[j].y*w[j]
                    
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
        
        self.statusBar.showMessage(tr('Computing phase correlation, please wait...'))
        
        sw = self.newMdiImageViewer("Phase correlation")
        iv = self.mdi_windows[sw]['widget']
        iv.setColorMap(cmaps.jet)
        iv.forceDisplayLevelsFitMode(1)
        
        ref_set=False
        self.lock()
        self.progress.setMaximum(len(self.framelist))
        
        ref = None
            
        mask = utils.generateCosBell(self.currentWidth,self.currentHeight)
                
        count=0
        
        sharp1=self.wnd.sharp1DoubleSpinBox.value()
        sharp2=self.wnd.sharp2DoubleSpinBox.value()
        
        for img in self.framelist:
            
            self.progress.setValue(count)
            count+=1

            if self.progressWasCanceled():
                self.unlock()
                self.wnd.zoomCheckBox.setEnabled(True)
                self.wnd.zoomCheckBox.setCheckState(old_state)
                self.statusBar.showMessage(tr('canceled by the user'))
                return False
            
            if img.isUsed():
                QtGui.QApplication.instance().processEvents()
                if ref is None:
                    ref = img
                    log.log(repr(self),'using image '+img.name+' as reference',level=logging.INFO)
                    ref_data = ref.getData(asarray=True)
                    if len(ref_data.shape)==3:
                        ref_data=ref_data.sum(2)
                    ref_data*=mask
                    ref.setOffset([0,0])
                else:
                    log.log(repr(self),'registering image '+img.name,level=logging.INFO)
                    img_data=img.getData(asarray=True)
                    if len(img_data.shape)==3:
                        img_data=img_data.sum(2)
                    img_data*=mask
                    data=utils.register_image(ref_data,img_data,sharp1,sharp2,align,derotate,self.phase_interpolation_order)
                    self._phase_align_data=(data[1],data[2],data[0])
                    self.statusBar.showMessage(tr('shift: ')+str(data[1])+', '+
                                               tr('rotation: ')+str(data[2]))
                    del img_data
                    if (data[0] is not None) and (self.checked_show_phase_img==2):
                        iv.showImage(data[0])
                    img.setOffset(data[1])
                    img.setAngle(data[2])
                    
        del mask
        self._phase_align_data=None
        sw.close()
        self.unlock()
        self.statusBar.showMessage(tr('DONE'))       
    

    def getStackingMethod(self, method, framelist, bias_image, dark_image, flat_image, **args):
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
            return self.average(framelist, bias_image, dark_image, flat_image, **args)
        elif method==1:
            return self.median(framelist, bias_image, dark_image, flat_image, **args)
        elif method==2:
            return self.sigmaclip(framelist, bias_image, dark_image, flat_image, **args)
        elif method==3:
            return self.stddev(framelist, bias_image, dark_image, flat_image, **args)
        elif method==4:
            return self.variance(framelist, bias_image, dark_image, flat_image, **args)
        elif method==5:
            return self.maximum(framelist, bias_image, dark_image, flat_image, **args)
        elif method==6:
            return self.minimum(framelist, bias_image, dark_image, flat_image, **args)
        elif method==7:
            return self.product(framelist, bias_image, dark_image, flat_image, **args)
        else:
            #this should never happen
            log.log(repr(self),"Something that sould never happen has just happened: An unknonw stacking method has been selected!",level=logging.ERROR)
            return None
    
    def doStack(self, clicked):
        self.stack()
    
    def stack(self,method=None,skip_light=False):
        
        self.clearResult()
        """
        selecting method and setting options
        before stacking
        """
        
        if(self.wnd.masterBiasCheckBox.checkState() == 2):
            self.stack_dlg.tabWidget.setTabEnabled(1,False)
        else:
            self.stack_dlg.tabWidget.setTabEnabled(1,True)
            
        if(self.wnd.masterDarkCheckBox.checkState() == 2):
            self.stack_dlg.tabWidget.setTabEnabled(2,False)
        else:
            self.stack_dlg.tabWidget.setTabEnabled(2,True)
        
        if(self.wnd.masterFlatCheckBox.checkState() == 2):
            self.stack_dlg.tabWidget.setTabEnabled(3,False)
        else:
            self.stack_dlg.tabWidget.setTabEnabled(3,True)
        
        if skip_light:
            self.stack_dlg.tabWidget.setTabEnabled(0,False)
        else:
            self.stack_dlg.tabWidget.setTabEnabled(0,True)
            
        if method is not None:
            bias_method=method
            dark_method=method
            flat_method=method
            lght_method=method
                        
        elif self.stack_dlg.exec_():
            bias_method=self.stack_dlg.biasStackingMethodComboBox.currentIndex()
            dark_method=self.stack_dlg.darkStackingMethodComboBox.currentIndex()
            flat_method=self.stack_dlg.flatStackingMethodComboBox.currentIndex()
            lght_method=self.stack_dlg.ligthStackingMethodComboBox.currentIndex()
            
        else:
            return False
        
        bias_args={'lk':self.stack_dlg.biasLKappa.value(),
                   'hk':self.stack_dlg.biasHKappa.value(),
                   'iterations':self.stack_dlg.biasKIters.value(),
                   'debayerize_result':False}
        
        dark_args={'lk':self.stack_dlg.darkLKappa.value(),
                   'hk':self.stack_dlg.darkHKappa.value(),
                   'iterations':self.stack_dlg.darkKIters.value(),
                   'debayerize_result':False}
        
        flat_args={'lk':self.stack_dlg.flatLKappa.value(),
                   'hk':self.stack_dlg.flatHKappa.value(),
                   'iterations':self.stack_dlg.flatKIters.value(),
                   'debayerize_result':False}
                    
        lght_args={'lk':self.stack_dlg.ligthLKappa.value(),
                   'hk':self.stack_dlg.ligthHKappa.value(),
                   'iterations':self.stack_dlg.ligthKIters.value(),
                   'debayerize_result':True}
        
        hotp_args={'hp_smart':bool(self.stack_dlg.hotSmartGroupBox.isChecked()),
                   'hp_global':bool(self.stack_dlg.hotGlobalRadioButton.isChecked()),
                   'hp_trashold':self.stack_dlg.hotTrasholdDoubleSpinBox.value()}
        
        self.lock()
        
        self.master_bias_file = str(self.wnd.masterBiasLineEdit.text())
        self.master_dark_file = str(self.wnd.masterDarkLineEdit.text())
        self.master_flat_file = str(self.wnd.masterFlatLineEdit.text())
        
        if (self.wnd.masterBiasCheckBox.checkState() == 2):
            if os.path.isfile(self.master_bias_file):
                bas=utils.Frame(self.master_bias_file, **self.frame_open_args)
                self._bas=bas.getData(asarray=True, ftype=self.ftype)
            elif self.master_bias_file.replace(' ','').replace('\t','') == '':
                pass #ignore
            else:
                msgBox = Qt.QMessageBox()
                msgBox.setText(tr("Cannot open \'"+self.master_bias_file+"\':"))
                msgBox.setInformativeText(tr("the file does not exist."))
                msgBox.setIcon(Qt.QMessageBox.Critical)
                msgBox.exec_()
                return False
        elif (len(self.biasframelist)>0):
            self.statusBar.showMessage(tr('Creating master-bias, please wait...'))
            _bas=self.getStackingMethod(bias_method,self.biasframelist, None, None, None,**bias_args)
            if _bas is None:
                return False
            else:
                self._bas=_bas
        
        if (self.wnd.masterDarkCheckBox.checkState() == 2):
            if os.path.isfile(self.master_dark_file):
                drk=utils.Frame(self.master_dark_file, **self.frame_open_args)
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
            _drk=self.getStackingMethod(dark_method,self.darkframelist, None, None, None,**dark_args)
            if _drk is None:
                return False
            else:
                self._drk=_drk
                
        if (self.wnd.masterFlatCheckBox.checkState() == 2):
            if os.path.isfile(self.master_flat_file):
                flt=utils.Frame(self.master_flat_file, **self.frame_open_args)
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
            _flt=self.getStackingMethod(flat_method,self.flatframelist, None, None, None,**flat_args)
            if _flt is None:
                return False
            else:
                self._flt=_flt
        
        if skip_light:
            self.statusBar.clearMessage()
        else:
            self.statusBar.showMessage(tr('Stacking images, please wait...'))
            
            _stk=self.getStackingMethod(lght_method,self.framelist, self._bas, self._drk, self._flt,
                                        hotpixel_options=hotp_args,**lght_args)
            
            if(_stk is None):
                self.unlock()
                return False
            else:
                self._stk=_stk-_stk.min()
                QtGui.QApplication.instance().processEvents()
                del _stk
                self.showResultImage(newtab=True)
                self.activateResultControls()
                self.statusBar.showMessage(tr('DONE'))
                
        self.unlock()
        
        self.wnd.toolBox.setCurrentIndex(7)
        
        return ((lght_method,lght_args), (bias_method,bias_args), (dark_method,dark_args), (flat_method,flat_args), hotp_args)
        
    def generateMasters(self, bias_image=None, dark_image=None, flat_image=None, hot_pixels_options=None):
        log.log(repr(self),"generating master frames",level=logging.INFO)
        
        if (bias_image is not None):
            log.log(repr(self),"generating master bias-frame",level=logging.DEBUG)
            master_bias=(bias_image*self.master_bias_mul_factor)
            
        else:
            master_bias=None
            
        if (dark_image is not None):
            log.log(repr(self),"generating master dark-frame",level=logging.DEBUG)
            if (master_bias is not None):
                master_dark=(dark_image-master_bias)*self.master_dark_mul_factor
            else:
                master_dark=dark_image*self.master_dark_mul_factor
            
            log.log(repr(self),"generating hot-pixels map",level=logging.DEBUG)
            
            if hot_pixels_options['hp_smart']:
                
                trashold=hot_pixels_options['hp_trashold']
                
                if (len(master_dark.shape)==2) or hot_pixels_options['hp_global']:
                    mean_dark=master_dark.mean()
                    ddev_dark=master_dark.std()
                    hot_pixels={'global':True,
                                'data':np.argwhere(abs(master_dark-mean_dark)>=(trashold*ddev_dark))}
                    log.log(repr(self),"Found "+str(len(hot_pixels['data']))+" hot pixels",level=logging.INFO)
                elif len(master_dark.shape)==3:
                    hot_pixels={'global':False,
                                'data':[]}
                    hp_count=0
                    for c in range(master_dark.shape[2]):
                        mean_dark=master_dark[...,c].mean()
                        ddev_dark=master_dark[...,c].std()
                        hp_tmp=np.argwhere(abs(master_dark[...,c]-mean_dark)>=(trashold*ddev_dark))
                        hp_count=len(hp_tmp)
                        hot_pixels['data'].append(hp_tmp)
                        
                    log.log(repr(self),"Found "+str(hp_count)+" hot pixels",level=logging.INFO)
                
            else:
                hot_pixels=None
        else:
            master_dark=None
            hot_pixels=None
            
        if (flat_image is not None):
            log.log(repr(self),"generating master flatfield",level=logging.DEBUG)
            # this should avoid division by zero
            zero_mask = ((flat_image == 0).astype(self.ftype))*flat_image.max()
            corrected = flat_image+zero_mask
            del zero_mask
            normalizer = corrected.min()
            master_flat=((corrected/normalizer)*self.master_flat_mul_factor)
            del corrected
            
        else:
            master_flat=None
            
        return (master_bias, master_dark, master_flat, hot_pixels)
    
    def calibrate(self, image, master_bias=None, master_dark=None, master_flat=None, hot_pixels=None, debayerize_result=False, **args):
                
        if (master_bias is None) and (master_dark is None) and (master_flat is None):
            log.log(repr(self),"skipping image calibration",level=logging.INFO)
        else:
            log.log(repr(self),"calibrating image...")
            if master_bias is not None:
                log.log(repr(self),"calibrating image: subtracting bias",level=logging.DEBUG)
                image -=  master_bias
                                    
            if master_dark is not None:
                log.log(repr(self),"calibrating image: subtracting master dark",level=logging.DEBUG)
                image -=  master_dark
            
            if hot_pixels is not None:
                log.log(repr(self),"calibrating image: correcting for hot pixels",level=logging.DEBUG)
                
            
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
                cnt=0
                if hot_pixels['global']:
                    self.progress_dialog.setLabelText(tr("Correcting for hotpixels..."))
                    self.progress_dialog.setValue(0)
                    self.progress_dialog.setMaximum(len(hot_pixels['data']))
                    self.progress_dialog.show()
                    for hotp in hot_pixels['data']:
                        cnt+=1
                        if cnt % 100 == 0: # do not overload main application
                            self.progress_dialog.setValue(cnt)
                            QtGui.QApplication.instance().processEvents()
                        hotp_x=hotp[1]
                        hotp_y=hotp[0]
                        image[hotp_y,hotp_x]=utils.getNeighboursAverage(image,hotp_x,hotp_y,self.isBayerUsed())
                else:
                    total_progress=0
                    for c in range(len(hot_pixels['data'])):
                        total_progress=len(hot_pixels['data'][c])
                    self.progress_dialog.setValue(0)
                    self.progress_dialog.setMaximum(len(hot_pixels['data'][c]))
                    self.progress_dialog.show()
                    for c in range(len(hot_pixels['data'])):
                        self.progress_dialog.setLabelText(tr("Correcting for hotpixels in component "+str(c)+"..."))
                        for hotp in hot_pixels['data'][c]:
                            cnt+=1
                            if cnt % 100 == 0: # do not overload main application
                                self.progress_dialog.setValue(cnt)
                                QtGui.QApplication.instance().processEvents()
                            hotp_x=hotp[1]
                            hotp_y=hotp[0]
                            image[hotp_y,hotp_x,c]=utils.getNeighboursAverage(image[...,c],hotp_x,hotp_y,self.isBayerUsed())
                            
                            
                self.progress_dialog.hide()
            if master_flat is not None:
                log.log(repr(self),"calibrating image: dividing by master flat",level=logging.DEBUG)
                image /= master_flat  
                
        
        
        if debayerize_result:
            debay = self.debayerize(image)
            return debay
        else:
            return image
            
    def registerImages(self, img, img_data):
        if img.angle!=0:
            log.log(repr(self),"rotating of "+str(img.angle)+" degrees",level=logging.INFO)
            img_data = sp.ndimage.interpolation.rotate(img_data,img.angle,order=self.interpolation_order,reshape=False,mode='constant',cval=0.0)
            
        else:
            log.log(repr(self),"skipping rotation",level=logging.INFO)
        
        shift=np.zeros([len(img_data.shape)])
        shift[0]=-img.offset[1]
        shift[1]=-img.offset[0]
        
        if (shift[0]!=0) or (shift[1]!=0):
            
            log.log(repr(self),"shifting of "+str(shift[0:2])+" pixels",level=logging.INFO)
            img_data = sp.ndimage.interpolation.shift(img_data,shift,order=self.interpolation_order,mode='constant',cval=0.0)
            
        else:
            log.log(repr(self),"skipping shift",level=logging.INFO)
        del shift

        return img_data
    
    def nativeOperationOnImages(self, operation, name, framelist ,bias_image=None, dark_image=None,
                                flat_image=None, post_operation = None, **args):
        
        result = None
        
        if 'hotpixel_options' in args:
            hotp_args=args['hotpixel_options']
        else:
            hotp_args=None
        
        master_bias, master_dark, master_flat, hot_pixels = self.generateMasters(bias_image,dark_image,flat_image,hotp_args)
        
        total = len(framelist)
        
        log.log(repr(self),'Computing ' + str(name) + ', please wait...',level=logging.INFO)
        
        self.progress.reset()
        self.progress.setMaximum(4*(total-1))
        
        count = 0
        progress_count=0
        
        if 'chunks_size' in args and args['chunks_size']>1:
            chunks=[]
            chunks_size=int(args['chunks_size'])
        else:
            chunks_size=1
        
        for img in framelist:
   
            self.progress.setValue(progress_count)
            progress_count+=1
            
            if self.progressWasCanceled():
                return None
            
            if img.isUsed():
                count+=1
                log.log(repr(self),'Using image '+img.name,level=logging.INFO)
            else:
                progress_count+=3
                log.log(repr(self),'Skipping image '+img.name,level=logging.INFO)
                continue
            
            
            r=img.getData(asarray=True, ftype=self.ftype)
            
            if self.progressWasCanceled():
                return None
            
            self.progress.setValue(progress_count)
            progress_count+=1

            if img.isRGB() and (r.shape[2]>3):
                r = r[...,0:3]
                
            r = self.calibrate(r, master_bias, master_dark, master_flat, hot_pixels, **args)
            
            if self.progressWasCanceled():
                return None
            
            self.progress.setValue(progress_count)
            progress_count+=1
            
            r = self.registerImages(img,r)
            
            if self.progressWasCanceled():
                return None
            
            self.progress.setValue(progress_count)
            progress_count+=1
            
            
            if chunks_size>1:
                if len(chunks) <= chunks_size:
                    chunks.append(r)
                else:
                    if 'numpy_like' in args and args['numpy_like']==True:
                        result=operation(chunks, axis=0)
                    else:
                        result=operation(chunks)
                    chunks=[result,]
            else:
                if result is None:
                    result=r.copy()
                else:
                    if 'numpy_like' in args and args['numpy_like']==True:
                        result=operation((result,r), axis=0)
                    else:
                        result=operation(result,r)

            del r
        
        self.progress.setValue(4*(total-1))  
        
        if result is not None:
            if chunks_size>1 and len(chunks) > 1:
                
                if 'numpy_like' in args and args['numpy_like']==True:
                    result=operation(chunks, axis=0)
                else:
                    result=operation(chunks)
                
            self.statusBar.showMessage(tr('Computing final image...'))
            
            if post_operation is not None:
                result=post_operation(result,count)
            
        
        self.statusBar.clearMessage()
        
        return result

    """
    Executes the 'operation' on each subregion of size 'subw'x'subh' of images stored in
    temporary files listed in filelist. the original shape of the images must be passed
    as 'shape'
    """
    #TODO: make option to change subw and subh
    def _operationOnSubregions(self,operation, filelist, shape, title="", subw=256, subh=256, **args):
        
        if len(filelist) == 0:
            return None
        
        n_y_subs=shape[0]/subh
        n_x_subs=shape[1]/subw
        
        total_subs=(n_x_subs+1)*(n_y_subs+1)
        
        log.log(repr(self),"Executing "+ str(title)+": splitting images in "+str(total_subs)+" sub-regions",level=logging.DEBUG)
        self.statusBar.showMessage(tr('Computing') +' '+ str(title) + ', ' + tr('please wait...'))
        self.progress.reset
        self.progress.setMaximum(total_subs*(len(filelist)+1))
        progress_count = 0
        
        x=0
        y=0
        
        result=np.zeros(shape)
        
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
                log.log(repr(self),'Computing '+str(title)+' on subregion '+str(count)+' of '+str(total_subs),level=logging.INFO)
                self.statusBar.showMessage(tr('Computing ')+str(title)+tr(' on subregion ')+str(count)+tr(' of ')+str(total_subs))
                QtGui.QApplication.instance().processEvents()
                
                if len(args)>0:
                    try:
                        operation(lst, axis=0, out=result[yst:ynd,xst:xnd],**args)
                    except:
                        operation(lst, axis=0, out=result[yst:ynd,xst:xnd])
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

        clipped = np.ma.masked_array(array)
        
        for i in range(itr):
            sigma = np.std(array, axis=axis)
            mean = np.mean(array, axis=axis)

            min_clip=mean-lkappa*sigma
            max_clip=mean+hkappa*sigma
            
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
    
    def medianSigmaClipping(self,array, axis=-1, out=None, **args): #TODO:check -> validate -> add functionality
        
        lkappa = args['lmk']
        hkappa = args['hmk']
        itr = args['miterations']        

        clipped = np.ma.masked_array(array)
        
        for i in range(itr):
            sigma = np.std(array, axis=axis)
            mean = np.median(array, axis=axis)

            min_clip=mean-lkappa*sigma
            max_clip=mean+hkappa*sigma
            
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
            
        
    def average(self,framelist , bias_image=None, dark_image=None, flat_image=None, **args):
        return self.nativeOperationOnImages(np.add,tr('average'),framelist,
                                            bias_image, dark_image, flat_image,
                                            post_operation = np.divide, **args)
    
    def stddev(self,framelist, bias_image=None, dark_image=None, flat_image=None, **args):
        avg=self.average(framelist,  bias_image, dark_image, flat_image)
        return self.nativeOperationOnImages(lambda a1,a2: (a2-avg)**2,tr('standard deviation'),framelist,
                                            dark_image, flat_image, post_operation=lambda x,n: np.sqrt(x/(n-1)), **args)
        
    def variance(self,framelist, bias_image=None, dark_image=None, flat_image=None, **args):
        #return self.operationOnImages(np.var,tr('variance'),framelist, dark_image, flat_image)
        avg=self.average(framelist,  bias_image, dark_image, flat_image)
        return self.nativeOperationOnImages(lambda a1,a2: (a2-avg)**2,tr('variance'),framelist,
                                            dark_image, flat_image, post_operation=lambda x,n: x/(n-1), **args)
        
    #TODO: try to make a native function
    def sigmaclip(self,framelist, bias_image=None, dark_image=None, flat_image=None, **args):
        return self.operationOnImages(self.sigmaClipping,tr('sigma clipping'),framelist,  bias_image, dark_image, flat_image, **args)
    
    #TODO: try to make a native function 
    def median(self,framelist, bias_image=None, dark_image=None, flat_image=None, **args):
        return self.operationOnImages(np.median,tr('median'),framelist,  bias_image, dark_image, flat_image, **args)
            
    def maximum(self,framelist, bias_image=None, dark_image=None, flat_image=None, **args):
        #return self.operationOnImages(np.max,tr('maximum'),framelist, dark_image, flat_image)
        return self.nativeOperationOnImages(np.max,tr('maximum'),framelist,  bias_image, dark_image, flat_image,
                                            numpy_like=True, **args)
    
    def minimum(self,framelist, bias_image=None, dark_image=None, flat_image=None, **args):
        #return self.operationOnImages(np.min,tr('minimum'),framelist, dark_image, flat_image)
        return self.nativeOperationOnImages(np.min,tr('minimum'),framelist,  bias_image, dark_image, flat_image,
                                            numpy_like=True, **args)

    def product(self,framelist, bias_image=None, dark_image=None, flat_image=None, **args):
        #return self.operationOnImages(np.prod,tr('product'),framelist, dark_image, flat_image)
        return self.nativeOperationOnImages(np.prod,tr('product'),framelist, bias_image, dark_image, flat_image, numpy_like=True, **args)
    
    

    def operationOnImages(self,operation, name,framelist, bias_image=None, dark_image=None, flat_image=None, **args):
            
        result=None
                
        master_bias, master_dark, master_flat, hot_pixels = self.generateMasters(bias_image,dark_image,flat_image)

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
                        
            self.progress.setValue(progress_count)
            progress_count+=1

            if self.progressWasCanceled():
                return False

            if img.isRGB() and (r.shape[2]>3):
                r = r[...,0:3]
                
            r = self.calibrate(r, master_bias, master_dark, master_flat, hot_pixels, **args)
            
            if original_shape is None:
                original_shape = r.shape
            
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
    
    def doGenerateLightCurves(self):
        return self.generateLightCurves()
    
    def generateLightCurves(self,method=None):
        
        del self._bas
        del self._drk
        del self._flt
                
        self._drk=None
        self._flt=None
        self._bas=None
        
        log.log(repr(self),'generating light curves, please wait...',level=logging.INFO)
        
        self.stack(skip_light=True)
        
        self.wnd.tabWidget.setCurrentIndex(2)
        self.wnd.chartsTabWidget.setCurrentIndex(1)
        self.wnd.saveADUChartPushButton.setEnabled(False)
        self.wnd.saveMagChartPushButton.setEnabled(False)
        self.wnd.chartsTabWidget.setTabEnabled(1,False)
        self.wnd.chartsTabWidget.setTabEnabled(2,False)
        self.wnd.aduListWidget.clear()
        self.wnd.magListWidget.clear()
        QtGui.QApplication.instance().processEvents()
        
        self.lock()
                
        #create empty lightcurve dict
        self.lightcurve={True:{},False:{},'time':[],'info':[],'magnitudes':{}}
        self.progress.reset()     
        self.progress.setMaximum(len(self.framelist))
       
        cx=self.currentWidth/2.0
        cy=self.currentHeight/2.0
                
        count=0
        
        for i in self.starslist:
            self.lightcurve[i[6]][i[2]]={'magnitude':i[7],'data':[], 'error':[]}
            
            for comp in range(self.getNumberOfComponents()):
                self.addLightCurveListElement(str(i[2])+'-'+self.getComponentName(comp),
                                              str(i[2]),
                                              self.wnd.aduListWidget,
                                              i[6],
                                              count,
                                              16,
                                              checked=(not i[6]),
                                              component=comp)
            count+=1
            
            
        used_name_list=[]
        count=0
        
        self.use_image_time=(self.wnd.imageDateCheckBox.checkState()==2)
        
        master_bias, master_dark, master_flat, hot_pixels = self.generateMasters(self._bas,self._drk,self._flt)
        
        for img in self.framelist:
            count+=1
            if not (img.isUsed()):
                log.log(repr(self),'\nskipping image '+str(img.name),level=logging.INFO)
                continue
            else:
                log.log(repr(self),'\nusing image '+str(img.name),level=logging.INFO)
                
            self.progress.setValue(count)
            r = img.getData(asarray=True, ftype=self.ftype)
            r = self.calibrate(r, master_bias, master_dark, master_flat, hot_pixels, debayerize_result=True)
            
            if self.use_image_time:
                self.lightcurve['time'].append(img.getProperty('UTCEPOCH'))
            else:
                self.lightcurve['time'].append(count)
            
            for i in self.starslist:
                log.log(repr(self),'computing adu value for star '+str(i[2]),level=logging.INFO)
               
                di = dist(cx,cy,i[0],i[1])
                an = math.atan2((cy-i[1]),(cx-i[0]))
               
                an2=img.angle*math.pi/180.0
               
                strx = cx - di*math.cos(an+an2) + img.offset[0]
                stry = cy - di*math.sin(an+an2) + img.offset[1]
               
                if self.progressWasCanceled():
                    return False 
               
                try:
                    adu_val, adu_delta = utils.getStarMagnitudeADU(r,strx,stry,i[3],i[4],i[5])
                except Exception as exc:
                    utils.showErrorMsgBox(str(exc))
                    self.unlock()
                    return False
                   
               
                self.lightcurve[i[6]][i[2]]['data'].append(adu_val)
                self.lightcurve[i[6]][i[2]]['error'].append(adu_delta)

            self.wnd.aduLabel.repaint()
        

        #converting to ndarray
        for i in  self.lightcurve[False]:
            self.lightcurve[False][i]['data']=np.array(self.lightcurve[False][i]['data'],dtype=self.ftype)
            self.lightcurve[False][i]['error']=np.array(self.lightcurve[False][i]['error'],dtype=self.ftype)
        
        for i in  self.lightcurve[True]:
            self.lightcurve[True][i]['data']=np.array(self.lightcurve[True][i]['data'],dtype=self.ftype)
            self.lightcurve[True][i]['error']=np.array(self.lightcurve[True][i]['error'],dtype=self.ftype)
        
        self.wnd.saveADUChartPushButton.setEnabled(True)

        self.progress.setMaximum(len(self.lightcurve))
        
        count=0
        #now reference star will be used to compute the actual magnitude
        if len(self.lightcurve[True]) > 0:
            for i in  self.lightcurve[False]:
                
                star=self.lightcurve[False][i]
                magref=[]
                magerr=[]
                
                if (len(star['data'].shape)==2):
                    
                    bb=star['data'][:,2]
                    vv=star['data'][:,1]
                    
                    star_bv_index=-2.5*np.log10(bb/vv)
                    
                    star_bv_error=[]
                    
                    if len(star['error'])>0:
                        bd=star['error'][:,2]
                        vd=star['error'][:,1]
                        star_bv_error=2.5*(np.abs(bd/bb)+abs(vd/vv))
                        
                    star_bv_error=np.array(star_bv_error)
                    
                    self.lightcurve['magnitudes'][i+'(B-V)']={'data':star_bv_index, 'error':star_bv_error}
                    self.addLightCurveListElement(str(i+'(B-V)'),str(i+'(B-V)'),self.wnd.magListWidget,'magnitudes',count)
                    count+=1
                
                self.lightcurve['magnitudes'][i]={}
                
                for j in  self.lightcurve[True]:
                    ref = self.lightcurve[True][j]
                    if (len(star['data'].shape)==2) and (len(ref['data'].shape)==2):
                        
                        rbb=ref['data'][:,2]
                        rvv=ref['data'][:,1]
                        
                        ref_bv_index=-2.5*np.log10(rbb/rvv)                                                
                        ref_bv_error=[]
                        
                        if len(ref['error'])>0:
                            rbd=ref['error'][:,2]
                            rvd=ref['error'][:,1]
                            ref_bv_error=2.5*(np.abs(rbd/rbb)+abs(rvd/rvv))
                                
                        ref_bv_error=np.array(ref_bv_error)
                        
                        color_dif=0.1*(star_bv_index-ref_bv_index)
                        color_err=0.1*(star_bv_error+ref_bv_error)
                        
                        strval=star['data'].sum(1)
                        refval=ref['data'].sum(1)
                        
                        strerr=star['error'].sum(1)
                        referr=ref['error'].sum(1)
                        
                        magref.append(ref['magnitude']-2.5*np.log10(strval/refval)-color_dif)
                        magerr.append(2.5*(np.abs(strerr/strval)+abs(referr/refval))+color_err)
                    else:
                        
                        strval=star['data']
                        refval=ref['data']
                        
                        strerr=star['error']
                        referr=ref['error']
                        
                        magref.append(ref['magnitude']-2.5*np.log10(star['data']/ref['data']))
                        magerr.append(2.5*(np.abs(strerr/strval)+abs(referr/refval)))
                
                self.lightcurve['magnitudes'][i]['data']=np.array(magref).mean(0)
                self.lightcurve['magnitudes'][i]['error']=np.array(magerr).mean(0)
                self.addLightCurveListElement(str(i),str(i),self.wnd.magListWidget,'magnitudes',count,checked=True)
                count+=1

        self.fillNumericData()

        self.wnd.saveMagChartPushButton.setEnabled(True)
        self.wnd.chartsTabWidget.setTabEnabled(1,True)
        self.wnd.chartsTabWidget.setTabEnabled(2,True)
    
        self.unlock()
        
    
    def fillNumericData(self):
        
        n1 = len(self.lightcurve[False])
        n2 = len(self.lightcurve[True])
        n3 = len(self.lightcurve['magnitudes'])
        
        
        shape=self.lightcurve[False].values()[0]['data'].shape

        if len(shape)==2:
            ncomp = shape[1]
        else:
            ncomp = 1
        
        tot_cols = 2+(n1+n2)*ncomp+n3
            
        tot_rows = len(self.lightcurve['time'])
        
        hdr_lbls=['index','date']
        
        self.wnd.numDataTableWidget.clear()
        self.wnd.numDataTableWidget.setSortingEnabled(False)
        self.wnd.numDataTableWidget.setColumnCount(tot_cols)
        self.wnd.numDataTableWidget.setRowCount(tot_rows)
        
        row_count = 0
        for i in self.lightcurve['time']:
            idx_item=Qt.QTableWidgetItem('{0:04d}'.format(row_count+1))
            dte_item=Qt.QTableWidgetItem(str(i))
            self.wnd.numDataTableWidget.setItem(row_count,0,idx_item)
            self.wnd.numDataTableWidget.setItem(row_count,1,dte_item)
            row_count+=1
        
        col_count = 2
        for i in self.lightcurve[False]:
            if ncomp > 1:
                if ncomp==3:
                    hdr_lbls.append(str(i)+'-I (ADU)')
                    hdr_lbls.append(str(i)+'-V (ADU)')
                    hdr_lbls.append(str(i)+'-B (ADU)')
                else:
                    for c in xrange(ncomp):
                        hdr_lbls.append(str(i)+'-'+str(c)+' (ADU)')
                row_count=0
                for vl in self.lightcurve[False][i]['data']:
                    for v in vl:
                        val_item=Qt.QTableWidgetItem(str(v))
                        self.wnd.numDataTableWidget.setItem(row_count,col_count,val_item)
                        col_count+=1
                    col_count-=ncomp
                    row_count+=1
            else:
                hdr_lbls.append(str(i)+' (ADU)')
                row_count=0
                for v in self.lightcurve[False][i]['data']:
                    val_item=Qt.QTableWidgetItem(str(v))
                    self.wnd.numDataTableWidget.setItem(row_count,col_count,val_item)
                    row_count+=1
            col_count+=ncomp
            
        for i in self.lightcurve[True]:
            if ncomp > 1:
                if ncomp==3:
                    hdr_lbls.append(str(i)+'-I (ADU)')
                    hdr_lbls.append(str(i)+'-V (ADU)')
                    hdr_lbls.append(str(i)+'-B (ADU)')
                else:
                    for c in xrange(ncomp):
                        hdr_lbls.append(str(i)+'-'+str(c)+' (ADU)')
                row_count=0
                for vl in self.lightcurve[True][i]['data']:
                    for v in vl:
                        val_item=Qt.QTableWidgetItem(str(v))
                        self.wnd.numDataTableWidget.setItem(row_count,col_count,val_item)
                        col_count+=1
                    col_count-=ncomp
                    row_count+=1
            else:
                hdr_lbls.append(str(i)+' (ADU)')
                row_count=0
                for v in self.lightcurve[True][i]['data']:
                    val_item=Qt.QTableWidgetItem(str(v))
                    self.wnd.numDataTableWidget.setItem(row_count,col_count,val_item)
                    row_count+=1
            col_count+=ncomp
  
        for i in self.lightcurve['magnitudes']:
            hdr_lbls.append(str(i)+' (Mag)')
            row_count=0
            for v in self.lightcurve['magnitudes'][i]['data']:
                val_item=Qt.QTableWidgetItem(str(v))
                self.wnd.numDataTableWidget.setItem(row_count,col_count,val_item)
                row_count+=1
            col_count+=1
                    
        self.wnd.numDataTableWidget.setHorizontalHeaderLabels(hdr_lbls)
        self.wnd.numDataTableWidget.setSortingEnabled(True)
    
    def exportNumericDataCSV(self, val):
        file_name = str(Qt.QFileDialog.getSaveFileName(self.wnd, tr("Save the project"),
                                                os.path.join(self.current_dir,'lightcurves.csv'),
                                                "CSV *.csv (*.csv);;All files (*.*)",None,
                                                utils.DIALOG_OPTIONS))
        utils.exportTableCSV(self, self.wnd.numDataTableWidget, file_name, sep='\t', newl='\n')
        
    def addLightCurveListElement(self,name,obj_name,widget,index,points,smoothing=8,checked=False,component=0):
        q=Qt.QListWidgetItem(name,widget)
        q.setCheckState(2*checked)
        q.listindex=(index,obj_name,component)
        q.chart_properties={'color':self.getChartColor(component),
                            'line': False,
                            'points': self.getChartPoint(points),
                            'bars':'|',
                            'smoothing':smoothing,
                            'point_size':2,
                            'line_width':1}
    
    def progressWasCanceled(self):
        QtGui.QApplication.instance().processEvents()

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
        destdir = str(Qt.QFileDialog.getExistingDirectory(self.wnd,
                                                          tr("Choose the output folder"),
                                                          self.current_dir,
                                                          utils.DIALOG_OPTIONS | Qt.QFileDialog.ShowDirsOnly ))
        self.save_dlg.lineEditDestDir.setText(str(destdir))
        
        
    
    def saveVideo(self):
        
        file_name = str(Qt.QFileDialog.getSaveFileName(self.wnd, tr("Save the project"),
                                                       os.path.join(self.current_dir,'Untitled.avi'),
                                                       "Video *.avi (*.avi);;All files (*.*)",None,
                                                       utils.DIALOG_OPTIONS))
        
        if file_name.replace(' ','') == '':
            log.log(repr(self),'no video file selected for output',level=logging.ERROR)
            return False
        
        
        self.video_dlg.exec_()
        
        cidx = self.video_dlg.codecComboBox.currentIndex()
        custom_size = (self.video_dlg.fullFrameCheckBox.checkState()==0)
        fps=self.video_dlg.fpsSpinBox.value()
        size=(self.currentWidth,self.currentHeight)
        fitlvl=(self.video_dlg.fitVideoCheckBox.checkState()==2)
        
        fh = self.video_dlg.resSpinBox.value()
        
        if cidx==0:
            fcc_str='DIVX'
            max_res=(4920,4920)
        elif cidx==0:
            fcc_str='MJPG'
            max_res=(9840,9840)
        elif cidx==0:
            fcc_str='U263'
            max_res=(2048,1024)
                    
        if not custom_size:
            size=(self.currentWidth,self.currentHeight)    
        else:
            fzoom=float(fh)/float(self.currentHeight)
            fw=int(self.currentWidth*fzoom)
            size=(fw,fh)
        
        try:
            vw=cv2.VideoWriter(file_name,cv2.cv.CV_FOURCC(*fcc_str),fps,size)
        except Exception as exc:
            estr=str(exc)
            if ('doesn\'t support this codec' in estr):
                
                utils.showErrorMsgBox(tr("Cannot create the video file."),
                                      tr("Try to use a lower resolution and assure you\nhave the permissions to write the file."))                
        
        log.log(repr(self),'writing video to: \"'+file_name+'\"',level=logging.INFO)
        log.log(repr(self),' FPS : ' + str(fps),level=logging.DEBUG)
        log.log(repr(self),' FOURCC : ' + fcc_str,level=logging.DEBUG)
        log.log(repr(self),' FRAME SIZE : ' + str(size),level=logging.DEBUG)
        
        
        
        if vw.isOpened():
            self.lock(False)
            self.progress.setMaximum(len(self.framelist))
            count=0
            self.statusBar.showMessage(tr('Writing video, please wait...'))
            
            
            for frm in self.framelist:
                count+=1
                QtGui.QApplication.instance().processEvents()
                self.progress.setValue(count)
                if frm.isUsed():
                    
                    log.log(repr(self),'using frame '+str(frm.name),level=logging.INFO)
                    log.log(repr(self),'loading data...',level=logging.DEBUG)
                    
                    img = self.debayerize(frm.getData(asarray=True, asuint8=True, fit_levels=fitlvl)).astype(np.uint8)
                    
                    _rgb = (len(img.shape) == 3)
                    
                    if self.video_dlg.useAligedCheckBox.checkState()==2:
                        img = self.registerImages(frm,img)
                    
                    if custom_size:
                        log.log(repr(self),'resizing image to ' + str(size),level=logging.DEBUG)
                        if _rgb:
                            img = sp.ndimage.interpolation.zoom(img,(fzoom,fzoom,1),order=self.interpolation_order)
                        else:
                            img = sp.ndimage.interpolation.zoom(img,(fzoom,fzoom),order=self.interpolation_order)
                    
                    if _rgb:
                        cv2img = np.empty_like(img)
                        log.log(repr(self),' converting to BRG format...',level=logging.DEBUG)
                        cv2img[...,0]=img[...,2]
                        cv2img[...,1]=img[...,1]
                        cv2img[...,2]=img[...,0]
                    else:
                        log.log(repr(self),' converting to BRG format...',level=logging.DEBUG)
                        img = utils.getColormappedImage(img,self.current_colormap,fitlvl)
                        cv2img = np.empty((size[1],size[0],3),dtype=np.uint8)
                        cv2img[...,0]=img[2]
                        cv2img[...,1]=img[1]
                        cv2img[...,2]=img[0]
                            
                    log.log(repr(self),' pushing frame...',level=logging.DEBUG)
                    
                    vw.write(cv2img)
                    
                    del cv2img
                    
                else:
                    log.log(repr(self),'\nskipping frame '+str(frm.name),level=logging.INFO)
                    
            vw.release()
            self.unlock()
            self.statusBar.showMessage(tr('DONE'))
            log.log(repr(self),'DONE',level=logging.INFO)
            
        else:
            utils.showErrorMsgBox('\nCannot open destination file')
    
    def doSaveResult(self, clicked):
        return self.saveResult()

    def saveResult(self):
        self.updateSaveOptions()
        if self.save_dlg.exec_() != 1:
            return False
        destdir=str(self.save_dlg.lineEditDestDir.text())
        
        while not os.path.isdir(destdir):
            utils.showWarningMsgBox(tr("The selected output folder is not a directory\nor it does not exist!"))
            if self.save_dlg.exec_() != 1:
                return False
            destdir=str(self.save_dlg.lineEditDestDir.text())

        self.lock()
        QtGui.QApplication.instance().processEvents()
        name=str(self.save_dlg.lineEditFileName.text())
        
        flags=None
        
        if self.save_dlg.radioButtonJpeg.isChecked():
            frmat='jpg'
            flags=(cv2.cv.CV_IMWRITE_JPEG_QUALITY,int(self.save_dlg.spinBoxIQ.value()))
        elif self.save_dlg.radioButtonPng.isChecked():
            frmat='png'
            flags=(cv2.cv.CV_IMWRITE_PNG_COMPRESSION,int(self.save_dlg.spinBoxIC.value()))
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
        
        if self.save_dlg.radioButtonInt.isChecked():
            if self.save_dlg.checkBoxUnsigned.checkState()==2:
                dtype='uint'
            else:
                dtype='int'
        elif self.save_dlg.radioButtonFloat.isChecked():
            dtype='float'
        
        common_args={"force_overwrite":False,
                     "filename":None,
                     "save_dlg":False,
                     "frmat":frmat,
                     "bits":bits,
                     "dtype":dtype,
                     "flags":flags,
                     "rgb_fits_mode":(self.save_dlg.rgbFitsCheckBox.checkState()==2),
                     "fits_compressed":(self.save_dlg.comprFitsCheckBox.checkState()==2)}
        
        stk_frm = utils.Frame(os.path.join(destdir,name+"."+frmat))
        stk_frm.saveData(data=self._stk,**common_args)
        
        if self.save_dlg.saveMastersCheckBox.checkState()==2:
            if (self._bas is not None):
                bas_frm = utils.Frame(os.path.join(destdir,name+"-master-bias."+frmat))
                bas_frm.saveData(data=self._bas,**common_args)
                
            if (self._drk is not None):
                drk_frm = utils.Frame(os.path.join(destdir,name+"-master-dark."+frmat))
                drk_frm.saveData(data=self._flf,**common_args)
                
            if (self._flt is not None):
                flt_frm = utils.Frame(os.path.join(destdir,name+"-master-flat."+frmat))
                flt_frm.saveData(data=self._flf,**common_args)
        
        self.unlock()
        
    #TODO: move all save functions to Frame class
    #TODO: add save support for all images and colormaps
    def _save_fits(self,destdir, name, bits):

        rgb_mode = (self.save_dlg.rgbFitsCheckBox.checkState()==2)
        fits_compressed = (self.save_dlg.comprFitsCheckBox.checkState()==2)
        
        avg_name=os.path.join(destdir,name)
        frm = utils.Frame(avg_name)
        
        try:
            frm._imwrite_fits_(self._stk,rgb_mode,compressed=fits_compressed,outbits=bits)
        except:
            frm._imwrite_fits_(self._stk,rgb_mode,compressed=False,outbits=bits)
            utils.showWarningMsgBox(tr("Cannot save compressed files with this version of pyfits")+":\n "+ tr("the image was saved as an uncompressed FITS file."))
            
        if self.save_dlg.saveMastersCheckBox.checkState()==2:
            if (self._bas is not None):
                bas_name=os.path.join(destdir,name+"-master-bias")
                frm = utils.Frame(bas_name)
                try:
                    frm._imwrite_fits_(self._bas,rgb_mode,compressed=fits_compressed,outbits=bits)
                except:
                    frm._imwrite_fits_(self._bas,rgb_mode,compressed=False,outbits=bits)
            if (self._drk is not None):
                drk_name=os.path.join(destdir,name+"-master-dark")
                frm = utils.Frame(drk_name)
                try:
                    frm._imwrite_fits_(self._drk,rgb_mode,compressed=fits_compressed,outbits=bits)
                except:
                    frm._imwrite_fits_(self._drk,rgb_mode,compressed=False,outbits=bits)
            if (self._flt is not None):
                flt_name=os.path.join(destdir,name+"-master-flat")
                frm = utils.Frame(flt_name)
                try:
                    frm._imwrite_fits_(self._flt,rgb_mode,compressed=fits_compressed,outbits=bits)
                except:
                    frm._imwrite_fits_(self._flt,rgb_mode,compressed=False,outbits=bits)
        del frm
        
    def _save_numpy(self,destdir, name, bits):

        if bits==32:
            outbits=np.float32
        elif bits==64:
            outbits=np.float64
        
        avg_name=os.path.join(destdir,name)
        np.save(avg_name,self._stk.astype(outbits))
        
        if self.save_dlg.saveMastersCheckBox.checkState()==2:
            if (self._bas is not None):
                bas_name=os.path.join(destdir,name+"-master-bias")
                np.save(bas_name,self._bas.astype(outbits))
                
            if (self._drk is not None):
                drk_name=os.path.join(destdir,name+"-master-dark")
                np.save(drk_name,self._drk.astype(outbits))
            
            if (self._flt is not None):
                flt_name=os.path.join(destdir,name+"-master-flat")
                np.save(flt_name,self._flt.astype(outbits))
    
    def _save_cv2(self,destdir, name, frmt, bits):
               
        if bits==8:
            rawavg=utils.normToUint8(self._stk, False)
            rawbas=utils.normToUint8(self._bas, False)
            rawdrk=utils.normToUint8(self._drk, False)
            rawflt=utils.normToUint8(self._flt, False)
        elif bits==16:
            rawavg=utils.normToUint16(self._stk, False)
            rawbas=utils.normToUint16(self._bas, False)
            rawdrk=utils.normToUint16(self._drk, False)
            rawflt=utils.normToUint16(self._flt, False)
        else:
            #this should never be executed!
            utils.showErrorMsgBox(tr("Cannot save image:"),tr("Unsupported format ")+str(bits)+"-bit "+tr("for")+" "+str(frmt))
            return False
                
        avg_name=os.path.join(destdir,name+"."+frmt)
        
        if frmt=='jpg':
            flags=(cv2.cv.CV_IMWRITE_JPEG_QUALITY,int(self.save_dlg.spinBoxIQ.value()))
        elif frmt=='png':
            flags=(cv2.cv.CV_IMWRITE_PNG_COMPRESSION,int(self.save_dlg.spinBoxIC.value()))
        else:
            flags=None
        
        frm = utils.Frame(avg_name)
        
        if not frm._imwrite_cv2_(rawavg,flags):
            return False
        
        
        if self.save_dlg.saveMastersCheckBox.checkState()==2:
            if (self._bas is not None):
                bas_name=os.path.join(destdir,name+"-master-bias."+frmt)
                frm = utils.Frame(bas_name)
                frm._imwrite_cv2_(rawbas,flags)
                
            if (self._drk is not None):
                drk_name=os.path.join(destdir,name+"-master-dark."+frmt)
                frm = utils.Frame(drk_name)
                frm._imwrite_cv2_(rawdrk,flags)
            
            if (self._flt is not None):
                flt_name=os.path.join(destdir,name+"-master-flat."+frmt)
                frm = utils.Frame(flt_name)
                frm._imwrite_cv2_(rawflt,flags)

        del frm

        