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

from PyQt4 import Qt, QtCore, QtGui, uic
import sys
import os
import subprocess
import paths
import time
import math
import tempfile
import cPickle  
import logging
import log

PROGRAM = paths.PROGRAM_NAME
PROGRAM_NAME = paths.PROGRAM_NAME

FORMAT_BLACKLIST = ['BUFR', 'EPS', 'GRIB',
                    'HDF5', 'MPEG','WMF' ]

CUSTOM_EXTENSIONS = {'.fts':'FITS',
                     '.npy':'NPY',
                     '.npz':'NPZ',
                     '.avi':'VIDEO',
                     '.mp4':'VIDEO',
                     '.mpg':'VIDEO',
                     '.mpeg':'VIDEO'}

POINTS_TYPE=['','o','d','s','+','*']
LINES_TYPE=['','-','--','..','-.','-..']
BARS_TYPE=['','|']

LIGHT_FRAME_TYPE  = 'light frame'
BIAS_FRAME_TYPE   = 'bias frame'
DARK_FRAME_TYPE   = 'dark frame'
FLAT_FRAME_TYPE   = 'flatfield frame'

def tr(s):
    news=QtCore.QCoreApplication.translate('@default',s)
    #python3 return str...
    if type(news) == str:
        return news
    else:
        #... while python2 return QString 
        # that must be converted to str
        try:
            return str(news.toAscii())
        except:
            return str(news)

def showMsgBox(text,informative_text="",parent=None,buttons=Qt.QMessageBox.Ok,icon=None):
    msgBox = Qt.QMessageBox(parent)
    msgBox.setText(str(text))
    msgBox.setInformativeText(str(informative_text))
    msgBox.setStandardButtons(buttons)
    
    if icon is not None:
        msgBox.setIcon(icon)
        
    return msgBox.exec_()

def showYesNoMsgBox(text,informative_text="",parent=None):
    return showMsgBox(text,
                      informative_text,
                      parent,
                      Qt.QMessageBox.Yes | Qt.QMessageBox.No,
                      Qt.QMessageBox.Question)

def showYesNoCancelMsgBox(text,informative_text="",parent=None):
    return showMsgBox(text,
                      informative_text,
                      parent,
                      Qt.QMessageBox.Yes | Qt.QMessageBox.No | Qt.QMessageBox.Cancel,
                      Qt.QMessageBox.Question)

def showErrorMsgBox(text,informative_text="",parent=None):
    log.log("<lxnstack.utils module>","MessageBox: "+str(text)+": "+informative_text,level=logging.ERROR)
    return showMsgBox(tr("Error")+": "+str(text),
                      informative_text,
                      parent,
                      icon=Qt.QMessageBox.Critical)

def showWarningMsgBox(text,informative_text="",parent=None):
    log.log("<lxnstack.utils module>","MessageBox: "+str(text)+": "+informative_text,level=logging.WARN)
    return showMsgBox(tr("Warning")+": "+str(text),
                      informative_text,
                      parent,
                      icon=Qt.QMessageBox.Warning)
try:
    import numpy as np
except ImportError:
    log.log("<lxnstack.utils module>",'\'numpy\' python module not found! exiting program.',level=logging.ERROR)
    showErrorMsgBox(tr("\'numpy\' python module not found!"),tr("Please install numpy."))
    sys.exit(1)

try:
    import scipy as sp
    from scipy import signal, ndimage
except ImportError:
    log.log("<lxnstack.utils module>",'\'scipy\' python module not found! exiting program.',level=logging.ERROR)
    showErrorMsgBox(tr("\'scipy\' python module not found!"),tr("Please install scipy."))
    sys.exit(1)

try:
    import cv2
except ImportError:
    log.log("<lxnstack.utils module>",'\'opencv (cv2)\' python module not found! exiting program.',level=logging.ERROR)
    showErrorMsgBox(tr("\'opencv2\' python module not found!"),tr("Please install opencv2 python bindings."))
    sys.exit(1)



try:
    from PIL import Image, ExifTags
    Image.init()
except ImportError:
    log.log("<lxnstack.utils module>",'\'PIL\' python module not found! exiting program.',level=logging.ERROR)
    showErrorMsgBox(tr("\'PIL\' python module not found!"),tr("Please install the python imaging library (PIL/Pillow)."))
    sys.exit(1)

try:
    import astropy.io.fits as pyfits
    FITS_SUPPORT=True
    log.log("<lxnstack.utils module>","FITS support enabled",level=logging.INFO)
    
except ImportError:
    #if you have pyfits
    try:
        import pyfits
        FITS_SUPPORT=True
        log.log("<lxnstack.utils module>","FITS support enabled",level=logging.INFO)
        log.log("<lxnstack.utils module>","The pyFITS package will be soon fully replaced by 'astropy'!\nYou can find it at http://www.astropy.org/",level=logging.WARN)

    except ImportError:
        log.log("<lxnstack.utils module>","FITS support not enabled:\nto enable FITS support please install the 'astropy' python package!",level=logging.WARN)

        FITS_SUPPORT=False
        FORMAT_BLACKLIST.append('FITS')

if FITS_SUPPORT:

    std_fits_header=[('SWCREATE',str(paths.PROGRAM_NAME))]

    def getFitsStdHeader():
        try:
            return pyfits.header.Header(std_fits_header)
        except:
            #old pyfits package!
            head = pyfits.Header()
            for line in std_fits_header:
                head.update(line[0],line[1])
            return head

try:
    import cr2plugin
    CR2_SUPPORT=True
    log.log("<lxnstack.utils module>","CR2 support enabled",level=logging.INFO)
    for ext in cr2plugin.EXTENSION.keys():
        CUSTOM_EXTENSIONS[ext]=cr2plugin.EXTENSION[ext]
except Exception as exc:
    log.log("<lxnstack.utils module>","WARNING: CR2 support not enabled:\n"+str(exc),level=logging.WARNING)
    FORMAT_BLACKLIST.append('CR2')

# it seems that kde's native dialogs work correctly while, on the contrary,
# gnome's dialogs (and also dialogs of other desktop environmetns?) will not
# display correclty! In this case the Qt (non native) dialogs will be
# used.

try:
    #try automatic detection
    if 'kde' == os.environ['XDG_CURRENT_DESKTOP'].lower():
        DIALOG_OPTIONS = Qt.QFileDialog.Option(Qt.QFileDialog.HideNameFilterDetails)
    else:
       DIALOG_OPTIONS = Qt.QFileDialog.Option(Qt.QFileDialog.HideNameFilterDetails | Qt.QFileDialog.DontUseNativeDialog)
except Exception:
    # This should work in each Desktop Environment
    DIALOG_OPTIONS = Qt.QFileDialog.Option(Qt.QFileDialog.HideNameFilterDetails | Qt.QFileDialog.DontUseNativeDialog)


def genTimeUID():
    time.sleep(0.00001)
    baseid = "{0:016x}".format(int(time.time()*10000000))
    return baseid[0:4]+'-'+baseid[4:8]+'-'+baseid[8:12]+'-'+baseid[12:16]
    

def Int(val):
    i = math.floor(val)
    if ((val-i)<0.5):
        return int(i)
    else:
        return int(math.ceil(val))

def timeouted_loop(func, t_step=0.5, timeout=10, c_val=None, arg=(), args={}):
    timelimit = time.time() + timeout
    
    result=func(*arg,**args)
    if c_val in (True, False, None):
        while (result is not c_val) and (time.time()<timelimit):
            time.sleep(0.5)
            result=func(*arg,**args)
        return result is c_val
    else:
        while (result != c_val) and (time.time()<timelimit):
            time.sleep(0.5)
            result=func(*arg,**args)
        return result == c_val

def getCreationTime(url):
    # Some times I found files modified before their creation!
    return min(os.path.getctime(url),os.path.getmtime(url))

def getModificationTime(url):
    # Some times I found files modified before their creation!
    return max(os.path.getctime(url),os.path.getmtime(url))

def notUpdated(url1, url2):
    if os.path.exists(url1) and os.path.exists(url2):
        t1 = getModificationTime(url1)
        t2c = os.path.getctime(url2)
        t2m = os.path.getmtime(url2)
        return (t1 > t2m) or (t2m != t2c)
    else:
        return True

def _getCTime(v, sep=' '):
    tm_struct=[0]*9
    stm=v.strip('\x00\n\r').split(sep)
    
    dt = stm[0].split(':')  #the date is yyyy:mm:dd
    
    if len(dt)<3: #maybe it is yyyy-mm-dd
        dt = stm[0].split('-')
    
    if len(dt)<3: # the try to detect the separator
        dt = stm[0].split(stm[-3])
    
    if len(stm)==2:
        tm = stm[1].split(':')
        
        if len(tm)<3: # the try to detect the separator
            tm = stm[0].split(stm[-3])
            
        tm_struct[3]=int(tm[0])
        tm_struct[4]=int(tm[1])
        ff=float(tm[2])
        tm_struct[5]=int(ff)
    else:
        return None
    
    yy=int(dt[0])
    
    if dt[0]<100:
        tm_struct[0]=1990+yy
    else:
        tm_struct[0]=yy
    
    tm_struct[1]=int(dt[1])
    tm_struct[2]=int(dt[2])
    tm_struct[8]=-1
    return time.mktime(time.struct_time(tm_struct))+math.modf(ff)[0]

def getCurrentTimeMsec():
    return Qt.QDateTime.toMSecsSinceEpoch(Qt.QDateTime.currentDateTime())


def getQIcon(name="",verbose=False):
    
    if type(name) != str:
        name=str(name)
    
    if name=="":
        return QtGui.QIcon("")
    
    if QtGui.QIcon.hasThemeIcon(name):

        log.log("<lxnstack.utils module>","Found icon form Theme: \""+name+"\"",level=logging.DEBUG)
        return QtGui.QIcon.fromTheme(name)
    else:
        iconurl=os.path.join(paths.ICONS_PATH,name)
        
        if os.path.isfile(iconurl):
            log.log("<lxnstack.utils module>","Found icon: \""+name+"\"",level=logging.DEBUG)
            return QtGui.QIcon(iconurl)
        else:
            
            root_name = os.path.basename(os.path.splitext(name)[0])
                            
            for each_icon in os.listdir(paths.ICONS_PATH):
                
                new_name = os.path.splitext(each_icon)[0]
                
                if root_name == new_name:
                    log.log("<lxnstack.utils module>","Found default icon: \""+os.path.join(paths.ICONS_PATH,each_icon)+"\"",level=logging.DEBUG)
                    return QtGui.QIcon(os.path.join(paths.ICONS_PATH,each_icon))
                
            log.log("<lxnstack.utils module>","No icon found for: \""+name+"\"",level=logging.WARNING)
            return QtGui.QIcon("")
    
class Frame(Qt.QObject):
    
    """
    command for args**
    rgb_fits = True/False
    """
    
    titleChanged = QtCore.pyqtSignal(str)
    infoTextChanged = QtCore.pyqtSignal(str)
    progressValueChanged = QtCore.pyqtSignal(int)
    progressMaximumChanged = QtCore.pyqtSignal(int)
    hideProgress = QtCore.pyqtSignal()
    showProgress = QtCore.pyqtSignal()
    canceled = QtCore.pyqtSignal()
    
    def cancel(self):
        self.hideProgress.emit()
        self.canceled.emit()
    
    def __del__(self):
        log.log("lxnstack.utils.Fame","deleting Frame \'"+self.tool_name+"\'",level=logging.DEBUG)
    
    def __init__(self, file_name="", page=0, **args):
        Qt.QObject.__init__(self)
        self.setUrl(file_name, page)
        self.properties={}
        self.is_good=False
        self._open_args=args
        
        if (('progress_bar' in args) and args['progress_bar'] is not None):
            pb = args['progress_bar']
            self.progressValueChanged.connect(pb.setValue)
            self.progressMaximumChanged.connect(pb.setMaximum)
            self.infoTextChanged.connect(pb.setLabelText)
            self.titleChanged.connect(pb.setWindowTitle)
            self.showProgress.connect(pb.show)
            self.hideProgress.connect(pb.hide)
            
            pb.canceled.connect(self.cancel)
            
        self.titleChanged.emit('Please wait')
        if not os.path.exists(self.url):
            # Probably you want to save a new file
            args['skip_loading']=True
            
        elif not os.path.isfile(self.url):
            raise IOError('the file '+self.url+' does not exist')
                      
        if 'rgb_fits_mode' in args:
            self.RGB_mode=args['rgb_fits_mode']
        else:
            self.RGB_mode=False
        
        if (('skip_loading' in args) and 
            (args['skip_loading']==True) and
            not ('data' in args)):
            self.width = None
            self.height = None
            self.mode = None
        else:
        
            if ('data' in args):
                _tmp_data = args['data']
                self.width = _tmp_data.shape[0]
                self.height = _tmp_data.shape[1]
                
                if len(_tmp_data.shape) > 2:
                    dpth = _tmp_data.shape[2]
                    if dpth == 1:
                        self.mode = 'L'
                    elif dpth == 3:
                        self.mode = 'RGB'
                    elif dpth == 4:
                        self.mode = 'RGBA'
                    else:
                        return None
                
                
            else:
                _tmp_data = self.open(self.url, page, PIL_priority=True, only_sizes=True, **args)
            
            
            if not ('data' in args):
                del _tmp_data
            
        self.alignpoints=[]
        self.angle=0
        self.offset=None
        self.setOffset([0,0])
    
    def _setModeFromArray(self, arr):
        if len(arr.shape) > 2:
            dpth = arr.shape[2]
            dtyp = arr.dtype
            
            if dpth == 1:
                if np.issubdtype(dtyp,np.float):
                    self.mode = 'F'
                elif (dtyp is np.int8) or (dtyp is np.uint8):
                    self.mode = 'L'
                elif (np.issubdtype(dtyp,np.int) or np.issubdtype(dtyp,np.uint)
                      or np.issubdtype(dtyp,np.uint16) or np.issubdtype(dtyp,np.uint32)
                      or np.issubdtype(dtyp,np.uint6)):
                    self.mode = 'I'
                elif np.issubdtype(dtyp,np.bool):
                    self.mode = '1'
            elif dpth == 3:
                self.mode = 'RGB'
            elif dpth == 4:
                self.mode = 'RGBA'
            else:
                # multidimensional image AKA datacube
                self.mode = 'M'*dpth
        else:
            self.mode = '0'
            
    def setUrl(self, url, page):
        self.url=str(url)
        self.name=os.path.basename(self.url)
        self.page=page
        self.tool_name = self.name+'-frame'+str(self.page)
        self.long_tool_name = self.url+'-frame'+str(self.page)
        
    def isRGB(self):
        return ('RGB' in self.mode)
    
    
    
    def getNumeberOfComponents(self):
        if '1' in self.mode:
            return 1
        elif 'L' in self.mode:
            return 1
        elif 'P' in self.mode:
            return 1
        elif 'RGBA' in self.mode:
            return 4
        elif 'RGB' in self.mode:
            return 3
        elif 'CMYK' in self.mode:
            return 4
        elif 'YCbCr' in self.mode:
            return 3
        elif 'LAB' in self.mode:
            return 3
        elif 'HSV' in self.mode:
            return 3
        elif 'I' in self.mode:
            return 1
        elif 'F' in self.mode:
            return 1
        elif 'M' in self.mode:
            return len(self.mode)
        else:
            return 0
        
    def isUsed(self):
        
        check = self.getProperty('listItem')
        
        if (check is None):
            return True
        elif check.checkState() == 2:
            return True        
        else:
            return False
            
    def addProperty(self, key, val):
        self.properties[key]=val
        
    def getProperty(self, key):
        
        if key in self.properties:
            return self.properties[key]
        else:
            log.log(repr(self),'image '+str(self.name)+' has no property '+str(key),level=logging.WARNING)
            return None
            
    """
    setOffset([x_offset, y_offset]):
    """ 
    def setOffset(self,xyoff):
        
        if self.isRGB:
            self.offset=np.array([float(xyoff[0]),float(xyoff[1]),0,0])
        else:
            self.offset=np.array([float(xyoff[0]),float(xyoff[1])])

    def setAngle(self,ang):
        self.angle=ang
     
    def getData(self, asarray=False, asuint8=False, fit_levels=False, ftype=np.float32, PIL_priority=False):
        return self.open(self.url, self.page, asarray, asuint8, fit_levels, ftype, PIL_priority, **self._open_args)
        
    def open(self, file_name, page=0, asarray=False, asuint8=False, fit_levels=False, ftype=np.float32,
             PIL_priority=False, only_sizes=False, force_update=False, **args):
        
        data = self._open(file_name, page, asarray, asuint8, fit_levels, ftype, PIL_priority, 
                         only_sizes, force_update, **args)
        
        if data is None:
            self.is_good=False
        else:
            self.is_good=True
        
        QtGui.QApplication.instance().processEvents()
        
        return data
    
    def _open(self, file_name, page=0, asarray=False, asuint8=False, fit_levels=False, ftype=np.float32,
             PIL_priority=False, only_sizes=False, force_update=False, **args):
        
        image = None
        
        file_path,file_ext = os.path.splitext(file_name)
        
        file_ext=file_ext.lower()
                            
        if 'rgb_fits_mode' in args:
            self.RGB_mode=args['rgb_fits_mode']
        else:
            self.RGB_mode=False 
        
        if np.dtype(ftype).kind!='f':
            raise Exception("Error: float type neede for \'ftype\' argument")
        
        if file_ext in getSupportedFormats():
            file_type = getSupportedFormats()[file_ext]
        else:
            return None
        
        if page == 0:
            log.log(repr(self),"Opening file \'"+str(file_name)+"\'",level=logging.INFO)
            log.log(repr(self),"file format: \'"+str(file_type)+"\'",level=logging.DEBUG)
            
        ctime = None
        exif_file_path = file_path+'.exif'
        
        if os.path.isfile(exif_file_path):
            self.importProperties(exif_file_path)
                
        #choosing among specific loaders
        if file_type == 'FITS':
            if not FITS_SUPPORT:
                #this should never happen
                return None
            
            try:
                hdu_table=pyfits.open(file_name)
            except IOError as exc:
                try:
                    hdu_table=pyfits.open(file_name, ignore_missing_end=True)
                except Exception as exc2:
                    showErrorMsgBox(exc2)
                    return None
                
            header = hdu_table[0].header
            
            for k, v in header.items():
                self.addProperty(k, v)
            
            for date_tag,time_tag in (('DATE-OBS','TIME-OBS'),('DATE','TIME')):
                if date_tag in header:
                    ctime=_getCTime(header[date_tag],'T')
                    
            #checking for 3 ImageHDU (red, green and blue components)
            if self.RGB_mode and (len(hdu_table) >= 3):
                layers = []
                for i in hdu_table:
                    try:
                        if i.is_image and (len(i.data.shape)==2):
                            layers.append(i)
                    except AttributeError:
                        if isinstance(i,(pyfits.PrimaryHDU,pyfits.ImageHDU)):
                            try:
                                if len(i.data.shape)==2:
                                    layers.append(i)
                                else:
                                    continue
                            except:
                                continue
                        else:
                            continue
                        
                if len(layers) == 3:
                    if ((layers[0].data.shape == layers[1].data.shape) and
                        (layers[0].data.shape == layers[2].data.shape)):
                        is_RGB=True
                else:
                    # if there are more or less then 3 ImageHDU
                    # it is not an RGB fits file
                    is_RGB=False
            else:
                is_RGB=False
            
            
            if self.RGB_mode and is_RGB:
                if page!=0:
                    return None
                else:
                    imh,imw=layers[0].data.shape
                    img = np.zeros((imh,imw,len(layers)))
                    
                    for j in range(len(layers)):
                        img[...,j]=layers[j].data
                    
                    self._setSize(img)
                    
                    if only_sizes:
                        return True
                    elif asarray:
                        if asuint8:
                            image = normToUint8(img, fit_levels)
                        else:
                            image = img.astype(ftype)
                    else:
                        image = Image.fromarray(normToUint8(img))

            else:
                i=0
                npages=page
                while(i>=0):
                    try:
                        imagehdu = hdu_table[i]
                    except IndexError:
                        i=-1
                        return None
                    
                    try:
                        if not imagehdu.is_image:
                            i+=1
                            continue
                    except AttributeError:
                        if not isinstance(imagehdu,(pyfits.PrimaryHDU,pyfits.ImageHDU)):
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
                            naxis=len(imagehdu.data.shape)
                        except:
                            log.log(repr(self),"FITS: corrupted data", level=logging.ERROR)
                            return None
                    else:
                        if naxis <= 1:
                            #cannot handle 0-D or 1-D image data!
                            log.log(repr(self),"FITS: unsupported data format in HDU "+str(i),level=logging.WARNING)
                        else:
                            axis=imagehdu.data.shape[:-2] #number of image layers
                            imh,imw=imagehdu.data.shape[-2:] #image size
                            
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
                                self._setSize(data)
                                
                                if only_sizes:
                                    return True
                                elif asarray:
                                    if asuint8:
                                        image = normToUint8(data, fit_levels)
                                        break
                                    else:
                                        image = data.astype(ftype)
                                        break
                                else:
                                    image = Image.fromarray(normToUint8(data))
                                    break
                    
                    finally:
                        i+=1

        elif file_type =='NPY':
            #the files of this type contain
            #only one array
            if page > 0:
                return None
                        
            ctime=getCreationTime(file_name)
            img = np.load(file_name)
            
            if len(img.shape) < 2:
                return None
            
            self._setSize(img)
                    
            if only_sizes:
                return True            
            elif asarray:
                if asuint8:
                    image = normToUint8(img, fit_levels)
                else:
                    image = img.astype(ftype)
            else:
                image = Image.fromarray(normToUint8(img))


        elif file_type =='NPZ':
            
            npzarch = np.load(file_name)
            ctime=getCreationTime(file_name)
                        
            if page < len(npzarch):
                img = npzarch.values()[page]
            else:
                return None
            
            if len(img.shape) < 2:
                return None
            
            self._setSize(img)
                    
            if only_sizes:
                return True            
            elif asarray:
                if asuint8:
                    image = normToUint8(img, fit_levels)
                else:
                    image = img.astype(ftype)
            else:
                image = Image.fromarray(normToUint8(img))
            
        elif file_type =='CR2':
            cr2file = cr2plugin.imread(file_name)
            
            for k, v in cr2file.EXIF.items():  #READING EXIF
                if (k==306) or (k==36867) or (k==36868):
                    ctime=_getCTime(v)
                    self.addProperty('UTCEPOCH',ctime)
                if k in ExifTags.TAGS:
                    self.addProperty(ExifTags.TAGS[k], v)
                else:
                    self.addProperty(k, v)
                        
            for k, v in cr2file.MAKERNOTES.items():
                self.addProperty(('MAKERNOTE',k), v)
                            
            if page > 0:
                return None

            self.width,self.height = cr2file.size
            self.mode = 'L'
            
            self.canceled.connect(cr2file.cancel)
            cr2file.decodingProgressChanged.connect(self.progressValueChanged.emit)
            cr2file.decodingStarted.connect(self.showProgress.emit)
            cr2file.decodingEnded.connect(self.hideProgress.emit)
                 
            if FITS_SUPPORT:
                fits_header=[]
                if ctime is not None:
                    gm=time.gmtime(ctime)
                    date = '{0:02d}-{1:02d}-{2:02d}T{3:02d}:{4:02d}:{5:02.0f}'.format(
                        gm.tm_year,gm.tm_mon,gm.tm_mday,gm.tm_hour,gm.tm_min,gm.tm_sec)
                    fits_header.append(('DATE-OBS',date,'Date of observations'))
                data_file_name=file_path+'.fits'
            else:
                data_file_name=file_path+'.npy'
                                       
            if asarray:

                self.infoTextChanged.emit(tr('decoding image ')+self.name+', '+tr('please wait...'))
                                
                if notUpdated(self.url,data_file_name) or force_update==True:
                    log.log(repr(self),'decoding raw data to file '+data_file_name,level=logging.INFO)
                    self.infoTextChanged.emit(tr('decoding raw data to file')+'\n'+data_file_name)
                    
                    try:
                        img = cr2file.load()
                        if img is None:
                            return None
                    except SyntaxError as exc:
                        msgBox = Qt.QMessageBox()
                        msgBox.setText('Corrupted CR2 data!')
                        msgBox.setInformativeText(str(exc))
                        msgBox.setIcon(Qt.QMessageBox.Critical)
                        msgBox.exec_()
                        return None
                    
                    if FITS_SUPPORT:
                        self._imwrite_fits_(img, override_name=os.path.splitext(data_file_name)[0],
                                            header=fits_header, force_overwrite=True)
                    else:
                        np.save(data_file_name,img)
                        
                    self.exportProperties(exif_file_path)
                                        
                    if asuint8:
                        image = normToUint8(img, fit_levels)
                    else:
                        image = img.astype(ftype)

                else:
                    log.log(repr(self),'loading raw data',level=logging.INFO)
                    self.infoTextChanged.emit(tr('decoding image ')+self.name+', '+tr('please wait...'))
                    try:
                        image = self.open(data_file_name, page, asarray, asuint8, fit_levels, ftype, PIL_priority,**args)
                    except:
                        image=None
                    
                    if (image is None) or (cr2file.size[0] != self.width) or (cr2file.size[1] != self.height):
                        self.open(file_name, page, asarray, asuint8, fit_levels, ftype, PIL_priority,force_update=True,**args)
            else:
                if (('convert_cr2' in args) and args['convert_cr2']==True):
                    self.infoTextChanged.emit(tr('decoding image')+', '+tr('please wait...'))
                     
                    if notUpdated(self.url,data_file_name):
                        log.log(repr(self),'decoding raw data to file '+data_file_name,level=logging.INFO)
                        self.infoTextChanged.emit(tr('decoding raw data to file')+'\n'+data_file_name)
                        
                        try:
                            img = cr2file.load()
                            if img is None:
                                return None
                        except SyntaxError as exc:
                            msgBox = Qt.QMessageBox()
                            msgBox.setText(tr('Corrupted CR2 data!'))
                            msgBox.setInformativeText(str(exc))
                            msgBox.setIcon(Qt.QMessageBox.Critical)
                            msgBox.exec_()
                            return None
                        
                        if FITS_SUPPORT:
                            self._imwrite_fits_(img, override_name=os.path.splitext(data_file_name)[0],
                                                header=fits_header, force_overwrite=True, compressed=True)
                        else:
                            np.save(data_file_name,img)

                self.exportProperties(exif_file_path)
                image = cr2file
            
            cr2file.decodingProgressChanged.disconnect()
            cr2file.decodingStarted.disconnect()
            cr2file.decodingEnded.disconnect()
            
            del cr2file
            
        elif file_type =='VIDEO':
            video = cv2.VideoCapture(file_name)
            s=video.read()
            total_frames=video.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT)
            if not s[0]:
                log.log(repr(self),"the video file is corrupted or have an unsupported format",level=logging.ERROR)
                return None
            elif total_frames <=0:
                log.log(repr(self),"the video file may be corrupted",level=logging.ERROR)
            elif page >= total_frames:
                log.log(repr(self),"video loading ended",level=logging.ERROR)
                self.hideProgress.emit()
                return None
            else:

                if only_sizes:
                    self.showProgress.emit()
                    self.progressMaximumChanged.emit(total_frames)
                    self.progressValueChanged.emit(page)
                    self.infoTextChanged.emit(tr('loading frame') +' '+ str(page) +'/'+str(total_frames)+ tr('of video')+' \n'+file_name)
                    Qt.QApplication.instance().processEvents()
                else:
                    self.hideProgress.emit()
                    
                shape = s[1].shape
                
                imh = s[1].shape[0]
                imw = s[1].shape[1]
                
                if len(shape) > 2:
                    dpth = shape[2]
                    if dpth == 1:
                        dep = 'L'
                    elif dpth == 3:
                        dep = 'RGB'
                    elif dpth == 4:
                        dep = 'RGBA'
                    else:
                        return None
                            
                self.width = imw
                self.height = imh
                self.mode = dep

                log.log(repr(self),"loading frame "+str(page)+" of video "+str(file_name),level=logging.INFO)
                
                if only_sizes:
                    return True
                else:
                    video.set(cv2.cv.CV_CAP_PROP_POS_FRAMES,page)
                    
                    time_offset=video.get(cv2.cv.CV_CAP_PROP_POS_MSEC)/1000.0
                    
                    ctime=getCreationTime(file_name)+time_offset
                    
                    img = bgr2rgb(video.read()[1])

                
                    if asarray:
                        if asuint8:
                            image = normToUint8(np.asarray(img), fit_levels)
                        else:
                            image = (np.asarray(img)).astype(ftype)
                    else:
                        image = Image.fromarray(normToUint8(img))
                
        elif file_type =='???':
            #New codecs will be added here
            return None
        else:   

            try:
                cv2img = cv2.imread(file_name,-1)
            except:
                cv2img=None
                
            if (page==0) and (cv2img is not None) and not(PIL_priority):
                    
                img = bgr2rgb(cv2img)
                
                self._setSize(img)
                    
                if only_sizes:
                    return True            
                elif asarray:
                    if asuint8:
                        image = normToUint8(np.asarray(img), fit_levels)
                    else:
                        image = (np.asarray(img)).astype(ftype)
                else:
                    image = Image.fromarray(normToUint8(img))
            else:
                _using_cv2=False
                try:

                    img = Image.open(file_name)
                    img.seek(page)
                    
                    self.mode = img.mode
                    self.width = img.size[0]
                    self.height = img.size[1]
                    
                    try:
                        for k, v in img._getexif().items(): #READING EXIF
                            if (k==306) or (k==36867) or (k==36868):
                                tm_struct=[0]*9
                                stm=v.split(' ')
                                
                                dt = stm[0].split(':')  #the date is yyyy:mm:dd
                                
                                if len(dt)<3: #maybe it is yyyy-mm-dd
                                    dt = stm[0].split('-')
                                
                                if len(dt)<3: # the try to detect the separator
                                    dt = stm[0].split(stm[-3])
                                
                                if len(stm)==3:
                                    tm = stm[1].split(':')
                                    
                                    if len(tm)<3: # the try to detect the separator
                                        tm = stm[0].split(stm[-3])
                                        
                                    tm_struct[3]=int(tm[0])
                                    tm_struct[4]=int(tm[1])
                                    ff=float(tm[2])
                                    tm_struct[5]=int(tm[2])
                                else:
                                    continue
                                
                                yy=int(dt[0])
                                
                                if dt[0]<100:
                                    tm_struct[0]=1990+yy
                                else:
                                    tm_struct[0]=yy
                                
                                tm_struct[1]=int(dt[1])
                                tm_struct[2]=int(dt[2])
                                
                                ctime=time.mktime(time.struct_time(tm_struct))+math.modf(ff)[0]
                                
                            if k in ExifTags.TAGS:
                                self.addProperty(ExifTags.TAGS[k], v)
                            else:
                                self.addProperty(k, v)
                    except AttributeError:
                        pass
                    #testing decoder
                    pix = img.getpixel((0,0))
                except EOFError:
                    return None
                except Exception as err:
                    if page==0:
                        if cv2img is None:  # Nor PIL neither CV2 can open the file!
                            msgBox = Qt.QMessageBox()
                            msgBox.setText(str(err))
                            msgBox.setIcon(Qt.QMessageBox.Critical)
                            msgBox.exec_()
                            return None
                        else: # PIL can't open the image but CV2 can!
                            _using_cv2=True
                            img = bgr2rgb(cv2img)
                            self._setSize(img)
                    else:
                        return None
                
                if only_sizes:
                    return True            
                elif asarray:
                    if asuint8:
                        image = normToUint8(np.asarray(img), fit_levels)
                    else:
                        image = (np.asarray(img)).astype(ftype)
                else:
                    if _using_cv2:
                        image = Image.fromarray(normToUint8(img))
                    else:
                        image = img
    
        if not 'UTCEPOCH' in self.properties:
            if ctime is None:
                self.addProperty('UTCEPOCH',getCreationTime(file_name))
            else:
                self.addProperty('UTCEPOCH',ctime)
        
        return image
    
    def _setSize(self, data):
        shape = data.shape
        
        self.height = shape[0]
        self.width = shape[1]
        
        self._setModeFromArray(data)
                        
    def exportProperties(self,url):
        try:
            f=open(url,'w')
            cPickle.dump(self.properties,f)
            return True
        except Exception as exc:
            log.log(repr(self),'Cannot create file '+url+':'+str(exc),level=logging.ERROR)
            return False
        
    def importProperties(self,url):
        try:
            f=open(url,'r')
            newprop=cPickle.load(f)
            newprop.update(self.properties)
            self.properties = newprop
            f.close()
            del f
            return True
        except Exception as exc:
            log.log(repr(self),'Cannot read file '+url+':'+str(exc),level=logging.ERROR)
            return False

    def _fits_secure_imwrite(self, hdulist, url, force=False):
        if os.path.exists(url):
            if force:
                os.remove(url)
            else:
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

    def _imwrite_fits_(self, data, rgb_mode=True, override_name=None, force_overwrite=False,
                       compressed=False, header={},outbits=16, **args):

        if override_name!= None:
            name = override_name
        else:
            name = self.url
            
        if compressed:
            imgHDU=pyfits.CompImageHDU
        else:
            imgHDU=pyfits.ImageHDU
            
        
        if outbits==8:
            data=normToUint8(data)
        elif outbits==16:
            data=normToUint16(data)
        elif outbits==32:
            data=data.astype(np.float32)
        elif outbits==64:
            data=data.astype(np.float64)
                
        if rgb_mode and (len(data.shape) == 3):
            
                #NOTE: cannot compress primary HDU
            hdu=pyfits.PrimaryHDU(header=getFitsStdHeader())                
            
            hdu_r = imgHDU(data[...,0].copy())
            hdu_g = imgHDU(data[...,1].copy())
            hdu_b = imgHDU(data[...,2].copy())
            
            hdu_r.update_ext_name('RED')
            hdu_g.update_ext_name('GREN')
            hdu_b.update_ext_name('BLUE')
            
            for k,v,d in header:
                hdu.header.update(str(k).upper(),v,str(d))
                hdu_r.header.update(str(k).upper(),v,str(d))
                hdu_g.header.update(str(k).upper(),v,str(d))
                hdu_b.header.update(str(k).upper(),v,str(d))
            
            if outbits==16:
                hdu_r.scale('int16', bzero=32768)
                hdu_g.scale('int16', bzero=32768)
                hdu_b.scale('int16', bzero=32768)
            
            
            hdl = pyfits.HDUList([hdu,hdu_r,hdu_g,hdu_b])
                
            log.log(repr(self),'Saving to '+name+'-RGB.fits',level=logging.INFO)
            self._fits_secure_imwrite(hdl,name+'-RGB.fits',force=force_overwrite)
            log.log(repr(self),hdl.info(),level=logging.INFO)
            
        elif (len(data.shape) == 3):
            hdl_r=self._get_fits_hdl(name,data[...,0].copy(),header,compressed,outbits)
            log.log(repr(self),'Saving to '+name+'-R.fits',level=logging.INFO)
            self._fits_secure_imwrite(hdl_r,name+'-R.fits',force=force_overwrite)
            log.log(repr(self),hdl_r.info(),level=logging.INFO)
            
            hdl_g=self._get_fits_hdl(name,data[...,1].copy(),header,compressed,outbits)
            log.log(repr(self),'Saving to '+name+'-G.fits',level=logging.INFO)
            self._fits_secure_imwrite(hdl_g,name+'-G.fits',force=force_overwrite)
            log.log(repr(self),hdl_g.info(),level=logging.INFO)
            
            hdl_b=self._get_fits_hdl(name,data[...,2].copy(),header,compressed,outbits)
            log.log(repr(self),'Saving to '+name+'-B.fits',level=logging.INFO)
            self._fits_secure_imwrite(hdl_b,name+'-B.fits',force=force_overwrite)
            log.log(repr(self),hdl_b.info(),level=logging.INFO)
            
        elif (len(data.shape) <= 2):  
            hdl=self._get_fits_hdl(name,data,header,compressed,outbits)
            log.log(repr(self),'Saving to '+name+'.fits',level=logging.INFO)
            self._fits_secure_imwrite(hdl,name+'.fits',force=force_overwrite)
            log.log(repr(self),hdl.info(),level=logging.INFO)
        else:
            showErrorMsgBox("unsupported data format!")
            
    def _get_fits_hdl(self,name,data,header,compressed=False,outbits=16):
            if compressed: #NOTE: cannot compress primary HDU
                hdu = pyfits.PrimaryHDU(header=getFitsStdHeader())
                com = pyfits.ImageHDU(data,header=getFitsStdHeader())
                for k,v,d in header:
                    hdu.header.update(str(k).upper(),v,str(d))
                    com.header.update(str(k).upper(),v,str(d))
                if outbits==16:
                    com.scale('int16', bzero=32768)
                hdl = pyfits.HDUList([hdu,com])
            else:
                hdu = pyfits.PrimaryHDU(data,header=getFitsStdHeader())
                for k,v,d in header:
                    hdu.header.update(str(k).upper(),v,str(d))
                if outbits==16:
                    hdu.scale('int16', bzero=32768)
                hdl = pyfits.HDUList([hdu])
            return hdl
                
    def _imwrite_cv2_(self, data, flags=None, force_overwrite=False, override_name=None, **args):
        
        if override_name!= None:
            url = override_name
        else:
            url = self.url
        
        try:
            if os.path.exists(url):
                if force_overwrite:
                    os.remove(url)
                else:
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
                    
            if len(data.shape) == 3:
                return cv2.imwrite(url,data[...,(2,1,0)].copy(),flags)
            elif len(data.shape) == 2:
                return cv2.imwrite(url,data,flags)
            else:
                #this should never happens
                raise TypeError("Cannot save "+str(len(data.shape))+"-D images")
        except Exception as exc:
            log.log(repr(self),"Cannot save image due to cv2 exception: " + str(exc),level=logging.ERROR)
            msgBox = Qt.QMessageBox()
            msgBox.setText(tr("Cannot save image due to cv2 exception:"))
            msgBox.setInformativeText(str(exc))
            msgBox.setIcon(Qt.QMessageBox.Critical)
            msgBox.exec_()
            return False       
    
    def saveData(self, data=None, filename=None, save_dlg=None, force_overwrite=False,
             frmat=None, bits=None, dtype=None, fits_compressed=False,
             rgb_fits_mode=True, flags=None, **args):
        
        """
        save the Frame data to the current file
        
        Parameters
        ----------
        
        data : numpy.ndarray [=None]
            Specify the data to write. If no data is passed, the current
            data is used.
        
        filename : string [=""]
            Specify the output file. If no name is specified, the current
            file url is used.
            
        save_dlg : QWidget [=None]
            If a QWidget is passed, it will be uesd as save-dialog window.
            If None is passed the default dialog will be used else if 
            False is passed then no dialog will be used.
            
            NOTE: If a save-dialog is used, then its options will take
                  precedence over any other conflicting parameter passed.
            
        force_overwrite: bool [=False]
            If true the file will be overwritten without any confirmation.
            
        frmat: string [=None]
            'fits', 'numpy', 'jpg', 'png'
            
        bits: integer [=None]
            8, 16, 32, 64
            
        dtype: string [=None]
            'uint', 'int', 'float'
            
        FITS options
        ------------
        
        rgb_fits_mode : bool [=True]
            If true a single RGB FITS file will be saved, otherwise
            a mocrhomatic FITS file will be written for each component.
            
        fits_compressed : bool [=False]
            Specify if compression must be applied or not.
        
        fits_header : dict [={}]
        
        CV2 options
        -----------
        
        flags : tuple [=None]
        """
        
        external_save_dialog=False
        use_dialog=True 
        
        if save_dlg is None:
            log.log(repr(self),"Creating a new standard save-dialog window",level=logging.DEBUG)
            self.save_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'save_dialog.ui'))
            external_save_dialog=False
            use_dialog=True
            try:
                #connecting signals
                self.save_dlg.radioButtonJpeg.toggled.connect(self._updateSaveOptions)
                self.save_dlg.radioButtonPng.toggled.connect(self._updateSaveOptions)
                self.save_dlg.radioButtonTiff.toggled.connect(self._updateSaveOptions)
                self.save_dlg.radioButtonFits.toggled.connect(self._updateSaveOptions)
                self.save_dlg.radioButtonNumpy.toggled.connect(self._updateSaveOptions)
                self.save_dlg.radioButtonInt.toggled.connect(self._updateSaveOptions)
                self.save_dlg.radioButtonFloat.toggled.connect(self._updateSaveOptions)
                self.save_dlg.radioButton8.toggled.connect(self._updateSaveOptions)
                self.save_dlg.radioButton16.toggled.connect(self._updateSaveOptions)
                self.save_dlg.radioButton32.toggled.connect(self._updateSaveOptions)
                self.save_dlg.radioButton64.toggled.connect(self._updateSaveOptions)
                self.save_dlg.checkBoxUnsigned.stateChanged.connect(self._updateSaveOptions)
                self.save_dlg.pushButtonDestDir.clicked.connect(self._getDestDir)
                self.save_dlg.radioButtonFits.setEnabled(FITS_SUPPORT)
                
                self.save_dlg.saveMastersCheckBox.hide()

            except Exception as exc:
                log.log(repr(self),"Unsupported dialog window: " + str(exc),level=logging.ERROR)
                del self.save_dlg
        elif save_dlg == False:
            external_save_dialog=False
            use_dialog=False
            log.log(repr(self),"Using no save-dialog window",level=logging.DEBUG)
        else:
            log.log(repr(self),"Using an existing external save-dialog window: "+str(save_dlg),level=logging.DEBUG)
            external_save_dialog=True
            use_dialog=True
            self.save_dlg=save_dlg #NOTE: external dialogs passed here,
                                    #     must have their own signals already 
                                    #     connected to theire respective slots
                                    #     and must follow the naming scheme of
                                    #     'save_dialog.ui'
            try:
                self.save_dlg.saveMastersCheckBox.hide()
            except:
                # no error here if there is no saveMastersCheckBox
                pass
        
        if use_dialog:
            log.log(repr(self),"Running save-dialog window..." ,level=logging.DEBUG)
                        
            if filename == None:
                self.save_dlg.lineEditFileName.setText(os.path.basename(self.url))
                self.save_dlg.lineEditDestDir.setText(os.path.dirname(self.url))
            else:
                self.save_dlg.lineEditFileName.setText(os.path.basename(filenamel))
                self.save_dlg.lineEditDestDir.setText(os.path.dirname(filenamel))
            
            self._updateSaveOptions()
            if self.save_dlg.exec_() == 1:
                destdir=str(self.save_dlg.lineEditDestDir.text())
                name=str(self.save_dlg.lineEditFileName.text())
                
                valid_dir  = os.path.isdir(destdir)
                valid_name = (name.strip() != "")
                
                while not (valid_dir and valid_name):
                    
                    if not valid_dir:
                        showWarningMsgBox(tr("The selected output folder is not a directory\nor it does not exist!"))                        
                    if not valid_name:
                        showWarningMsgBox(tr("The file name is not valid!"))
                        
                    if self.save_dlg.exec_() != 1:
                        log.log(repr(self),"Operation canceled: deleting save dialog window",level=logging.DEBUG)
                        del self.save_dlg
                        return False                    
                    destdir=str(self.save_dlg.lineEditDestDir.text())
                    name=str(self.save_dlg.lineEditFileName.text())
                        
                    valid_dir  = os.path.isdir(destdir)
                    valid_name = (name.strip() != "")
                
                                
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
                
                
                filename=os.path.join(destdir,name+"."+frmat)
                
                rgb_fits_mode = (self.save_dlg.rgbFitsCheckBox.checkState()==2)
                fits_compressed = (self.save_dlg.comprFitsCheckBox.checkState()==2)
                
                args["force_overwrite"]=force_overwrite
                args["frmat"]=frmat
                args["bits"]=bits
                args["dtype"]=dtype
                args["flags"]=flags
                                
            if not external_save_dialog:
                log.log(repr(self),"Deleting save dialog window",level=logging.DEBUG)
                del self.save_dlg
        
        if data is None:
            data=self.getData(asarray=True)
            
        log.log(repr(self),"Saving Frame data to file: "+self.url,level=logging.INFO)
        log.log(repr(self),"filename: "+str(filename),level=logging.DEBUG)
        log.log(repr(self),"frmat: "+str(frmat),level=logging.DEBUG)
        log.log(repr(self),"bits: "+str(bits),level=logging.DEBUG)
        log.log(repr(self),"dtype: "+str(dtype),level=logging.DEBUG)
        log.log(repr(self),"save_dlg: "+str(save_dlg),level=logging.DEBUG)
        log.log(repr(self),"rgb_fits_mode: "+str(rgb_fits_mode),level=logging.DEBUG)
        log.log(repr(self),"fits_compressed: "+str(fits_compressed),level=logging.DEBUG)
        log.log(repr(self),"flags: "+str(flags),level=logging.DEBUG)
        log.log(repr(self),"args: "+str(args),level=logging.DEBUG)
                
        if frmat=='fits':
            try:
                return self._imwrite_fits_(data,rgb_fits_mode,compressed=fits_compressed,outbits=bits,override_name=filename,**args)
            except:
                return self._imwrite_fits_(data,rgb_fits_mode,compressed=False,outbits=bits,override_name=filename,**args)
                if use_dialog:
                    showWarningMsgBox(tr("Cannot save compressed files with this version of pyfits")+":\n "+ tr("the image was saved as an uncompressed FITS file."))
                else:
                    log.log(repr(self),"Cannot save compressed files with this version of pyfits: the image was saved as an uncompressed FITS file.",level=logging.WARNING)
                
            
        elif frmat=='numpy':
            return np.save(filename,data.astype(dtype+str(bits)))
        else:
            
            if bits==8:
                rawavg=normToUint8(data, False)
            elif bits==16:
                rawavg=normToUint16(data, False)
            else:
                #this should never be executed!
                showErrorMsgBox(tr("Cannot save image:"),tr("Unsupported format ")+str(bits)+"-bit "+tr("for")+" "+str(frmt))
                return False
                
            return self._imwrite_cv2_(data,flags,force_overwrite,override_name=filename)
    
    def _getDestDir(self):
        destdir = str(Qt.QFileDialog.getExistingDirectory(None,
                                                          tr("Choose the output folder"),
                                                          os.path.dirname(self.url),
                                                          DIALOG_OPTIONS | Qt.QFileDialog.ShowDirsOnly ))
        self.save_dlg.lineEditDestDir.setText(str(destdir))
        
    def _updateSaveOptions(self, *args):       
        
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
        
            
        self.save_dlg.radioButtonFloat.toggled.connect(self._updateSaveOptions)
    
        
def getSupportedFormats():
    formats={}
        
    for ext in Image.EXTENSION.keys():
        key=str(Image.EXTENSION[ext])
 
        if not (key in FORMAT_BLACKLIST):
            formats[ext]=key
            
    for ext in CUSTOM_EXTENSIONS.keys():
        key=str(CUSTOM_EXTENSIONS[ext])
 
        if not (key in FORMAT_BLACKLIST):
            formats[ext]=key
            
    return formats

def bgr2rgb(cv2img):
    if (len(cv2img.shape) == 3) and (cv2img.shape[2]==3):
        return cv2img[...,(2,1,0)]
    else:
        return cv2img
        

def normToUint8 (data,adapt=False, lrange=None):
    if data is None:
        return None
    else:
        minv,maxv=getMinMax(data,adapt, lrange) # 35% of computation time
        delta = maxv-minv
        if delta > 0: # 25% of computation time
            norm = 255.0/delta
            result=(data-minv)*norm
        else:
            result=data            
        return result.clip(0,255).astype(np.uint8) #40% of computation time

def normToUint16 (data):    
    if data is None:
        return None
    elif data.dtype == np.uint16:
        return data
    else:
        if data.min() < 0:
            minv=data.min()
        else:
            minv=0
            
        if data.max() > 65536:
            maxv=data.max()
        else:
            maxv=65536.0
            
        norm = maxv-minv
        
        if norm > 0:
            spec=(data-minv)*65536.0/norm
        elif norm==0:
            spec=data
        else:
            #should never happens
            spec=-(data)*65536.0/norm
            
        return spec.astype(np.uint16)
    
def getMinMax(data,adapt=False, lrange=None):
    
    datamax=data.max()
    datamin=data.min()
    
    if ((adapt==2) and
        (lrange is not None) and
        (len(lrange)>=2)):
        maxv=lrange[1]*datamax/100.0
        minv=datamin+lrange[0]*(datamax-datamin)/100.0
    elif adapt==1:
        maxv=datamax
        minv=datamin
    else:
        if datamax > 65536:
            maxv=datamax
        elif datamax > 255:
            maxv=65536.0
        elif datamax <= 1:
            #some float point images have values in range [0,1]
            maxv=datamax
        else:
            maxv=255.0
        
        if datamin < 0:
            minv=datamin
        else:
            minv=0
    
    return (minv,maxv)

def testreshape(img,h,w):
    
    arr = 255*np.ones((h,w,3), np.uint8, 'C')
    
    arr[0:h,0:w,2] = img[2]
    arr[0:h,0:w,1] = img[1]
    arr[0:h,0:w,0] = img[0]
            
    arr=arr.astype('uint8')
    return arr

def getNeighboursAverage(array,x0,y0,raw_mode=False):
    
    h,w = array.shape[0:2]
    
    total1=0.0
    count1=0.0
    
    if raw_mode:
        x1=x0-2
        x2=x0+2
        y1=y0-2
        y2=y0+2
    else:
        x1=x0-1
        x2=x0+1
        y1=y0-1
        y2=y0+1        
    
    if (x1 >= 0):
        total1+=array[y0,x1]
        count1+=1
            
    if (x2 < w):
        total1+=array[y0,x2]
        count1+=1
            
    if (y1 >= 0):
        total1+=array[y1,x0]
        count1+=1
    if (y2 < h):
        total1+=array[y2,x0]
        count1+=1
    
    return (total1/count1)

def logpolar(input, wmul=1, hmul=1, clip=False):

    if clip:
        max_r = min(input.shape)/2
    else:
        max_r=((input.shape[0]/2)**2 + (input.shape[1]/2)**2)**0.5
    h = hmul*max_r
    w = wmul*360.0
    coordinates = np.mgrid[0:h,0:w] 
    log_r = max_r*(10**((coordinates[0]/h)-1))
    angle = 2.*math.pi*(coordinates[1]/w)

    lpinput = sp.ndimage.interpolation.map_coordinates(input,(log_r*np.cos(angle)+input.shape[0]/2.,log_r*np.sin(angle)+input.shape[1]/2.),order=3,mode='constant')

    return lpinput

def polar(input, wmul=1, hmul=1, clip=False):

    if clip:
        max_r = min(input.shape)/2
    else:
        max_r=((input.shape[0]/2)**2 + (input.shape[1]/2)**2)**0.5
    
    h = hmul*max_r
    w = wmul*360.0
    
    coordinates = np.mgrid[0:h,0:w] 
    r = (coordinates[0]/hmul)
    angle = 2.*math.pi*(coordinates[1]/w)

    lpinput = sp.ndimage.interpolation.map_coordinates(input,(r*np.cos(angle)+input.shape[0]/2.,r*np.sin(angle)+input.shape[1]/2.),order=1,mode='constant')

    return lpinput

def register_image(ref, img, sharp1=2, sharp2=2, align=True, derotate=True, int_order=0):
    
    if derotate:
        log.log("<lxnstack.utils module>",'computing image derotation...',level=logging.INFO)
        d = _derotate_mono(ref, img, sharp1)    
        angle = d[1]
        dsize = d[0].shape
        log.log("<lxnstack.utils module>",'rotation angle = '+str(angle),level=logging.INFO)
    else:
        angle=0
    
    if angle != 0:
        derotated = sp.ndimage.interpolation.rotate(img,angle,order=int_order,reshape=False,mode='constant',cval=0.0)
    else:
        derotated = img
    
    if align:
        log.log("<lxnstack.utils module>",'computing image shift...',level=logging.INFO)
        s = _correlate_mono(ref, derotated,sharp2)    
        log.log("<lxnstack.utils module>",'shift = '+str(s[1]),level=logging.INFO)
        shift = s[1]
        s0 = s[0]
        
    else:
        shift = [0,0]
        s0 = None
    
    return s0,shift,angle


def _derotate_mono(im1, im2, sharpening=2):
    
    f1 = _FFT_mono(im1)
    f2 = _FFT_mono(im2)
    
    m1 = np.fft.fftshift(abs(f1))
    del f1
    
    m2 = np.fft.fftshift(abs(f2))
    del f2
    
    l1 = logpolar(m1,wmul=4,clip=True)
    del m1
    
    l2 = logpolar(m2,wmul=4,clip=True)
    del m2
        
    f1 = _FFT_mono(l1)
    del l1
    
    f2 = _FFT_mono(l2)
    del l2
    
    f1 = (f1*f2.conj())/abs(f1*f2)
    
    del f2
    
    r = _IFT_mono(f1)

    del f1
    
    r=np.fft.ifftshift(r)
            
    half = r.shape[1]/2
        
    r = r[...,0:half] + r[...,half:]
    
    half = r.shape[1]/2
    
    c = np.empty_like(r)
    
    c[...,0:half] = r[...,half:]
    c[...,half:]  = r[...,0:half]
    
    del r
    
    if sharpening > 0:
        c = ndimage.gaussian_filter(c,sharpening)
    
    rmax=(np.unravel_index(c.argmax(),c.shape)[1]*180.0/c.shape[1]) - 90
    
    return c,rmax


def _correlate_mono(im1, im2, sharpening=1):
        
    n = np.zeros_like(im1)

    n[0:im2.shape[0],0:im2.shape[1]]=im2
    
    f1 = _FFT_mono(im1)
    f2 = _FFT_mono(n)
    
    f = (f1*f2.conj())/abs(f1*f2)
    
    del f1
    del f2
    
    r = abs(_IFT_mono(f))
    
    #this section is necessary to avoid 
    #the bad infuence of the maximum at
    #the ceter of the image
    
    r_0_0=r[0,0]
    r_1_0=r[-1,0]
    r_0_1=r[0,-1]
    r_1_1=r[-1,-1]
    
    mean_1 = r.mean()
    max_1= r.max()
    
    r[0,0]=r.min()-1
    r[-1,0]=r.min()-1
    r[0,-1]=r.min()-1
    r[-1,-1]=r.min()-1
    
    mean_2 = r.mean()
    max_2 = r.max()
    
    if ((mean_1/mean_2)<0.2) and ((max_1*max_2)<max_1):
        #then probably the center is the only maximum present in the image
        log.log("<lxnstack.utils module>",' probably very small shift',level=logging.INFO)
        r[0,0]=r_0_0
        r[-1,0]=r_1_0
        r[0,-1]=r_0_1
        r[-1,-1]=r_1_1

    del f
    
    r=np.fft.ifftshift(r)

    if (r.shape[0]%2) == 0:
        y_corr=0.5
    else:
        y_corr=0
    
    if (r.shape[1]%2) == 0:
        x_corr=0.5
    else:
        x_corr=0
    
    center = (r.shape[0]/2.0,r.shape[1]/2.0,)

    if sharpening > 0:
        r = ndimage.gaussian_filter(r,sharpening)
    
    rmax=np.unravel_index(r.argmax(),r.shape)
    
    #subpixel alignment
    
    if ((rmax[0] < 10) or (rmax[0] > (r.shape[0]-10)) or
        (rmax[1] < 10) or (rmax[1] > (r.shape[1]-10))):
        #this is a very bad situation!
        log.log("<lxnstack.utils module>"," Shift is too big for sub-pixe alignment",level=logging.WARNING)
        shift=[center[1]-rmax[1],center[0]-rmax[0]]
        return (r,shift)
    
    if r.shape[1] <= 32:
        x_start=0
        x_end = r.shape[1]
    else:        
        x_start = rmax[1]-10
        x_end = rmax[1]+11
        
    if r.shape[0] <= 32:
        y_start=0
        y_end = r.shape[0]
    else:        
        y_start = rmax[0]-10
        y_end = rmax[0]+11

    zoom_level=25.0

    sub_region=r[y_start:y_end,x_start:x_end]
    sub_region=sp.ndimage.zoom(sub_region,zoom_level,order=5)

    submax = np.unravel_index(sub_region.argmax(),sub_region.shape)
    del sub_region
    
    pos_max = (y_start+submax[0]/zoom_level, x_start+submax[1]/zoom_level)

    shift=[center[1]+x_corr-pos_max[1],center[0]+y_corr-pos_max[0]]

    return (r,shift)

def brakets(text):
    def wrapped(text):
        return '('+text+')'
    return wrapped(text)


def getSciStr(val):

    if val!=0.0:    
        exp = int(np.floor(math.log10(abs(val))))
    
        if (exp >= 2) or (exp < 0):
            sv = val/(10.0**exp)
    
            return '{0:1.2f}e{1:02d}'.format(sv,exp)
        else:
            return '{0:1.2f}'.format(val)
    else:
        return '0.00'
    
def getTimeStr(val):
    return time.strftime('%H:%M:%S',time.gmtime(val))

def drawMarker(painter, x, y, r=7, l=4, ring=True, cross=True, square=False):
    if ring:
        painter.drawEllipse(Qt.QPointF(x,y),r,r)
    if square:
        painter.drawRect(Qt.QRectF(x-r/2.0,y-r/2.0,r,r))
    if cross:
        painter.drawLine(Qt.QPointF(x-r-l,y),Qt.QPointF(x-r+l,y))
        painter.drawLine(Qt.QPointF(x+r-l,y),Qt.QPointF(x+r+l,y))
        painter.drawLine(Qt.QPointF(x,y-l-r),Qt.QPointF(x,y-r+l))
        painter.drawLine(Qt.QPointF(x,y+r+l),Qt.QPointF(x,y+r-l))
    
    if not (cross or ring or square):
        painter.drawPolygon(Qt.QPointF(x-r,y),Qt.QPointF(x,y-r),Qt.QPointF(x+r,y),Qt.QPointF(x,y+r))
        
def drawAxis(painter, data_x=(0,1), data_y=(0,1), x_offset=60.0, y_offset=30.0, axis_name=('x','y'),
             inverted_y=False, x_str_func=str,y_str_func=getSciStr):
    
    surface_window=painter.window()
    
    w=surface_window.width()
    h=surface_window.height()
    
    miny=data_y[0]
    maxy=data_y[-1]
    minx=data_x[0]
    maxx=data_x[-1]
    
    
    if inverted_y:
        x1=x_offset
        y1=y_offset
        x2=w-x_offset 
        y2=h-y_offset 
        y3=10
        x_scale=(w-2*x_offset)/(maxx-minx)
        y_scale=(h-2*y_offset)/(maxy-miny)
    else:
        x1=x_offset
        y1=h-y_offset
        x2=w-x_offset 
        y2=y_offset 
        y3=-10
        x_scale=(w-2*x_offset)/(maxx-minx)
        y_scale=-(h-2*y_offset)/(maxy-miny)
    
    pxy1=Qt.QPointF(x1,y1)
    px2=Qt.QPointF(x2,y1)
    py2=Qt.QPointF(x1,y2)
        
    #draw x-axis
    painter.setPen(Qt.QPen(QtCore.Qt.black,1,QtCore.Qt.SolidLine))
    painter.drawLine(pxy1,py2)
    painter.drawText(Qt.QPointF(x2,y1-y3),brakets(axis_name[0]))
    count=0
    for x in getChartDivision(minx,maxx,w/50):
        if x<=minx:
            continue
        elif x>maxx:
            break
        stxt_off=0.75+1.25*(count%2)
        painter.setPen(Qt.QPen(QtCore.Qt.black,1,QtCore.Qt.SolidLine))
        p1 = Qt.QPointF((x-minx)*x_scale+x1,y1)
        p2 = Qt.QPointF((x-minx)*x_scale+x1,y1-stxt_off*y3)
        p3 = Qt.QPointF((x-minx)*x_scale+x1-25,y1-stxt_off*y3-1.25*y3)
        p4 = Qt.QPointF((x-minx)*x_scale+x1,y2)
        painter.drawLine(p1,p2)
        painter.drawText(p3,x_str_func(x))
        painter.setPen(Qt.QPen(QtCore.Qt.gray,1,QtCore.Qt.DotLine))
        painter.drawLine(p1,p4)
        count+=1
    
    #draw y-axis
    painter.setPen(Qt.QPen(QtCore.Qt.black,1,QtCore.Qt.SolidLine))
    painter.drawLine(pxy1,px2)
    painter.drawText(Qt.QPointF(10,y2-y3-20),brakets(axis_name[1]))
    for y in getChartDivision(miny,maxy,h/50):
        if y<=miny:
            continue
        elif y>maxy:
            break
        painter.setPen(Qt.QPen(QtCore.Qt.black,1,QtCore.Qt.SolidLine))
        p1 = Qt.QPointF(2*x1/3,(y-miny)*y_scale+y1)
        p2 = Qt.QPointF(x1,(y-miny)*y_scale+y1)
        p3 = Qt.QPointF(5,(y-miny)*y_scale+y1)
        p4 = Qt.QPointF(x2,(y-miny)*y_scale+y1)
        painter.drawLine(p1,p2)
        painter.drawText(p3,y_str_func(y))
        painter.setPen(Qt.QPen(QtCore.Qt.gray,1,QtCore.Qt.DotLine))
        painter.drawLine(p2,p4)


def getSciVal(val):

    if val!=0.0:    
        exp = int(np.floor(math.log10(abs(val))))
        sv = val/(10.0**exp)
    
        return (sv,exp)
    else:
        return (0.0,0)

def ceil5(val):
    val*=10
    vmod=val%10
    if vmod>=5:
        return int(val+10-vmod)/10.0
    else:
        return int(val+5-vmod)/10.0

    
def floor5(val):
    val*=10
    vmod=val%10
    if vmod>=5:
        return int(val+5-vmod)/10.0
    else:
        return int(val-vmod)/10.0

def getSciRange(vmin,vmax):
    s1,e1=getSciVal(vmax)
    s2,e2=getSciVal(vmin)
    
    ds,de=getSciVal(vmax-vmin)
    ivmax = ceil5(s1*(10**(-de+e1)))*(10**(de))
    ivmin = floor5(s2*(10**(-de+e2)))*(10**(de))
    
    return (ivmin,ivmax)

def getChartDivision(vmin,vmax,n=10):
        
    step=(vmax-vmin)/float(n)
    
    arr = np.arange(vmin,vmax,step)
    
    return arr
    
    
def drawCurves(painter, data_x, data_y, min_max, color=0,errors=None,
               point_type='s', line_type=False, bar_type=False, int_param=64,
               point_size=2, line_width=1,x_offset=60.0,y_offset=30.0, inverted_y=False):
    
    
    surface_window=painter.window()
    w=surface_window.width()
    h=surface_window.height()
        
    pcount=len(data_y)
    
    miny=min_max[0]
    maxy=min_max[1]
    minx=data_x.min()
    maxx=data_x.max()
    
    if inverted_y:
        x1=x_offset
        y1=y_offset
        x_scale=(w-2*x_offset)/(maxx-minx)
        y_scale=(h-2*y_offset)/(maxy-miny)
    else:
        x1=x_offset
        y1=h-y_offset
        x_scale=(w-2*x_offset)/(maxx-minx)
        y_scale=-(h-2*y_offset)/(maxy-miny)
    
    painter.setPen(color)
    
    showpoints=True
    showline=True
    showbars=True
        
    if point_type==POINTS_TYPE[4]:
        cross=True
        ring=False
        square=False
        painter.setBrush(0)
        r1=point_size
        r2=point_size
    elif point_type==POINTS_TYPE[1]:
        cross=False
        ring=True
        square=False
        painter.setBrush(color)
        r1=point_size
        r2=point_size
    elif point_type==POINTS_TYPE[5]:
        cross=True
        ring=True
        square=False
        painter.setBrush(0)
        r1=3.0*point_size/2.0
        r2=point_size/2.0
    elif point_type==POINTS_TYPE[2]:
        cross=False
        ring=False
        square=False
        painter.setBrush(color)
        r1=point_size+1
        r2=point_size+1
    elif point_type==POINTS_TYPE[3]:
        cross=False
        ring=False
        square=True
        painter.setBrush(color)
        r1=point_size+1
        r2=point_size+1
    else:
        showpoints=False
    
    
    if line_type==LINES_TYPE[1]:
        linetype=QtCore.Qt.SolidLine
    elif line_type==LINES_TYPE[2]:
        linetype=QtCore.Qt.DashLine
    elif line_type==LINES_TYPE[3]:
        linetype=QtCore.Qt.DotLine
    elif line_type==LINES_TYPE[4]:
        linetype=QtCore.Qt.DashDotLine
    elif line_type==LINES_TYPE[5]:
        linetype=QtCore.Qt.DashDotDotLine    
    else:
        showline=False
       
    painter.setPen(color)
    if showpoints:
        for i in range(pcount):
            x=(data_x[i]-minx)*x_scale + x1
            y=(data_y[i]-miny)*y_scale + y1
            drawMarker(painter,x,y,r1,r2,ring,cross,square)
            if (errors is not None):
                if bar_type==BARS_TYPE[1]:
                    ys=(data_y[i]+errors[i]-miny)*y_scale + y1
                    yl=(data_y[i]-errors[i]-miny)*y_scale + y1
                    painter.drawLine(Qt.QPointF(x,yl),Qt.QPointF(x,ys))        
    
    if showline:
        painter.setPen(Qt.QPen(color, line_width, linetype))
        points=[]
        # now signal will be interpolated and all high frequency noise will be removed
        for p in interpolate(data_x, data_y,10,4,int_param):
            x=(p[0]-minx)*x_scale + x1
            y=(p[1]-miny)*y_scale + y1
            points.append(Qt.QPointF(x,y))
            #drawMarker(painter,x,y,r1,r2,False,True) #debug purpose only
        painter.drawPolyline(*points)
        
def interpolate(data_x, data_y, upsample_factor=4.0, downsample_factor=1.0, mask_factor=0, padding=20):
    
    ON=len(data_y)
    
    #padding for better results
    yst=data_y[0]
    ynd=data_y[-1]
    
    new_y_data=((yst,)*padding)+tuple(data_y)+((ynd,)*padding)
    data_y=np.array(new_y_data)
    
    #the actual interpolation process
    
    N=len(data_y)
    
    mask=np.zeros_like(data_y)

    for i in xrange(N):
        mask[i]=((1+np.cos(i*2.0*sp.pi/N))/2.0)**(mask_factor)
    
    ry=sp.signal.resample(data_y,N*upsample_factor,window=mask)

    if downsample_factor > 0:
        ry=sp.signal.resample(ry,N*downsample_factor)
    
    #now deleting the padding and retrieving the actual data
    delta=padding*downsample_factor
    ry=ry[delta:-delta]
    
    # NOTE: it seems that sp.signal.resample does not offer
    #       a valid way to correcly resample the data_x values!
    rx=[]    
    for i in xrange(ON-1):
        dd=(data_x[i+1]-data_x[i])/downsample_factor
        for n in xrange(downsample_factor):
            rx.append(data_x[i]+n*dd)
            
    for n in xrange(downsample_factor):
            rx.append(data_x[-1]+n*dd)
    
    newN = len(ry)
    
    result = np.empty((newN,2),dtype=np.float)
    
    for i in range(newN):
        result[i,0]=rx[i]
        result[i,1]=ry[i]
    
    return result


def exportTableCSV(self, qtable, fname, sep='\t', newl='\n', unit=','):
    
    try:
        f = open(fname,'w')
    except Exception as exc:
        msgBox = Qt.QMessageBox()
        msgBox.setText(tr("Cannot create the data file: ")+str(exc))
        msgBox.setInformativeText(tr("Assure you have the authorization to write the file."))
        msgBox.setIcon(Qt.QMessageBox.Critical)
        msgBox.exec_()
    else:
        line = ''
        rows = xrange(qtable.rowCount())
        cols = xrange(qtable.columnCount())
        
        for c in cols:
            itm = qtable.horizontalHeaderItem(c)
            line+=str(itm.text()).replace(' ','_')+str(sep)
        
        line = line[:-1]+str(newl)
        f.write(line)
        
        for r in rows:
            line=''
            for c in cols:
                itm = qtable.item(r,c)
                line+=str(itm.text()).replace('.',unit)+str(sep)   
            line = line[:-1]+str(newl)
            f.write(line)
        
        f.close()
        


#This function is a test for future de-blurring feature
def cepstrum(img):

    result = []
    if len(img.shape)==2:
        return cepstrum_mono(img)
    else:
        for l in range(img.shape[2]):
            
            result.append(cepstrum_mono(img[...,l]))
        
        final = np.ndarray((len(result[0]),len(result[0][0]),len(result)))
    
        for i in range(len(result)):
            final[...,i]=result[i]
        return final 
    
def autocepstrum(img):
    
    f = fft(img)
    
    f = (f*f.conj())/abs(f**2)
    
    return cepstrum( abs(ift(f)))

#This function is a test for future de-blurring feature
def cepstrum_mono(img):

    #this is the cepstrum
    return _IFT_mono(np.log10(1+abs(_FFT_mono(img))**2))

def ceplook(cep):

    #now a better look!    
    scep = np.fft.ifftshift(cep)
    norm = (scep - scep.min())/(scep.max()-scep.min())
    ecep = np.exp(2/(norm+1))    
    
    ecep = ecep-ecep.mean()
    return ((ecep.clip(-ecep.max()/2,ecep.max()/2)))

#This function is a test for future de-blurring feature
def getDefocusCircleRadius(img):

    if len(img.shape)==3:
        cep = cepstrum_mono(img.sum(2))
    elif len(img.shape)==2:
        cep = cepstrum_mono(img)
    
    i = polar(cep,1,2)
    
    mx=i.sum(1).argmax()/2.0
       
    return mx,cep

def getDefocusCircleRadius2(img):
    
    if len(img.shape)==3:
        cep = cepstrum_mono(img.sum(2))
    elif len(img.shape)==2:
        cep = cepstrum_mono(img)
    
    i=cep
    
    i = cv2.erode(cv2.dilate(cep,None),None)
    
    i = sp.ndimage.gaussian_filter(i,0.8)
   
    c = normToUint8(i)
    
    #del i
    
    circles = cv2.HoughCircles(c,cv2.cv.CV_HOUGH_GRADIENT,c.shape[0]/5.0,1,50,100)
    
    del c
    
    if circles is None:
        return (0,cep)
    else:

        d = min(img.shape[0],img.shape[1])

        cx = img.shape[1]/2.0
        cy = img.shape[0]/2.0

        tollerance=d/20.0
        
        best=None
        best_radius = 0
                
        for circle in circles[0]:
            x = circle[0]
            y = circle[1]
            r = circle[2]
            
            #the center of the circle we are searching for 
            #must be the center of the cepstrum image 
            difference = ((x-cx)**2+(y-cy)**2)**0.5

            if difference <= tollerance:
                if best is None:
                    best = difference
                    best_radius = r
                elif difference <= best:
                    best_radius = r
                    
        cv2.circle(i,(int(cx),int(cy)),best_radius,i.min())
        
        return (best_radius,i)

def spectrum(fft, shift=False):
    
    if shift:
        ff = np.fft.fftshift(fft)
    else:
        ff = fft        

    return abs(ff)**2
    
def magnitude(fft, shift=True):
    mag = spectrum(fft,shift)**0.5
    spec=np.log10(mag+1)

    return spec

    
def generateCosBell(w,h, roll_off=0.4):
    
    x,y=np.meshgrid(np.arange(w),np.arange(h))
    x=x*1.0/x.max() - 0.5
    y=y*1.0/y.max() - 0.5
    cb=(np.cos(math.pi*x)*np.cos(math.pi*y))**0.5

    return cb

def _FFT_mono(img):

    h,w=img.shape[0:2]
    
    cx = int(w/2)
    cy = int(h/2)
    
    optimal_w = cv2.getOptimalDFTSize(w) 
    optimal_h = cv2.getOptimalDFTSize(h)

    cmplx = np.zeros((optimal_h,optimal_w,2))
    cmplx[0:h,0:w,0]=img.real
    cmplx[0:h,0:w,1]=img.imag

    img_fft=cv2.dft(cmplx)
    
    return img_fft[...,0]+1j*img_fft[...,1]

def _IFT_mono(fft):

    imh,imw = fft.shape

    cmplx = np.zeros((imh,imw,2))
    cmplx[...,0]=fft.real
    cmplx[...,1]=fft.imag
    img_ift=cv2.idft(cmplx)
    
    return img_ift[...,0]

def _FFT_RGB(img):

    if type(img) != np.ndarray:
        return False

    result = []
        
    for l in range(img.shape[2]):
        
        result.append(_FFT_mono(img[...,l]))

    final = np.ndarray((len(result[0]),len(result[0][0]),len(result)), dtype='complex128')
    
    for i in range(len(result)):
        final[...,i]=result[i]
    return final 

def _IFT_RGB(fft):

    img = np.zeros_like(fft)
    res = np.zeros_like(fft)
    for l in range(fft.shape[2]):
        img[...,l] = _IFT_mono(fft[...,l])

    rel = img.real

    return rel #((rel-rel.min())*255/rel.max()).astype('uint8')

def fft(img):
    if len(img.shape)==3:
        return _FFT_RGB(img)
    else:
        return _FFT_mono(img)
    

def ift(img):
    if len(img.shape)==3:
        return _IFT_RGB(img)
    else:
        return _IFT_mono(img)

#This function is a test for future de-blurring feature
def convolve(img, fltr,transformed=False):
    fmax=max(fltr.max(),-fltr.min())
    i2=fltr.astype('complex')/fmax
    #img = img.astype('float64')/img.max()
            
    if (len(img.shape) == 3) and (len(i2.shape) == 2):
        f1 = fft(img)
        if transformed:
            f2m = i2
        else:
            f2m = fft(i2)
        f2=np.empty((f2m.shape[0],f2m.shape[1],f1.shape[2]),dtype=np.complex)
        for i in xrange(f1.shape[2]):
            f2[...,i] = f2m
    elif (len(img.shape) == 2) and (len(i2.shape) == 3):
        if transformed:
            f2 = i2
        else:
            f2 = fft(i2)
        f1m = fft(img)
        f1=np.empty((f1m.shape[0],f1m.shape[1],f2.shape[2]),dtype=np.complex)
        for i in xrange(f2.shape[2]):
            f1[...,i] = f1m
    elif (len(img.shape) == 3) and (i2.shape == img.shape):
        f1 = fft(img)
        if transformed:
            f2 = i2
        else:
            f2 = fft(i2)
    else:
        raise ValueError("Cannot deconvolve the image with the given filter!")
    del i2
    
    rf = ift(f1*f2)
    
    return rf

#This function is a test for future de-blurring feature
def deconvolve(img, fltr, transformed=False):
    fmax=max(fltr.max(),-fltr.min())
    i2=fltr.astype(np.complex)/fmax
    #img = img.astype('float64')/img.max()

    if (len(img.shape) == 3) and (len(i2.shape) == 2):
        f1 = fft(img)
        if transformed:
            f2m = i2
        else:
            f2m = fft(i2)
        f2=np.empty((f2m.shape[0],f2m.shape[1],f1.shape[2]),dtype=np.complex)
        for i in xrange(f1.shape[2]):
            f2[...,i] = f2m
    elif (len(img.shape) == 2) and (len(i2.shape) == 3):
        if transformed:
            f2 = i2
        else:
            f2 = fft(i2)
        f1m = fft(img)
        f1=np.empty((f1m.shape[0],f1m.shape[1],f2.shape[2]),dtype=np.complex)
        for i in xrange(f2.shape[2]):
            f1[...,i] = f1m
    elif (len(img.shape) == 3) and (i2.shape == img.shape):
        f1 = fft(img)
        if transformed:
            f2 = i2
        else:
            f2 = fft(i2)
    else:
        raise ValueError("Cannot deconvolve the image with the given filter!")
    del i2
    
    # This should avoid "division by 0" errors.
    mask1 = (f1==0)
    mask2 = (f2==0) 
    
    rf = ift((f1/(f2)))
        
    return rf

#TODO:
def waveletKernel(w, h, function, size, radial=False):
    if radial:
        r = (w**2+h**2)**0.5
        f = function(r+1,size[0])
        wav = np.empty((h,w),dtype=np.float32)
        for x in xrange(w):
            for y in  xrange(h):
                wav[y,x]=f[int(r/2+((x-w/2)**2+(y-h/2)**2)**0.5)]
    else:
        
        x,y = np.meshgrid(function(w,size[0]),function(h,size[1]))
        wav = (((x**2+y**2)**0.5))
        #wav = (x*y)
        
    return wav

def undefocus(img,radius):
    
    w = img.shape[1]
    h = img.shape[0]
    
    x,y=np.meshgrid(np.arange(-w/2,w/2),np.arange(-h/2,h/2))

    msk = 1.0*(((x**2+y**2)**0.5) < radius)
    
    del x,y
    
    df = abs(np.fft.fftshift(fft(msk)))
    del msk
    
    return np.fft.ifftshift(deconvolve(img,df))

def defocus(img,radius):
    
    w = img.shape[1]
    h = img.shape[0]
    
    x,y=np.meshgrid(np.arange(-w/2,w/2),np.arange(-h/2,h/2))

    msk = 1.0*(((x**2+y**2)**0.5) < radius)
    
    del x,y
    
    df = abs(fft(msk))
    del msk

    return convolve(img,df)
   

def storeTmpArray(array, tmpdir=None, compressed=False):
    
    if compressed:
        tmp = tempfile.NamedTemporaryFile(prefix="lxnstack-",suffix='.npz', dir=tmpdir)
        log.log("<lxnstack.utils module>"," saving to compressed temporary file "+str(tmp.name)+"\n",level=logging.DEBUG)
        np.savez_compressed(tmp.name,array)
    else:
        tmp = tempfile.NamedTemporaryFile(prefix="lxnstack-",suffix='.npy', dir=tmpdir)
        log.log("<lxnstack.utils module>"," saving to temporary file "+str(tmp.name)+"\n",level=logging.DEBUG)
        np.save(tmp.name,array)
    tmp.seek(0)
    return tmp
    
def loadTmpArray(tmpfile):
    tmpfile.file.seek(0)
    if tmpfile.name[-1]=='z':
        npzf=np.load(tmpfile.name)
        data=npzf['arr_0']
        del npzf.f
        npzf.close()
        return data
    else:
        return np.load(tmpfile.name, mmap_mode='r')

def generateHistGradient(height,color1,color2= QtCore.Qt.black):
    redlg = Qt.QLinearGradient(0.0,height*0.66,0.0,height*1.2)
    redlg.setColorAt(0, color1)
    redlg.setColorAt(1, color2)
    return redlg

def generatePreview(imgdata,max_dim):
    
    h=float(imgdata.shape[0])
    w=float(imgdata.shape[1])
    
    zoom_factor=0
    
    if w>=h:
        zoom_factor=max_dim/w
    else:
        zoom_factor=max_dim/h
    
    if (zoom_factor >= 1):
        log.log("<lxnstack.utils module>","A preview bigger than/equal to the actual image was requested!",level=logging.WARNING)
        return imgdata
    
    zoom=np.ones(len(imgdata.shape))
    zoom[0]=zoom_factor
    zoom[1]=zoom_factor
    
    return sp.ndimage.interpolation.zoom(imgdata,zoom,order=0)

def generateHistograhms(imgdata, bins=255):
    
    hists=[]
    shape=imgdata.shape
        
    hrange=getMinMax(imgdata,True)
    
    #NOTE: computing an extra histogram here for the total image
    #      is faster than adding the histograms of each component
    #      during the drawing operations.
    
    if len(shape)==2:
        h=np.histogram(imgdata,bins,range=hrange)
        hists.append(h)
        hists.append(h[:])
    else:
        channels=imgdata.shape[2]
        toth=None
        for i in range(channels):
            h=np.histogram(imgdata[...,i],bins,range=hrange)
            hists.append(h)
            if toth is None:
                toth=[h[0].copy(),h[1].copy()]
            else:
                toth[0]+=h[0]
        hists.insert(0,toth)
    
    
    return np.array(hists)

def applyWhiteBalance(data, factors, table):
    
    dmax=data.max()
    
    #TODO fix l and h
    
    factors_l=np.zeros(len(table),dtype=data.dtype)
    factors_m=np.zeros(len(table),dtype=data.dtype)
    factors_h=np.zeros(len(table),dtype=data.dtype)
    
    for i in table:
        
        l=factors[table[i]][0]
        m=factors[table[i]][1]
        h=factors[table[i]][2]
        
        #middle tones
        xm = np.tan(np.pi*(0.5-0.5*m))

        factors_l[i]=l
        factors_m[i]=xm
        factors_h[i]=h
        
    return (factors_h - factors_l)*dmax*((data/dmax)**factors_m)+dmax*factors_l

def applyHistWhiteBalance(hists, factors, table):
    
    hists2=hists.copy()
    for i in range(1,len(hists)):
        hmax=hists[i,1].max()
        
        l=factors[table[i-1]][0]
        m=factors[table[i-1]][1]
        h=factors[table[i-1]][2]
        
        xm = np.tan(np.pi*(0.5-0.5*m))
        
        hists2[i,1]=(h-l)*hmax*((hists[i,1]/hmax)**xm)+l*hmax
    
    return hists2

def drawHistograhm(painter, hists, xmin=None, xmax=None,logY=False):

    gm1 = 0.05 #geometric corrections
    gm2 = 1.0 - gm1
    
    surface_window=painter.window()
    w=surface_window.width()
    h=surface_window.height()
    
    ymax=0
    
    x0=w*gm1
    x1=w*gm2
    y0=h*gm2
    y1=h*gm1
    
    if hists is None:
        painter.setCompositionMode(0)
        painter.setPen(QtCore.Qt.black)
        painter.drawLine(x0,y0+2,x1,y0+2)
        painter.drawLine(x0-2,y0,x0-2,y1)
    
        painter.setPen(QtCore.Qt.DotLine)
        
        ly=np.emath.logn(10,y0/y1+1)
                    
        for yy in np.arange(y1,y0,(y0-y1)/10.0):
            
            if logY:
                yy=y0+(y1-y0)*np.emath.logn(10,yy/y1+1)/ly
            painter.drawLine(x0,yy,x1,yy)
            
            
        painter.setPen(QtCore.Qt.DashLine)
        painter.drawLine(x0,y1,x1,y1)
        
        return None
    
    if logY:
        ymax=max(ymax,max(np.emath.logn(10,hists[0][0]+1)))
    else:
        ymax=max(ymax,max(2,max(hists[0][0])))
    
    if xmax is None:
        xmax=max(hists[0][1])
    if xmin is None:
        xmin=min(hists[0][1])
    
    num_of_components=len(hists)
    
    for channel in range(num_of_components):
        draw_axes=False
        if channel==0:
            color = QtCore.Qt.darkGray
            painter.setCompositionMode(0)
        elif channel==1:
            color = QtCore.Qt.red
            painter.setCompositionMode(painter.CompositionMode_Plus)
        elif channel==2:
            color = QtCore.Qt.green
            painter.setCompositionMode(painter.CompositionMode_Plus)
        elif channel==3:
            color = QtCore.Qt.blue
            painter.setCompositionMode(painter.CompositionMode_Plus)
        else:
            color = QtCore.Qt.gray
            painter.setCompositionMode(0)
        
        if channel==(num_of_components-1):
            draw_axes=True
        
        path = Qt.QPainterPath()
        hist = hists[channel]
        
        path.moveTo(x0,y0)
        
        if xmax==xmin:
            xmax=xmin+1
            
        if ymax==0:
            ymax=1
        
        path.lineTo(x0+w*(hist[1][0]-1-xmin)*(gm2-gm1)/(xmax-xmin),y0)
        
        if logY:
            hist_y=np.emath.logn(10,hist[0]+1)
        else:
            hist_y=hist[0]
        
        for i in range(len(hist[1])-1):
            x=hist[1][i]
            y=hist_y[i]
            
            path.lineTo(x0+w*(x-xmin)*(gm2-gm1)/(xmax-xmin),y0-(h*(gm2-gm1))*y/ymax)

        path.lineTo(x0+w*(hist[1][-1]+1-xmin)*(gm2-gm1)/(xmax-xmin),y0)
        path.lineTo(x1,y0)
    
        painter.setBrush(generateHistGradient(h,color))
        painter.setPen(color)
        painter.drawPath(path)
    
        if draw_axes:
            painter.setCompositionMode(0)
            painter.setPen(QtCore.Qt.black)
            painter.drawLine(x0,y0+2,x1,y0+2)
            painter.drawLine(x0-2,y0,x0-2,y1)
        
            painter.setPen(QtCore.Qt.DotLine)
            
            ly=np.emath.logn(10,y0/y1+1)
                        
            for yy in np.arange(y1,y0,(y0-y1)/10.0):
                
                if logY:
                    yy=y0+(y1-y0)*np.emath.logn(10,yy/y1+1)/ly
                painter.drawLine(x0,yy,x1,yy)
                
                
            painter.setPen(QtCore.Qt.DashLine)
            painter.drawLine(x0,y1,x1,y1)
        
            painter.drawText(x0,y0+15,str(xmin))
            for xx in np.arange(x1,x0,-(x1-x0)/5.0):
                painter.drawLine(xx,y0,xx,y1)
                painter.drawText(xx-15,y0+15,str(xmax*(xx-x0)/(x1-x0)))
                
        if num_of_components==2:
                break
            
# Light curves generation functions
def getStarMagnitudeADU(ndimg, star_x, star_y, inner_radius, middle_radius, outer_radius):

    val_adu=[]
    bkg_adu=[]
    ir2 = (inner_radius**2)
    mr2 = (middle_radius**2)
    or2 = (outer_radius**2)
    
    for x in range(-int(inner_radius)-1,int(inner_radius)+1):
        for y in range(-int(inner_radius)-1,int(inner_radius)+1):
                                   
            p = (x**2+y**2)
            
            if p <= ir2:
                val_adu.append(ndimg[star_y+y,star_x+x])
            
    for x in range(-int(outer_radius)-1,int(outer_radius)+1):
        for y in range(-int(outer_radius)-1,int(outer_radius)+1):
            
            p = (x**2+y**2)
            
            if (p<=or2) and (p>mr2):
                bkg_adu.append(ndimg[star_y+y,star_x+x])
    
    val_adu=np.array(val_adu)
    bkg_adu=np.array(bkg_adu)
    
    total_star_pixels = len(val_adu)
    
    total_val_adu=val_adu.sum(0) # total value for star
    mean_bkg_adu=bkg_adu.mean(0) # average for background
    
    total_val_adu_delta=val_adu.shape[0] # error value for star
    mean_bkg_adu_sigma=bkg_adu.std(0) # average for background
    
    mean_adu = total_val_adu - mean_bkg_adu*total_star_pixels # best value for star
    mean_adu_delta = total_val_adu_delta/3.0 + mean_bkg_adu_sigma

    #this avoids negative or null value:
    if (mean_adu >0).all():        
        return (mean_adu, mean_adu_delta)
    else:
        raise ValueError('Negative or null ADU values are not allowed!\nPlease set the star marker correctly.')
            

def getLocale():
    try:
        settings = Qt.QSettings()
        settings.beginGroup("settings")
        lang = str(settings.value("language_file",None,str))
        settings.endGroup()
        if not os.path.isfile(lang):
            raise Exception('no valid file')
        return lang
    except Exception as exc:
        local = 'lang_'+str(Qt.QLocale.system().name())+'.qm'
        lang = os.path.join(paths.LANG_PATH,local)

        settings = Qt.QSettings()
        settings.beginGroup("settings")
       
        if os.path.exists(lang):
            current_language = lang
        else:
            current_language = local
            
        settings.setValue("language_file",current_language)
        settings.endGroup()
        return current_language
    
    