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
import utils
import colormaps
import numpy as np
import time
from PyQt4 import Qt, QtCore, QtGui, uic
import os
import paths
import logging
import log

COMPONENTS_NAME=['L','R','G','B','A']

def getComponentTable(ncomps,named=True):
    component_table={}
    if named and (ncomps+1 < len(COMPONENTS_NAME)):
        if ncomps == 1:
            component_table[0]=COMPONENTS_NAME[0]
        elif ncomps == 2:
            component_table[0]=COMPONENTS_NAME[0]
            component_table[1]=COMPONENTS_NAME[4]
        elif ncomps >= 3:
            for c in xrange(ncomps):
                component_table[c]=COMPONENTS_NAME[c+1]
    else:
        for c in xrange(ncomps):
            component_table[c]=COMPONENTS_NAME['C'+str(c)]
    return component_table
        

class MappedImage(QtCore.QObject):
    
    remapped = QtCore.pyqtSignal()
    
    def __init__(self,data=None,cmap=colormaps.gray,fit_levels=False,levels_range=(0,100),name=''):
        QtCore.QObject.__init__(self)
        self._original_data=None
        self._colormap=cmap
        self._mapped_qimage=None
        self._fit_levels=fit_levels
        self._levels_range=levels_range      
        self.component_table={}
        self.component_ctrl_table={}
        
        self.setName(name)
        
        self.levelfunc_idx=0
        self._ignore_histogrham_update = False #this will be used to avoid recursion loop
        self.__updating_mwb_ctrls=False #this will be used to avoid recursion loop
        
        self._hst=None
        
        self.MWB_CORRECTION_FACTORS={}
        
        self.levels_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'levels_dialog.ui'))   
        
        # paint callback for histoGraphicsView
        self.levels_dlg.histoView.__paintEvent__= self.levels_dlg.histoView.paintEvent #base implementation
        self.levels_dlg.histoView.paintEvent = self.histoViewPaintEvent #new callback        

        self.levels_dlg.curveTypeComboBox.currentIndexChanged.connect(self.updateHistograhm)
        self.levels_dlg.aDoubleSpinBox.valueChanged.connect(self.updateHistograhm2)
        self.levels_dlg.bDoubleSpinBox.valueChanged.connect(self.updateHistograhm2)
        self.levels_dlg.oDoubleSpinBox.valueChanged.connect(self.updateHistograhm2)
        self.levels_dlg.nDoubleSpinBox.valueChanged.connect(self.updateHistograhm2)
        self.levels_dlg.mDoubleSpinBox.valueChanged.connect(self.updateHistograhm2)
        self.levels_dlg.dataClippingGroupBox.toggled.connect(self.updateHistograhm2)
        self.levels_dlg.dataClipping8BitRadioButton.toggled.connect(self.updateHistograhm2)
        self.levels_dlg.dataClippingFitDataRadioButton.toggled.connect(self.updateHistograhm2)
        self.levels_dlg.MWBGroupBox.toggled.connect(self.updateHistograhm2)
        self.levels_dlg.histLogViewCheckBox.stateChanged.connect(self.updateHistograhm2)
        self.levels_dlg.buttonBox.clicked.connect(self.levelsDialogButtonBoxClickedEvent)
        
        self.updateCurveData()
        if data is not None:
            self.setData(data)
        
    def __del__(self):
        del self._mapped_qimage
        del self._original_data
    
    def setName(self,name):
        self._name=str(name).strip()
        if self._name!='':
            self._logname="mappedimage.MappedImage["+str(self._name)+"]"
        else:
            self._logname="mappedimage.MappedImage"
            
    def getLevelsDialog(self):
        return self.levels_dlg
    
    def componentsCount(self):
        if self._original_data is None:
            return 0
        else:
            if len(self._original_data.shape) == 2:
                self.component_table[0]='L'
                return 1
            elif len(self._original_data.shape) < 2:
                return -1
            else:                
                return self._original_data.shape[2]
    
    def getNumberOfComponents(self):
        return len(self.component_table)
    
    def getComponentName(self,index):
        return self.component_table[index]
                
    def getOriginalData(self):
        return self._original_data
    
    def getColormap(self):
        return self._colormap
    
    def setColormap(self,cmap,update=False):
        self._colormap=cmap
        if update:
            return self.remap()
    
    def setData(self,data, update=True):
        
        if data is None:
            self._original_data=None
            self._hst=None
            self._original_hst=None
            return
        else:
            self._original_data=data.astype(np.float32) # 1% of computation time
        
        if len(self.component_table) != self.componentsCount():  # 0% of computation time
            self.component_table=getComponentTable(self.componentsCount(),named=True)
            
            self.MWB_CORRECTION_FACTORS={}
            for name in self.component_table.values():
                self.MWB_CORRECTION_FACTORS[name]=[0,0.5,1]
            
            self.rebuildMWBControls()
            
            self.backUpLevels()
            
        self._hst=utils.generateHistograhms(self._original_data,128) #TODO:make a user's control? # 65%|55% of computation time
        self._original_hst=self._hst.copy() # 0% of computation time
        
        if self.levels_dlg.isVisible():
            self.updateHistograhm2() # 0%|17% of computation time
        
        if update:
            return self.remap() # 34%|27% of computation time
    
    def getOutputLevels(self):
        return (self._levels_range,self._fit_levels)
    
    def setOutputLevels(self, lrange=None, lfitting=None, update=False):
        if lrange is not None:
            self._levels_range=lrange
        if lfitting is not None:
            self._fit_levels=lfitting
        if update:
            return self.remap()
    
    def getMappedData(self):
        if self._original_data is None:
            return None
        elif (self._original_data.ndim==2 and
              self._colormap is not colormaps.gray):
            mapped_data = self._colormap.mapData(self.getData(),self._fit_levels,self._levels_range)
            arr=np.empty((self._original_data.shape[0],self._original_data.shape[1],3),dtype=np.float)
            arr[...,0] = mapped_data[0]
            arr[...,1] = mapped_data[1]
            arr[...,2] = mapped_data[2]
            return arr
        else:
            return self.getData()
    
    def remap(self):
        if self._original_data is not None:
            self._mapped_qimage = arrayToQImage(self.getData(),
                                                cmap = self._colormap,
                                                fit_levels=self._fit_levels,
                                                levels_range=self._levels_range)
            log.log(self._logname,"Remapping data...",level=logging.DEBUG)
        self.remapped.emit()
        return self._mapped_qimage
    
    def getQImage(self):
        return self._mapped_qimage


    def levelsDialogButtonBoxClickedEvent(self, button):
        pushed = self.levels_dlg.buttonBox.standardButton(button)
        
        if pushed == self.levels_dlg.buttonBox.Reset:
            self.levels_dlg.dataClippingGroupBox.setChecked(False)
            self.resetLevels()
        elif pushed == self.levels_dlg.buttonBox.Close:
            self.backUpLevels()
        elif pushed == self.levels_dlg.buttonBox.Apply:
            self.backUpLevels()
        elif pushed == self.levels_dlg.buttonBox.Discard:
            self.discardLevels()
            
        self.remap()
            
            
    def resetLevels(self):
        self.levels_dlg.curveTypeComboBox.setCurrentIndex(0)
        self.levels_dlg.aDoubleSpinBox.setValue(0)
        self.levels_dlg.bDoubleSpinBox.setValue(1)
        self.levels_dlg.oDoubleSpinBox.setValue(1)
        self.levels_dlg.mDoubleSpinBox.setValue(1)
        self.levels_dlg.nDoubleSpinBox.setValue(np.e)
        for name in self.MWB_CORRECTION_FACTORS:
            self.MWB_CORRECTION_FACTORS[name]=[0,0.5,1]
        self.updateMWBControls()
        self.updateHistograhm2()

    def discardLevels(self):
        self.levels_dlg.curveTypeComboBox.setCurrentIndex(self._old_funcidx)
        self.levels_dlg.aDoubleSpinBox.setValue(self._old_a)
        self.levels_dlg.bDoubleSpinBox.setValue(self._old_b)
        self.levels_dlg.oDoubleSpinBox.setValue(self._old_o)
        self.levels_dlg.mDoubleSpinBox.setValue(self._old_m)
        self.levels_dlg.nDoubleSpinBox.setValue(self._old_n)
        self.MWB_CORRECTION_FACTORS = self._old_mwb
        self.updateHistograhm2()
        self.updateMWBControls()
        
    def backUpLevels(self):
        self._old_funcidx = self.levels_dlg.curveTypeComboBox.currentIndex()
        self._old_a = float(self.levels_dlg.aDoubleSpinBox.value())
        self._old_b = float(self.levels_dlg.bDoubleSpinBox.value())
        self._old_o = float(self.levels_dlg.oDoubleSpinBox.value())
        self._old_m = float(self.levels_dlg.mDoubleSpinBox.value())
        self._old_n = float(self.levels_dlg.nDoubleSpinBox.value())
        self._old_mwb = self.MWB_CORRECTION_FACTORS.copy()
        
    def histoViewPaintEvent(self, obj):
        
        painter = Qt.QPainter(self.levels_dlg.histoView)
        
        xmin,xmax = self.getLevelsClippingRange()
        
        painter.setBrush(QtCore.Qt.white)
        painter.drawRect(painter.window())
        
        utils.drawHistograhm(painter, self._hst, xmin, xmax, logY=self.levels_dlg.histLogViewCheckBox.checkState())
    
    def signalMWBSlider(self, *arg, **args):
        if not self.__updating_mwb_ctrls:
            self.__updating_mwb_ctrls=True
            for name in self.component_ctrl_table:
                
                c_l_dsb=self.component_ctrl_table[name][1]
                c_l_sld=self.component_ctrl_table[name][0]
                c_m_dsb=self.component_ctrl_table[name][3]
                c_m_sld=self.component_ctrl_table[name][2]
                c_h_dsb=self.component_ctrl_table[name][5]
                c_h_sld=self.component_ctrl_table[name][4]
                
                new_l_val=c_l_sld.value()/10000.0
                new_m_val=c_m_sld.value()/10000.0
                new_h_val=c_h_sld.value()/10000.0
                
                c_l_dsb.setValue(new_l_val)
                c_m_dsb.setValue(new_m_val)
                c_h_dsb.setValue(new_h_val)
                
                self.MWB_CORRECTION_FACTORS[name]=[new_l_val,new_m_val,new_h_val]
            self.updateMWBCorrectionFactors()
            self.updateHistograhm2()
            self.__updating_mwb_ctrls=False
            
    def signalMWBSpinBox(self, *arg, **args):
        if not self.__updating_mwb_ctrls:
            self.__updating_mwb_ctrls=True
            for name in self.component_ctrl_table:
                
                c_l_dsb=self.component_ctrl_table[name][1]
                c_l_sld=self.component_ctrl_table[name][0]
                c_m_dsb=self.component_ctrl_table[name][3]
                c_m_sld=self.component_ctrl_table[name][2]
                c_h_dsb=self.component_ctrl_table[name][5]
                c_h_sld=self.component_ctrl_table[name][4]
                
                new_l_val=c_l_dsb.value()
                new_m_val=c_m_dsb.value()
                new_h_val=c_h_dsb.value()
                
                c_l_sld.setValue(int(new_l_val*10000))
                c_m_sld.setValue(int(new_m_val*10000))
                c_h_sld.setValue(int(new_h_val*10000))
                
                self.MWB_CORRECTION_FACTORS[name]=[new_l_val,new_m_val,new_h_val]
            self.updateMWBCorrectionFactors()
            self.updateHistograhm2()
            self.__updating_mwb_ctrls=False
    
    def updateMWBCorrectionFactors(self):
        
        hmax=0
        lmin=1
        
        for name in self.MWB_CORRECTION_FACTORS:
            
            l,m,h=self.MWB_CORRECTION_FACTORS[name]
            
            hmax=max(hmax,h)
            lmin=min(lmin,l)
            
            min_step=self.component_ctrl_table[name][1].singleStep()
            
            if (h - l)<=min_step:
                self.MWB_CORRECTION_FACTORS[name][0]=h-min_step
                self.MWB_CORRECTION_FACTORS[name][2]=l+min_step
        
        for name in self.MWB_CORRECTION_FACTORS:
            self.MWB_CORRECTION_FACTORS[name][0]-=lmin
            self.MWB_CORRECTION_FACTORS[name][2]+=(1-hmax)
            
        self.updateMWBControls()
    
    def getMWBCorrectionFactors(self):
        self.updateMWBCorrectionFactors()
        return (self.MWB_CORRECTION_FACTORS,bool(self.levels_dlg.MWBGroupBox.isChecked()))
    
    def setMWBCorrectionFactors(self,factors,manual=False,update=True):
        self.MWB_CORRECTION_FACTORS=factors
        self.levels_dlg.MWBGroupBox.setChecked(bool(manual))
        if update:
            self.updateMWBControls()
    
    def updateMWBControls(self):
        self.__updating_mwb_ctrls=True
        for name in self.MWB_CORRECTION_FACTORS:
            l,m,h=self.MWB_CORRECTION_FACTORS[name]
            
            c_l_dsb=self.component_ctrl_table[name][1]
            c_l_sld=self.component_ctrl_table[name][0]
            c_m_dsb=self.component_ctrl_table[name][3]
            c_m_sld=self.component_ctrl_table[name][2]
            c_h_dsb=self.component_ctrl_table[name][5]
            c_h_sld=self.component_ctrl_table[name][4]

            c_l_sld.setValue(int(l*10000))
            c_m_sld.setValue(int(m*10000))
            c_h_sld.setValue(int(h*10000))      
            c_l_dsb.setValue(l)
            c_m_dsb.setValue(m)
            c_h_dsb.setValue(h)

        self.__updating_mwb_ctrls=False
    
    def buildMWBControls(self):
        
        self.levels_dlg.MWBScrollArea.setLayout(QtGui.QGridLayout())
        
        idx = 0
        
        l_lbl=Qt.QLabel(utils.tr("shadows"))
        m_lbl=Qt.QLabel(utils.tr("middletones"))
        h_lbl=Qt.QLabel(utils.tr("lights"))
        
        self.levels_dlg.MWBScrollArea.layout().addWidget(l_lbl,0,1,1,2)
        self.levels_dlg.MWBScrollArea.layout().addWidget(h_lbl,0,3,1,2)
        self.levels_dlg.MWBScrollArea.layout().addWidget(m_lbl,0,5,1,2)
        
        l_lbl.setSizePolicy(Qt.QSizePolicy.Expanding,Qt.QSizePolicy.Minimum)
        m_lbl.setSizePolicy(Qt.QSizePolicy.Expanding,Qt.QSizePolicy.Minimum)
        h_lbl.setSizePolicy(Qt.QSizePolicy.Expanding,Qt.QSizePolicy.Minimum)
        
        l_lbl.setAlignment(QtCore.Qt.AlignHCenter)
        m_lbl.setAlignment(QtCore.Qt.AlignHCenter)
        h_lbl.setAlignment(QtCore.Qt.AlignHCenter)
        
        for i in self.component_table:
            
            idx+=1    
            
            name = self.component_table[i]
            
            c_lbl=Qt.QLabel(str(name))
            
            c_l_sld=Qt.QDial()
            c_l_dsb=Qt.QDoubleSpinBox()
            c_m_sld=Qt.QDial()
            c_m_dsb=Qt.QDoubleSpinBox()
            c_h_sld=Qt.QDial()
            c_h_dsb=Qt.QDoubleSpinBox()
            
            c_l_dsb.setDecimals(4)
            c_m_dsb.setDecimals(4)
            c_h_dsb.setDecimals(4)
            
            c_l_sld.setSingleStep(1)
            c_l_dsb.setSingleStep(0.0001)
            c_m_sld.setSingleStep(1)
            c_m_dsb.setSingleStep(0.0001)
            c_h_sld.setSingleStep(1)
            c_h_dsb.setSingleStep(0.0001)
            
            c_l_sld.setMaximum(10000)
            c_l_dsb.setMaximum(1.0)
            c_m_sld.setMaximum(10000)
            c_m_dsb.setMaximum(1.0)
            c_h_sld.setMaximum(10000)
            c_h_dsb.setMaximum(1.0)
            
            c_l_sld.setMinimum(0)
            c_l_dsb.setMinimum(0)
            c_m_sld.setMinimum(0)
            c_m_dsb.setMinimum(0)
            c_h_sld.setMinimum(0)
            c_h_dsb.setMinimum(0)
            
            c_l_sld.setValue(int(self.MWB_CORRECTION_FACTORS[name][0]*10000))
            c_l_dsb.setValue(self.MWB_CORRECTION_FACTORS[name][0])
            c_m_sld.setValue(int(self.MWB_CORRECTION_FACTORS[name][1]*10000))
            c_m_dsb.setValue(self.MWB_CORRECTION_FACTORS[name][1])
            c_h_sld.setValue(int(self.MWB_CORRECTION_FACTORS[name][2]*10000))
            c_h_dsb.setValue(self.MWB_CORRECTION_FACTORS[name][2])
            
            c_l_sld.valueChanged.connect(self.signalMWBSlider)
            c_l_dsb.valueChanged.connect(self.signalMWBSpinBox)
            c_m_sld.valueChanged.connect(self.signalMWBSlider)
            c_m_dsb.valueChanged.connect(self.signalMWBSpinBox)
            c_h_sld.valueChanged.connect(self.signalMWBSlider)
            c_h_dsb.valueChanged.connect(self.signalMWBSpinBox)
            
            self.component_ctrl_table[name]=(c_l_sld,c_l_dsb,c_m_sld,c_m_dsb,c_h_sld,c_h_dsb)
            
            log.log(self._logname,"building controls for component "+str(name),level=logging.DEBUG)
            
            self.levels_dlg.MWBScrollArea.layout().addWidget(c_lbl,idx,0)
            self.levels_dlg.MWBScrollArea.layout().addWidget(c_l_sld,idx,1)
            self.levels_dlg.MWBScrollArea.layout().addWidget(c_l_dsb,idx,2)
            self.levels_dlg.MWBScrollArea.layout().addWidget(c_h_sld,idx,3)
            self.levels_dlg.MWBScrollArea.layout().addWidget(c_h_dsb,idx,4)
            self.levels_dlg.MWBScrollArea.layout().addWidget(c_m_sld,idx,5)
            self.levels_dlg.MWBScrollArea.layout().addWidget(c_m_dsb,idx,6)
            
            c_lbl.show()
            c_l_sld.show()
            c_l_dsb.show()
            c_m_sld.show()
            c_m_dsb.show()
            c_h_sld.show()
            c_h_dsb.show()
                                    
        log.log(self._logname,"DONE",level=logging.DEBUG)
    
    def clearMWBControls(self):
        log.log(self._logname,"clearing MWB controls...",level=logging.DEBUG)
        try:
            del self.component_ctrl_table
        except:
            pass
        
        self.component_ctrl_table={}
        
        if self.levels_dlg.MWBScrollArea.layout() is not None:
            Qt.QWidget().setLayout(self.levels_dlg.MWBScrollArea.layout())
    
    def rebuildMWBControls(self):
        self.clearMWBControls()
        self.buildMWBControls()
            
    def editLevels(self, clicked=True):
        
        if clicked:
            self.backUpLevels()
            self.rebuildMWBControls()            
            self.updateHistograhm2()
            self.levels_dlg.show()
        else:
            self.levels_dlg.hide()
            
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
    
    def updateCurveData(self):
        A = float(self.levels_dlg.aDoubleSpinBox.value())
        B = float(self.levels_dlg.bDoubleSpinBox.value())
        o = float(self.levels_dlg.oDoubleSpinBox.value())
        m = float(self.levels_dlg.mDoubleSpinBox.value())
        n = float(self.levels_dlg.nDoubleSpinBox.value())
        
        self._curve_data=(self.levelfunc_idx,A,B,o,m,n)
        
    def getCurve(self):
        return self._curve_data
    
    def setCurve(self,curve_id,A,B,o,m,n,update=True):
        self._ignore_histogrham_update = True
        
        self.levels_dlg.aDoubleSpinBox.setValue(float(A))
        self.levels_dlg.bDoubleSpinBox.setValue(float(B))
        self.levels_dlg.oDoubleSpinBox.setValue(float(o))
        self.levels_dlg.mDoubleSpinBox.setValue(float(m))
        self.levels_dlg.nDoubleSpinBox.setValue(float(n))
        self.levels_dlg.curveTypeComboBox.setCurrentIndex(curve_id)
        
        self._curve_data=(self.levelfunc_idx,A,B,o,m,n)
        
        self._ignore_histogrham_update = False
        
        if update:
            self.updateHistograhm2()
            
        self.backUpLevels()
        
    def getData(self):
        
        if self._original_data is None:
            return None
        
        A = self._curve_data[1]
        B = self._curve_data[2]
        o = self._curve_data[3]
        m = self._curve_data[4]
        n = self._curve_data[5]        
        
        #cf=[]
        
        #for i in self.component_table:
            #if self.levels_dlg.MWBGroupBox.isChecked():
                #cf.append(self.MWB_CORRECTION_FACTORS[self.component_table[i]])
            #else:
                #cf.append(1.0)
        
        if self.levels_dlg.MWBGroupBox.isChecked():
            data=utils.applyWhiteBalance(self._original_data,
                                         self.MWB_CORRECTION_FACTORS,
                                         self.component_table)
        else:
            data=self._original_data
        
        if self.levelfunc_idx == 0: #linear
            newdata = A+B*data
        elif self.levelfunc_idx == 1: #logarithmic
            newdata = A+B*np.emath.logn(n,(o+m*data))
        elif self.levelfunc_idx == 2: #power
            newdata = A+B*((o+m*data)**n)
        elif self.levelfunc_idx == 3: #exponential
            newdata = A+B*(n**(o+m*data))

        if self.levels_dlg.dataClippingGroupBox.isChecked():
            if self.levels_dlg.dataClipping8BitRadioButton.isChecked():
                data_max = 255
                data_min = 0
            elif self.levels_dlg.dataClipping16BitRadioButton.isChecked():
                data_max = 65535
                data_min = 0
                
            return newdata.clip(data_min,data_max)
        else:
            return newdata
    
    def updateHistograhm(self, curve_idx):
        
        if self._ignore_histogrham_update or (self._hst is None):
            return
        
        scenablied = self.levels_dlg.dataClippingGroupBox.isChecked()
        clipping   = scenablied and self.levels_dlg.dataClippingClipDataRadioButton.isChecked()
        streching  = scenablied and self.levels_dlg.dataClippingFitDataRadioButton.isChecked()
        
        self.levelfunc_idx=curve_idx
        
        self.updateCurveData()
        
        A = self._curve_data[1]
        B = self._curve_data[2]
        o = self._curve_data[3]
        m = self._curve_data[4]
        n = self._curve_data[5]
        
        data_min,data_max = self.getLevelsClippingRange()
        
        if streching:
            if curve_idx == 0: #linear
                tmphst=self._original_hst[0,1]
            elif curve_idx == 1: #logarithmic
                tmphst=np.emath.logn(n,(o+m*self._original_hst[0,1]))
            elif curve_idx == 2: #power
                tmphst=((o+m*self._original_hst[0,1])**n)
            elif curve_idx == 3: #exponential
                tmphst=(n**(o+m*self._original_hst[0,1]))
            
            minh = min(tmphst)
            maxh = max(tmphst)
            
            B = (data_max-data_min)/(maxh-minh)
            A = -(data_max-data_min)*minh/(maxh-minh)
            
            self._ignore_histogrham_update = True
            self.levels_dlg.aDoubleSpinBox.setValue(A)
            self.levels_dlg.bDoubleSpinBox.setValue(B)
            self._ignore_histogrham_update = False
    
        self._hst[0,0]=np.zeros_like(self._hst[0,0])
        
        if self.levels_dlg.MWBGroupBox.isChecked():
            _hst_wb=utils.applyHistWhiteBalance(self._original_hst,
                                                self.MWB_CORRECTION_FACTORS,
                                                self.component_table)
        else:
            _hst_wb=self._original_hst
        
        for i in range(len(self._hst)):
            
            if curve_idx == 0: #linear
                self._hst[i,1]=A+B*_hst_wb[i,1]
            elif curve_idx == 1: #logarithmic
                self._hst[i,1]=A+B*np.emath.logn(n,(o+m*_hst_wb[i,1]))
            elif curve_idx == 2: #power
                self._hst[i,1]=A+B*((o+m*_hst_wb[i,1])**n)
            elif curve_idx == 3: #exponential
                self._hst[i,1]=A+B*(n**(o+m*_hst_wb[i,1]))
            
            if i > 0:
                                        
                if clipping:
                    mask = (self._hst[i,1]>=data_min)*(self._hst[i,1]<=data_max)
                    self._hst[i,0]=_hst_wb[i,0]*mask[:-1]
                else:
                    self._hst[i,0]=_hst_wb[i,0]
                
                for j in range(len(self._hst[i,0])):
                    x = self._hst[i,1][j]
                    try:
                        k=np.argwhere(self._hst[0,1]>=x)[0,0]
                        x1=self._hst[0,1][k-1]
                        x2=self._hst[0,1][k]
                        
                        # x1 <= x < x2
                        
                        delta=x2-x1

                        self._hst[0,0][k-1]+=self._hst[i,0][j]*(x2-x)/delta
                        self._hst[0,0][k]+=self._hst[i,0][j]*(x-x1)/delta
                    except:
                        pass
    
        self.levels_dlg.update()
        #self.remap()
        
    def updateHistograhm2(self, *arg,**args):
        self.updateHistograhm(self.levelfunc_idx)
        




def arrayToQImage(img,R=0,G=1,B=2,A=3,cmap=colormaps.gray,fit_levels=False,levels_range=None):
    t1 = time.time()
    if img is None:
        return QtGui.QImage()
    elif type(img) != np.ndarray:
        raise TypeError('In module utils, in function arrayToQImage, ndarray expected as first argumrnt but '+str(type(img))+' given instead')
    
    #searching for NaN values
    if img.dtype.kind == 'f':
        tb=(img!=img).nonzero()
        img[tb]=np.Inf
        tb=(img==np.Inf).nonzero()
        img[tb]=img.min()
    
    if img.ndim ==2:
        h,w = img.shape[0:2]
        channels = 1
    else:
        h,w,channels = img.shape[0:3]
    
    #data must be 32bit aligned
    if (w%4) != 0:
        optimal_w = w + 4 - w%4
    else:
        optimal_w = w
        
    if (h%4) != 0:
        optimal_h = h + 4 - h%4
    else:
        optimal_h = h    
    
    if img.ndim==2:
        arr = 255*np.ones((optimal_h, optimal_w, 4), np.uint8, 'C')
        
        mapped=cmap.mapData(img,fit_levels,levels_range)
        arr[0:h,0:w,2] = mapped[0]
        arr[0:h,0:w,1] = mapped[1]
        arr[0:h,0:w,0] = mapped[2]
                
        arr[h:,0:,3] = 0
        arr[0:,w:,3] = 0
        
    elif (img.ndim==3) and (channels == 3):
        img2 = utils.normToUint8(img,fit_levels,levels_range) # 65% of computation time
        arr = 255*np.ones((optimal_h, optimal_w, 4), np.uint8, 'C') # 10% of computation time
        arr[0:h,0:w,0:3]=img2[...,(B,G,R)] # 25% of computation time
        arr[h:,0:,3] = 0  # 0% of computation time
        arr[0:,w:,3] = 0  # 0% of computation time
        
    elif (img.ndim==3) and (channels == 4):
        img2 = utils.normToUint8(img,fit_levels,levels_range)
        arr = 255*np.ones((optimal_h, optimal_w, 4), np.uint8, 'C')
        arr[0:h,0:w]=img2[...,(R,G,B,A)]
    else:
        return QtGui.QImage()
    
    arr=arr.astype('uint8')
    rawdata=arr.data
    del arr
    
    result = Qt.QImage(rawdata,optimal_w,optimal_h,Qt.QImage.Format_ARGB32_Premultiplied)
    result._raw_data=rawdata
    
    return result

    
    