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

_VERBOSE=False

from PyQt4 import Qt, QtCore
import sys
import os
import subprocess
import numpy
import paths
import time
import cv2
import math
import scipy
from scipy import signal, ndimage

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

def trace(msg):
    if _VERBOSE:
        print(msg)

class frame(object):
    
    """
    command for args**
    rgb_fits = True;False 
    """
    
    def __init__(self, file_name, page=0, **args):

        self.url=str(file_name)
        self.name=os.path.basename(str(file_name))
        self.page=page
        self.tool_name = self.name+'-page'+str(self.page)
        self.long_tool_name = self.url+'-page'+str(self.page)   
        self.properties={}
                      
        if 'rgb_fits' in args:
            self. RGB_mode=args['rgb_fits']
        else:
            self. RGB_mode=False            
        
        if (('skip_loading' in args) and 
            (args['skip_loading']==True) and
            not ('data' in args)):
            self.width = None
            self.height = None
            self.mode = None
        else:
        
            if ('data' in args):
                    _tmp_data = Image.fromarray(args['data'])
            else:
                _tmp_data = self.open(file_name, page, PIL_priority=True)
        
            if _tmp_data==None:
                self.is_good=False
                return
            else:
                self.is_good=True
            
            self.width = _tmp_data.size[0]
            self.height = _tmp_data.size[1]
            self.mode = _tmp_data.mode
            
            if not ('data' in args):
                del _tmp_data
            
        self.alignpoints=[]
        self.angle=0
        self.offset=None
        self.setOffset([0,0])        
        
    def isRGB(self):
        return ('RGB' in self.mode)
    
    def isUsed(self):
        checked = self.getProperty('listItem').checkState()

        if checked is None:
            return False
        elif checked == 2:
            return True        
        else:
            return False
            
    def addProperty(self, key, val):
        self.properties[key]=val
        
    def getProperty(self, key):
        
        if key in self.properties:
            return self.properties[key]
        else:
            return None
            
    """
    setOffset([x_offset, y_offset]):
    """ 
    def setOffset(self,xyoff):
        
        if self.isRGB:
            self.offset=numpy.array([float(xyoff[0]),float(xyoff[1]),0,0])
        else:
            self.offset=numpy.array([float(xyoff[0]),float(xyoff[1])])

    def setAngle(self,ang):
        self.angle=ang
        
    def getData(self, asarray=False, asuint8=False, ftype=numpy.float32, PIL_priority=False):
        return self.open(self.url, self.page, asarray, asuint8, ftype, PIL_priority)
        
    def open(self, file_name, page=0, asarray=False, asuint8=False, ftype=numpy.float32, PIL_priority=False):
        file_ext = os.path.splitext(file_name)[1].lower()
        
        if numpy.dtype(ftype).kind!='f':
            raise Exception("Error: float type neede for \'ftype\' argument")
        
        if file_ext in getSupportedFormats():
            file_type = getSupportedFormats()[file_ext]
        else:
            return None
        
        #choosing among specific loaders
        if file_type == 'FITS':

            if not FITS_SUPPORT:
                #this should never happens
                return None
                
            hdu_table=pyfits.open(file_name)

            #checking for 3 ImageHDU (red, green and blue components)
            if self.RGB_mode and (len(hdu_table) >= 3):
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
                

            if self.RGB_mode and is_RGB:
                if page!=0:
                    return None
                else:
                    imh,imw=layers[0].shape
                    img = numpy.zeros((imh,imw,len(layers)))
                
                    for j in range(len(layers)):
                        img[...,j]=layers[j].data
                    
                    if asarray:
                        if asuint8:
                            return normToUint8(img)
                        else:
                            return img.astype(ftype)
                    else:
                        return Image.fromarray(normToUint8(img))

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
                                        return normToUint8(data)
                                    else:
                                        return data.astype(ftype)
                                else:
                                    return Image.fromarray(normToUint8(data))
                    
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
                
            if (page==0) and (cv2img!=None) and not(PIL_priority):
                #img = numpy.empty_like(cv2img)

                if (len(cv2img.shape) == 3) and (cv2img.shape[2]==3):
                    img=cv2img[...,(2,1,0)]
                else:
                    img=cv2img
                
                if asarray:
                    if asuint8:
                        return normToUint8(numpy.asarray(img))
                    else:
                        return (numpy.asarray(img)).astype(ftype)
                else:
                    return Image.fromarray(normToUint8(img))
            else:
                try:
                
                    img = Image.open(file_name)
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
                        return normToUint8(numpy.asarray(img))
                    else:
                        return (numpy.asarray(img)).astype(ftype)
                else:
                    return img



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

def normToUint8 (data, refit=True):
    
    if data==None:
        return None
    elif data.dtype == numpy.uint8:
        return data
    elif refit:
        norm = data.max()-data.min()
        if norm > 0:
            spec=(data-data.min())*255.0/norm
        elif norm==0:
            spec=data
        else:
            #shold never happens
            spec=-(data)*255.0/norm
            
        return spec.astype(numpy.uint8)
    elif data.max()>255:
        return (data*255.0/data.max()).astype(numpy.uint8)
    else:
        return data.astype(numpy.uint8)
    
def normToUint16 (data, refit=True):
    if data==None:
        return None
    elif data.dtype == numpy.uint16:
        return data
    elif refit:
        norm = data.max() - data.min()
        if norm > 0:
            spec=(data-data.min())*65536.0/norm
        elif norm==0:
            spec=data
        else:
            #shold never happens
            spec=-(data-data.min())*65536.0/norm
            
        return spec.astype(numpy.uint16)
    elif data.max()>65536:
        return (data*65536.0/data.max()).astype(numpy.uint16)
    else:
        return data.astype(numpy.uint16)

    
def _min(n1, n2):
    return ((n1>=n2)*n2 + (n1<n2)*n1)

def getJetColor(data):

     value = data.astype(numpy.float)

     x = ((value - value.min())/float(value.max() - value.min())).astype(numpy.float32)
     
     del value
     
     r = (4*x - 1.5).clip(0.0,1.0) - (4*x - 3.5).clip(0.0,1.0)
     g = (4*x - 0.5).clip(0.0,1.0) - (4*x - 2.5).clip(0.0,1.0)
     b = (4*x + 0.5).clip(0.0,1.0) - (4*x - 1.5).clip(0.0,1.0)

     arr=[255*r, 255*g, 255*b]
     
     del r
     del g
     del b
     
     return arr
    
def arrayToQImage(img,R=0,G=1,B=2,A=3,bw_jet=True):
    
    if type(img) != numpy.ndarray:
        raise TypeError('In module utils, in function arrayToQImage, ndarray expected as first argumrnt but '+str(type(img))+' given instead')

    #searching for NaN values
    if img.dtype.kind == 'f':
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
        arr = 255*numpy.ones((optimal_h, optimal_w, 4), numpy.uint8, 'C')
        
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
            
        arr[h:,0:,3] = 0
        arr[0:,w:,3] = 0
        
    elif (img.ndim==3) and (channels == 3):
        img2 = normToUint8(img)
        arr = 255*numpy.ones((optimal_h, optimal_w, 4), numpy.uint8, 'C')
        arr[0:h,0:w,0:3]=img2[...,(B,G,R)]
        arr[h:,0:,3] = 0
        arr[0:,w:,3] = 0
        
    elif (img.ndim==3) and (channels == 4):
        img2 = normToUint8(img)
        arr = 255*numpy.ones((optimal_h, optimal_w, 4), numpy.uint8, 'C')
        arr[0:h,0:w]=img2[...,(B,G,R,A)]
    else:
        return None

    arr=arr.astype('uint8')
    rawdata=arr.data
    del arr
    result = Qt.QImage(rawdata,optimal_w,optimal_h,Qt.QImage.Format_ARGB32_Premultiplied)
    result._raw_data=rawdata
    result._original_data=img
    return result

def logpolar(input, wmul=1, hmul=1, clip=False):

    if clip:
        max_r = min(input.shape)/2
    else:
        max_r=((input.shape[0]/2)**2 + (input.shape[1]/2)**2)**0.5
    h = hmul*max_r
    w = wmul*360.0
    coordinates = numpy.mgrid[0:h,0:w] 
    log_r = max_r*(10**((coordinates[0]/h)-1))
    angle = 2.*math.pi*(coordinates[1]/w)

    lpinput = scipy.ndimage.interpolation.map_coordinates(input,(log_r*numpy.cos(angle)+input.shape[0]/2.,log_r*numpy.sin(angle)+input.shape[1]/2.),order=3,mode='constant')

    return lpinput

def register_image(ref, img, sharp1=2, sharp2=2):
    
    trace('computing image derotation...')
    d = _derotate_mono(ref, img, sharp1)    
    angle = d[1]
    dsize = d[0].shape
    dpix = Qt.QPixmap.fromImage(arrayToQImage(d[0]))
    del d
    trace('rotation angle = '+str(angle))
    
    if angle != 0:
        derotated = scipy.ndimage.interpolation.rotate(img,angle,order=0,reshape=False,mode='constant',cval=0.0)
    else:
        derotated = img
        
    trace('computing image shift...')
    s = _correlate_mono(ref, derotated,sharp2)    
    trace('shift = '+str(s[1]))
    shift = s[1]

    return s[0],shift,angle


def _derotate_mono(im1, im2, sharpening=2):
    
    f1 = _FFT_mono(im1)
    f2 = _FFT_mono(im2)
    
    m1 = numpy.fft.fftshift(abs(f1))
    del f1
    
    m2 = numpy.fft.fftshift(abs(f2))
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
    
    r=numpy.fft.ifftshift(r)
            
    half = r.shape[1]/2
        
    r = r[...,0:half] + r[...,half:]
    
    half = r.shape[1]/2
    
    c = numpy.empty_like(r)
    
    c[...,0:half] = r[...,half:]
    c[...,half:]  = r[...,0:half]
    
    del r
    
    if sharpening > 0:
        c = ndimage.gaussian_filter(c,sharpening)
    
    rmax=(numpy.unravel_index(c.argmax(),c.shape)[1]*180.0/c.shape[1]) - 90
    
    return c,rmax


def _correlate_mono(im1, im2, sharpening=1):
    
    n = numpy.zeros_like(im1)

    n[0:im2.shape[0],0:im2.shape[1]]=im2
    
    f1 = _FFT_mono(im1)
    f2 = _FFT_mono(n)
    
    f = (f1*f2.conj())/abs(f1*f2)
    
    del f1
    del f2
    
    r = _IFT_mono(f)
    r[0,0]=r.min()-1

    del f
    
    r=numpy.fft.ifftshift(r)

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
    
    rmax=numpy.unravel_index(r.argmax(),r.shape)
    
    #subpixel alignment
    #subw=int(r.shape[1]/(2*numpy.log2(r.shape[1])))
    #subh=int(r.shape[0]/(2*numpy.log2(r.shape[0])))
    
    if ((rmax[0] < 10) or (rmax[0] > (r.shape[0]-10)) or
        (rmax[1] < 10) or (rmax[1] > (r.shape[1]-10))):
        #this is a very bad situation!
        trace("Shift is too big for sub-pixe alignment")
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

    zoom_level=10.0

    sub_region=r[y_start:y_end,x_start:x_end]
    sub_region=scipy.ndimage.zoom(sub_region,zoom_level,order=5)

    submax = numpy.unravel_index(sub_region.argmax(),sub_region.shape)
    del sub_region
    
    pos_max = (y_start+submax[0]/zoom_level, x_start+submax[1]/zoom_level)

    shift=[center[1]+x_corr-pos_max[1],center[0]+y_corr-pos_max[0]]

    return (r,shift)

#This function a test is for future de-blurring feature
def cepstrum(img):

    result = []

    for l in range(img.shape[2]):
        
        result.append(cepstrum_mono(img[...,l],steps,perc,roll_off,rexp))

    final = numpy.ndarray((len(result[0]),len(result[0][0]),len(result)))
    
    for i in range(len(result)):
        final[...,i]=result[i]
    return final 

#This function a test is for future de-blurring feature
def cepstrum_mono(img):

    #this is the cepstrum
    cep = _IFT_mono(numpy.log(_FFT_mono(img)))

    #now a better look!    
    h,w = cep.shape
    
    h-=1
    w-=1
    
    cep[0,0]=cep.max()
    
    scep = numpy.fft.ifftshift(cep)
    norm = (scep - scep.min())/(scep.max()-scep.min())
    ecep = numpy.exp(2/(norm+1))    
    
    ecep = ecep-ecep.mean()
    
    return ecep.clip(-ecep.max(),ecep.max())

#This function a test is for future de-blurring feature
def getDefocusCircleRadius(img):
    
    if len(img.shape)==3:
        cep = cepstrum_mono(img.sum(2))
    elif len(img.shape)==2:
        cep = cepstrum_mono(img)
    
    i = cv2.erode(cv2.dilate(cep,None),None)
    
    i = scipy.ndimage.gaussian_filter(i,0.8)
   
    c = normToUint8(i)
    
    del i
    
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
                if best == None:
                    best = difference
                    best_radius = r
                elif difference <= best:
                    best_radius = r
                    
        cv2.circle(cep,(int(cx),int(cy)),best_radius,cep.min())
        
        return (best_radius,cep)

def spectrum(fft, shift=False):
    
    if shift:
        ff = numpy.fft.fftshift(fft)
    else:
        ff = fft        

    return abs(ff)**2
    
def magnitude(fft, shift=True):
    mag = spectrum(fft,shift)**0.5
    spec=numpy.log10(mag+1)

    return spec

    
def generateCosBell(w,h, roll_off=0.4):
    
    x,y=numpy.meshgrid(numpy.arange(w),numpy.arange(h))
    x=x*1.0/x.max() - 0.5
    y=y*1.0/y.max() - 0.5
    cb=(numpy.cos(math.pi*x)*numpy.cos(math.pi*y))**0.5

    return cb

def _FFT_mono(img):

    h,w=img.shape[0:2]
    
    cx = int(w/2)
    cy = int(h/2)
    
    optimal_w = cv2.getOptimalDFTSize(w) 
    optimal_h = cv2.getOptimalDFTSize(h)

    real=cv2.copyMakeBorder(img,0, optimal_h-h, 0, optimal_w-w, cv2.BORDER_CONSTANT)
    cmplx = numpy.zeros((optimal_h,optimal_w,2))
    cmplx[...,0]=real
    del real
    img_fft=cv2.dft(cmplx)
    
    return img_fft[...,0]+1j*img_fft[...,1]

def _IFT_mono(fft):

    imh,imw = fft.shape

    cmplx = numpy.zeros((imh,imw,2))
    cmplx[...,0]=fft.real
    cmplx[...,1]=fft.imag
    img_ift=cv2.idft(cmplx)
    
    return img_ift[...,0]

def _FFT_RGB(img):

    if type(img) != numpy.ndarray:
        return False

    result = []
        
    for l in range(img.shape[2]):
        
        result.append(_FFT_mono(img[...,l]))

    final = numpy.ndarray((len(result[0]),len(result[0][0]),len(result)), dtype='complex128')
    
    for i in range(len(result)):
        final[...,i]=result[i]
    return final 

def _IFT_RGB(fft):

    img = numpy.zeros_like(fft)
    res = numpy.zeros_like(fft)
    for l in range(fft.shape[2]):
        img[...,l] = _IFT_mono(fft[...,l])

    rel = img.real

    return rel #((rel-rel.min())*255/rel.max()).astype('uint8')

#This function a test is for future de-blurring feature
def convolve(img, fltr):

    i2=fltr.astype('float64')/fltr.max()
    #img = img.astype('float64')/img.max()
    
    f1 = _FFT_RGB(img)
    f2 = _FFT_RGB(i2)

    del i2
    
    f1=(f1*f2)
    
    del f2
    
    rf = _IFT_RGB(f1)
    
    del f1
    
    return rf

#This function a test is for future de-blurring feature
def deconvolve(img, fltr):
    
    i2=fltr.astype('float64')/fltr.max()
    #img = img.astype('float64')/img.max()

    f1 = _FFT_RGB(img)
    f2 = _FFT_RGB(i2)

    del i2

    f1=(f1/(f2+0.00000001))
    
    del f2
    
    rf = _IFT_RGB(f1)
    
    del f1
    
    return rf

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
    
def getV4LFps(device):
    v4l2_ctl = subprocess.Popen(['v4l2-ctl','--device='+device, '--get-parm'], stdout=subprocess.PIPE)
    v4l2_ctl.wait()
    rawdata=v4l2_ctl.stdout.read().replace(' ','').replace('\t','')
    
    pos1 = rawdata.find('Framespersecond:') + 16
    pos2 = rawdata.find('(',pos1)
    
    fps = rawdata[pos1:pos2]
    return float(fps)
    
    
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
