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

PROGRAM = paths.PROGRAM_NAME
PROGRAM_NAME = paths.PROGRAM_NAME



GRAY_COLORTABLE = [~((i + (i<<8) + (i<<16))) for i in range(255,-1,-1)]

def arrayToQImage(img,R=0,G=1,B=2,A=3):
    if type(img) != numpy.ndarray:
        raise TypeError('ndarray expected, '+str(type(img))+' given instead')
    
    h, w, channels = img.shape
    
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
        fmt = Qt.QImage.Format_Indexed8
        arr = numpy.zeros((optimal_h, optimal_w), numpy.uint8, 'C')
        arr[h:w]=img
    elif (img.ndim==3) and (channels == 3):
        fmt = Qt.QImage.Format_RGB888
        arr = numpy.zeros((optimal_h, optimal_w, 3), numpy.uint8, 'C')
        arr[0:h,0:w,0] = img[...,R]
        arr[0:h,0:w,1] = img[...,G]
        arr[0:h,0:w,2] = img[...,B]    
    elif (img.ndim==3) and (channels == 4):
        fmt = Qt.QImage.Format_ARGB32
        arr = numpy.zeros((optimal_h, optimal_w, 4), numpy.uint8, 'C')
        arr[0:h,0:w,0] = img[...,R]
        arr[0:h,0:w,1] = img[...,G]
        arr[0:h,0:w,2] = img[...,B]
        arr[0:h,0:w,3] = img[...,A]
    else:
        return None

    arr=arr.astype('uint8')
    result = Qt.QImage(arr.data,optimal_w,optimal_h,fmt)
    result._raw_data=arr

    if channels == 1:
        image.setColorTable(COLORTABLE)

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
