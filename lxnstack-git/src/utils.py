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

from PyQt4 import Qt, QtCore
import sys
import os
import subprocess
import numpy
import paths
import time

FORMAT_BLACKLIST = ['BUFR', 'EPS', 'GRIB',
                       'HDF5', 'MPEG','WMF' ]

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
    import pyfits
    FITS_SUPPORT=True
    print("FITS support enabled")
except ImportError:

    print("FITS support not enabled:")
    print("to enable FITS support please install the \'pyfits\' python package!")

    FITS_SUPPORT=False
    FORMAT_BLACKLIST.append('FITS')   

PROGRAM = paths.PROGRAM_NAME
PROGRAM_NAME = paths.PROGRAM_NAME

def tr(s):
    news=QtCore.QCoreApplication.translate('@default',s)
    #python3 return str...
    if type(news) == str:
        return news
    else:
        #... while python2 return QString 
        # that must be converted to str
        return str(news.toAscii())

def getSupportedFormats():
    formats={}
        
    for ext in Image.EXTENSION.keys():
        key=str(Image.EXTENSION[ext])
 
        if not (key in FORMAT_BLACKLIST):
            formats[ext]=key
    return formats

def normToUint8 (data):
    
    if data==None:
        return None
    elif data.dtype == numpy.uint8:
        return data
    else:
        norm = data.max()-data.min()
        if norm > 0:
            spec=(data-data.min())*255.0/norm
        elif norm==0:
            spec=data
        else:
            #shold never happens
            spec=-(data-data.min())*255.0/norm
            
        return spec.astype(numpy.uint8)
    
def normToUint16 (data):
    if data==None:
        return None
    elif data.dtype == numpy.uint16:
        return data
    else:
        norm = data.max()-data.min()
        if norm > 0:
            spec=(data-data.min())*65536.0/norm
        elif norm==0:
            spec=data
        else:
            #shold never happens
            spec=-(data-data.min())*65536.0/norm
            
        return spec.astype(numpy.uint16)

def _min(n1, n2):
    return ((n1>=n2)*n2 + (n1<n2)*n1)

def getJetColor(data):

     value = data.astype(numpy.float)

     x = (value - value.min())/float(value.max() - value.min())

     t = time.clock()
     
     r = (4*x - 1.5).clip(0.0,1.0) - (4*x - 3.5).clip(0.0,1.0)
     g = (4*x - 0.5).clip(0.0,1.0) - (4*x - 2.5).clip(0.0,1.0)
     b = (4*x + 0.5).clip(0.0,1.0) - (4*x - 1.5).clip(0.0,1.0)

     arr=[255*r, 255*g, 255*b]
     
     return arr


def arrayToQImage(img,R=0,G=1,B=2,A=3,bw_jet=True):
    
    if type(img) != numpy.ndarray:
        raise TypeError('In module utils, in function arrayToQImage, ndarray expected as first argumrnt but '+str(type(img))+' given instead')
    
    #searching for NaN values
    if img.dtype==numpy.float:
        tb=(img!=img).nonzero()
        img[tb]=numpy.Inf
        tb=(img==numpy.Inf).nonzero()
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
        arr = numpy.zeros((optimal_h, optimal_w, 4), numpy.uint8, 'C')
        
        if bw_jet:
            jet=getJetColor(img)
            arr[0:h,0:w,2] = jet[0]
            arr[0:h,0:w,1] = jet[1]
            arr[0:h,0:w,0] = jet[2]
        else:
            img2 = normToUint8(img)
            arr[0:h,0:w,2] = img2
            arr[0:h,0:w,1] = img2
            arr[0:h,0:w,0] = img2
            
        arr[0:h,0:w,3] = 255
        arr[h:,0:,3] = 0
        arr[0:,w:,3] = 0
        
    elif (img.ndim==3) and (channels == 3):
        img2 = normToUint8(img)
        arr = numpy.zeros((optimal_h, optimal_w, 4), numpy.uint8, 'C')
        arr[0:h,0:w,0:3]=img2[...,(B,G,R)]
        arr[0:h,0:w,3] = 255
        arr[h:,0:,3] = 0
        arr[0:,w:,3] = 0
        
    elif (img.ndim==3) and (channels == 4):
        img2 = normToUint8(img)
        arr = numpy.zeros((optimal_h, optimal_w, 4), numpy.uint8, 'C')
        arr[0:h,0:w]=img2[...,(B,G,R,A)]
    else:
        return None

    arr=arr.astype('uint8')
    result = Qt.QImage(arr.data,optimal_w,optimal_h,Qt.QImage.Format_ARGB32_Premultiplied)
    result._raw_data=arr
    result._original_data=img

    return result


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

def setV4LFormat(device,cmd):
    v4l2_ctl = subprocess.Popen(['v4l2-ctl','--device='+device, '--set-fmt-video='+cmd])
    v4l2_ctl.wait()
    del v4l2_ctl
    
def setV4LCtrl(device,ctrl,data):
    v4l2_ctl = subprocess.Popen(['v4l2-ctl','--device='+device, '--set-ctrl='+ctrl+'='+str(data)])
    v4l2_ctl.wait()
    del v4l2_ctl
    
def getV4LDeviceProperties(device):
    
    formats={}    
    v4l2_ctl = subprocess.Popen(['v4l2-ctl','--device='+device, '--list-formats-ext'], stdout=subprocess.PIPE)
    v4l2_ctl.wait()
    rawdata=v4l2_ctl.stdout.read().replace(' ','').replace('\t','')
    del v4l2_ctl
        
    blocks=rawdata.split('PixelFormat:\'')[1:]

    for block in blocks:
        format_name = block[:block.find('\'')]
        formats[format_name]={}
        sizes=block.split('Size:Discrete')[1:]
        for size in sizes:
            lines=size.split('\n')
            size=lines[0]
            w,h=size.split('x')
            formats[format_name][size]={'width':int(w),'height':int(h),'fps':[]}
            for line in lines[1:]:
                try:
                    fps=float(line[line.find('(')+1:line.find('fps)')])
                    formats[format_name][size]['fps'].append(str(fps)+' fps')
                except:
                    pass

    v4l2_ctl = subprocess.Popen(['v4l2-ctl','--device='+device, '-L'], stdout=subprocess.PIPE)
    v4l2_ctl.wait()
    rawdata=v4l2_ctl.stdout.readlines()
    del v4l2_ctl

    props = {'formats' : formats}
    
    for line in rawdata:
        if ' : ' in line:
            vals = line.replace('\n','').replace('\r','').split(':')
            name = vals[0][:vals[0].rfind('(')].replace(' ','').replace('\t','')
            typ  = vals[0][vals[0].rfind('(')+1:vals[0].rfind(')')]
            
            props[name]={'min':None, 'max':None, 'default':None, 'value':None, 'flags':None}

            for token in props[name]:        
                props[name][token]=_parse_token(vals[1],token)

            props[name]['type'] = typ
            if typ=='menu':
                props[name]['menu']={}
                
        elif ': ' in line:
            s = line.replace('\n','').replace('\r','').split(':')
            val = _autoType(s[0].replace(' ','').replace('\t',''))
            nme = s[1].replace(' ','').replace('\t','')
            props[name]['menu'][nme]=val
    return props
    
def _autoType(val):    
    try:
        ret=float(val)
    except:
        try:
            ret=int(val)
        except:
            ret=val
    return ret


def _parse_token(data, token):
    if token not in data:
        return None
    else:
        start = data.find(token)
        start = data.find('=',start)+1
        end   = data.find(' ',start)

        if end<0:
            val=data[start:]
        else:
            val=data[start:end]

        return _autoType(val)
