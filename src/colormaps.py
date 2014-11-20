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
import numpy as np

def _getStairData(data,clipval):    
    return (data>clipval)*1.0

def _getGateData(data,lc,hc):
    return _getStairData(data,lc) - _getStairData(data,hc)

def _getNormalizedColors(data,fit_levels=True, lrange=None):
    value = data.astype(np.float)
    minv,maxv = utils.getMinMax(data,fit_levels,lrange)
    
    if maxv==minv:
        x = (value/float(2*maxv)).astype(np.float32)
    else:
        x = ((value - minv)/float(maxv-minv)).astype(np.float32)
    
    return x

# parent object for all colormaps
class ColorMap(object):
    
    def __init__(self,name, mapfunc):
        self.name=name
        self.mapfunc=mapfunc
        
    def mapData(self, data, fit_levels=True, lrange=None):
        x = _getNormalizedColors(data, fit_levels, lrange)
        return self.mapfunc(x)
    
def mapFuncGray(x):
    return [255*x,255*x,255*x]

def mapFuncJet(x):
    x4=4*x
    
    r = (x4 - 1.5).clip(0.0,1.0) - (x4 - 3.5).clip(0.0,1.0)
    g = (x4 - 0.5).clip(0.0,1.0) - (x4 - 2.5).clip(0.0,1.0)
    b = (x4 + 0.5).clip(0.0,1.0) - (x4 - 1.5).clip(0.0,1.0)
         
    return [255*r, 255*g, 255*b]

def mapFuncRGB(x):
    x3=3.0*x
    
    r = (x3)
    g = (x3-1)
    b = (x3-2)
    
    r*=_getGateData(r,0,1)
    g*=_getGateData(g,0,1)
    b*=_getGateData(b,0,1)
         
    return [255*r, 255*g, 255*b]

def mapFuncBGR(x):    
    x3=3.0*x
    
    r = (x3-2)
    g = (x3-1)
    b = (x3)
    
    r*=_getGateData(r,0,1)
    g*=_getGateData(g,0,1)
    b*=_getGateData(b,0,1)
         
    return [255*r, 255*g, 255*b]

def mapFuncHeat(x):    
    x3=3.0*x
    
    r = x3.clip(0.0,1.0)
    g = x.clip(0.0,1.0)
    b = (x3 - 2).clip(0.0,1.0)
         
    return [255*r, 255*g, 255*b]

def mapFuncRed(x):
    x0=np.zeros_like(x)
    
    r = (x).clip(0.0,1.0)
    g = x0
    b = x0
    
    return [255*r, 255*g, 255*b]
    
def mapFuncGreen(x):
    x0=np.zeros_like(x)
    
    r = x0
    g = (x).clip(0.0,1.0)
    b = x0
    
    return [255*r, 255*g, 255*b]

def mapFuncBlue(x):
    x0=np.zeros_like(x)
    
    r = x0
    g = x0
    b = (x).clip(0.0,1.0)
         
    return [255*r, 255*g, 255*b]


def getColormappedImage(img,cmapid,fit_levels=None,levels_range=None):
    cmap = getColormap(cmapid)
    return cmap.mapData(img,fit_levels,levels_range)

gray  = ColorMap("Gray", mapFuncGray)
jet   = ColorMap("Jet",mapFuncJet)
heat  = ColorMap("Heat",mapFuncHeat)
red   = ColorMap("Red",mapFuncRed)
green = ColorMap("Green",mapFuncGreen)
blue  = ColorMap("Blue",mapFuncBlue)
rgb   = ColorMap("RGB",mapFuncRGB)
brg   = ColorMap("BRG",mapFuncBGR)

COLORMAPS={0:gray,
           1:jet,
           2:heat,
           3:red,
           4:green,
           5:blue,
           6:rgb,
           7:brg}

def getColormapName(idx):
    return COLORMAPS[int(idx)].name

def getColormap(idx):
    return COLORMAPS[int(idx)]

def getColormapId(cmap):
    for item in COLORMAPS.items():
        if cmap == item[1]:
            return item[0]
    return -1