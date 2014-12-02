# lxnstack is a program to align and stack atronomical images
# Copyright (C) 2013-2014  Maurizio D'Addona <mauritiusdadd@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""
 The informations to wirte this code were taken form:

 (1) http://lclevy.free.fr/cr2/ => Canon (TM) CR2 specifications

 (2)  Lossless Jpeg and Huffman decoding:
      http://www.impulseadventure.com/photo/jpeg-huffman-coding.html

 (3) Lossless Jpeg information
     http://www.digitalpreservation.gov/formats/fdd/fdd000334.shtml

 (4) Dave Coffin's raw photo decoder
     http://www.cybercom.net/~dcoffin/dcraw/
"""

from PyQt4 import Qt, QtCore
import numpy as np
import struct
import sys
import gc

IS_PYTHON_3 = (sys.version_info[0] > 2)

if IS_PYTHON_3:
    xrange = range

EXTENSION = {'.cr2': 'CR2'}

ImageWidth = 256
ImageLength = 257
ImageDescription = 270
Make = 271
Model = 272
StripOffset = 273
StripBytesCount = 279
EXIF = 34665
CR2Slice = 50752
ExposureTime = 33434
Makernote = 37500

CameraSettings = 0x0001
FocusInfo = 0x0002
ImageType = 0x0006
SensorInfo = 0x00e0
ColorBalance = 0x4001
BlackLevel = 0x4008
VignettingCorrection = 0x4015

DhtMarker = b'\xff\xc4'
StartOfFrameMarker = b'\xff\xc3'
StartOfScanMarker = b'\xff\xda'
StartOfImageMarker = b'\xff\xd8'
EndOfImageMarker = b'\xff\xd9'

MAX_HUFFMAN_BITS = 16
MIN_BUFFER_LEN = 2*MAX_HUFFMAN_BITS

decodestring = '>'+'Q'*16  # 16 * 8 bytes
tokenlen = struct.calcsize(decodestring)
bittokenlen = tokenlen*8


def ba2bs2(b):
    m = map('{0:08b}'.format, b)
    s = ''.join(m)
    return s


def ba2bs(b):
    d = struct.unpack(decodestring, b)
    m = map('{0:064b}'.format, d)
    s = ''.join(m)
    return s


def _reconstructData(byte_order, *bytesdata):

    result = 0

    if byte_order == b'II':
        for b in range(len(bytesdata)):
            data = bytesdata[b]
            if type(data) == str:
                data = ord(data)
            offs = b * 8
            result += data << offs
    else:
        for b in range(len(bytesdata)):
            data = bytesdata[-b]
            if type(data) == str:
                data = ord(data)
            offs = b * 8
            result += data << offs
    return result


def _reconstructDataFromString(byte_order, bytesdata):

    result = 0
    if byte_order == b'II':
        for b in range(len(bytesdata)):
            data = bytesdata[b]
            if type(data) == str:
                data = ord(data)
            offs = b * 8
            result += data << offs
    else:
        for b in range(len(bytesdata)):
            data = bytesdata[b]
            if type(data) == str:
                data = ord(data)
            offs = (len(bytesdata) - b - 1) * 8
            result += data << offs
    return result


def _getTypeSize(ind):

    if ind == 1:     # byte
        return 1
    elif ind == 2:   # ascii
        return -1
    elif ind == 3:   # short
        return 2
    elif ind == 4:   # long
        return 4
    elif ind == 5:   # rational
        return 8
    elif ind == 6:   # signed byte
        return 1
    elif ind == 7:   # undefined
        return -2
    elif ind == 8:   # signed short
        return 2
    elif ind == 9:   # signed long
        return 4
    elif ind == 10:  # signed rational
        return 8
    elif ind == 11:  # float
        return 4
    elif ind == 12:  # double
        return 8


def _getExifValue(data, data_type):

    if data_type == 1:
        return np.ubyte(data)
    elif data_type == 2:
        return str(data)
    elif data_type == 3:
        return np.uint16(data)
    elif data_type == 4:
        return np.uint32(data)
    elif data_type == 5:
        n = np.uint32(0xffffffff & data)
        d = np.uint32(((0xffffffff << 32) & data) >> 32)
        if n == 0:
            return 0
        elif d == 0:
            return "nan"
        else:
            return (n, d)
    elif data_type == 6:
        return np.byte(data)
    elif data_type == 7:
        return data
    elif data_type == 8:
        return np.int16(data)
    elif data_type == 9:
        return np.int32(data)
    elif data_type == 10:
        n = np.int32(0xffffffff & data)
        d = np.int32(((0xffffffff << 32) & data) >> 32)
        if n == 0:
            return 0
        elif d == 0:
            return "nan"
        else:
            return (n, d)
    elif data_type == 11:
        return np.float32(data)
    elif data_type == 12:
        return np.float64(data)
    else:
        return data


def getPredictorValue(psv, px_left, px_top, px_topleft):

    # NOTE: From the (3) Lossless JPEG specifications
    #       and (4) dcraw source code the following
    #       predictors for a pixel P can be found:
    #
    #              COLOR COMPONENT X
    #
    #         ... +--------+--------+ ...
    #             |        |        |
    #             |top_left|  top   |
    #             |        |        |
    #         ... +--------+--------+ ...
    #             |        |        |
    #             |  left  |   P    |
    #             |        |        |
    #         ... +--------+--------+ ...
    #
    #  ScanTable.psv = 1 --> predictor = left pixel
    #  ScanTable.psv = 2 --> predictor = top pixel
    #  ScanTable.psv = 3 --> predictor = top_left pixel
    #  ScanTable.psv = 4 --> predictor = left + top - top_left
    #  ScanTable.psv = 5 --> predictor = left + ((top - top_left) >> 1)
    #  ScanTable.psv = 6 --> predictor = top + ((left - top_left) >> 1)
    #  ScanTable.psv = 7 --> predictor = (top + left)>>1

    if psv == 1:
        pred = px_left
    elif psv == 2:
        pred = px_top
    elif psv == 3:
        pred = px_topleft
    elif psv == 4:
        pred = px_left + px_top - px_topleft
    elif psv == 5:
        pred = px_left + ((px_top - px_topleft) >> 1)
    elif psv == 6:
        pred = px_top + ((px_left - px_topleft) >> 1)
    elif psv == 7:
        pred = (px_top - px_left) >> 1
    else:
        pred = 0

    return pred


class Sensor(object):

    def __init__(self, data=(0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0)):
        self.width = data[1]
        self.height = data[2]
        self.left_border = data[5]
        self.top_border = data[6]
        self.right_border = data[7]
        self.bottom_border = data[8]
        self.black_mask_left_border = data[9]
        self.black_mask_top_border = data[10]
        self.black_mask_right_border = data[11]
        self.black_mask_bottom_border = data[12]

    def __str__(self):
        s = 'Sensor Width : ' + str(self.width) + '\n'
        s += 'Sensor Height : ' + str(self.height) + '\n'
        s += 'Border Top : ' + str(self.top_border) + '\n'
        s += 'Border Bottom : ' + str(self.bottom_border) + '\n'
        s += 'Border Left : ' + str(self.left_border) + '\n'
        s += 'Border Right : ' + str(self.right_border) + '\n'
        s += 'Black Mask Top : ' + str(self.black_mask_top_border) + '\n'
        s += 'Black Mask Bottom : ' + str(self.black_mask_bottom_border) + '\n'
        s += 'Black Mask Left : ' + str(self.black_mask_left_border) + '\n'
        s += 'Black Mask Right : ' + str(self.black_mask_right_border) + '\n'

        return s


class HuffmanTable(object):

    def __init__(self, data=None):

        self.codes = {}

        # bitmasks for faster computation
        self.masks = []
        for i in range(MAX_HUFFMAN_BITS):
            self.masks.append((1 << i) - 1)

        if (data is not None):

            if data[0:2] != DhtMarker:
                raise SyntaxError("Invalid Huffman Talbe")

            offset = 4
            while offset < len(data):

                info = data[offset]
                index = info & 0b00000111
                type = info & 0b00010000
                symbols = {0: []}
                count = 0

                if (info & 0b11110000) != 0:
                    raise SyntaxError("Invalid Huffman Talbe")

                for i in range(MAX_HUFFMAN_BITS):
                    current = data[offset+1+i]
                    symbols[i+1] = [None] * current

                for i in range(MAX_HUFFMAN_BITS):
                    for j in range(len(symbols[i+1])):
                        current = data[offset+0x11+count]
                        symbols[i+1][j] = current
                        count += 1
                offset = offset + 0x11 + count

                self.codes[index, type] = self.generateCodes(symbols)

    def __repr__(self):

        s = "\n"
        s += "-----------------------------\n"
        s += "|       Huffman Table       |\n"
        s += "-----------------------------\n"

        keyslst = sorted(self.codes.keys())
        for kk in keyslst:
            s += "|  Index |        0"+str(kk[0])+"        |\n"
            if kk[1] == 0:
                s += "|  Type  |        DC        |\n"
            else:
                s += "|  Type  |        AC        |\n"
            s += "-----------------------------\n"
            s += "|       BITS       |  CODE  |\n"
            s += "-----------------------------\n"

            keyslst2 = sorted(self.codes[kk].keys())
            for i in keyslst2:
                codes = self.codes[kk][i]
                s += "| {0:s}  |  0x{1:02x}  |\n".format(i.rjust(15), codes)
            s += "-----------------------------\n"
        return s

    def generateCodes(self, sym):

        branches = [['']]
        leafs = []
        current_count = 0
        row = 0
        codes = {}

        totalcodes = 0
        for cod in sym.values():
            totalcodes += len(cod)

        # finding last non empty row
        last_non_null = 0
        for i in sym.keys():
            if len(sym[i]) != 0:
                last_non_null = i

        while (len(leafs) < totalcodes) and (row <= last_non_null):

            lst = []
            current_count = 0
            current_max = len(sym[row+1])
            for p in branches[row]:
                for j in range(2):
                    i = p + str(j)
                    if current_count < current_max:
                        leafs.append(i)
                        codes[i] = sym[row+1][current_count]
                        current_count += 1
                    else:
                        lst.append(i)
            row += 1
            branches.append(lst)

        del branches
        del leafs
        return codes


class FrameTable(object):

    def __init__(self, data):

        self.bits = data[4]
        self.height = _reconstructDataFromString(b'MM', data[5:7])
        self.width = _reconstructDataFromString(b'MM', data[7:9])
        self.components = data[9]
        self.componentsPropetries = {}

        for i in range(self.components):
            index = data[10+3*i]
            hv = data[10+3*i+1]
            quant = data[10+3*i+2]
            pdic = {'index': index,
                    'h': (hv & 0b11110000) >> 4,
                    'v': (hv & 0b00001111),
                    'qunatization_table': quant
                    }
            self.componentsPropetries[i] = pdic

    def __repr__(self):
        s = '\n'
        s += "-----------------------------\n"
        s += "|        Frame Table        |\n"
        s += "-----------------------------\n"
        s += "|                            \n"
        s += "| bits : " + str(self.bits) + "\n"
        s += "| width : " + str(self.width) + "\n"
        s += "| height : " + str(self.height) + "\n"
        s += "| components # : " + str(self.components) + "\n"
        s += "-----------------------------\n"
        s += "|         Components        |\n"
        s += "-----------------------------\n"
        s1 = str(self.componentsPropetries)
        s1 = s1.replace(': {', ' -> ')
        s1 = s1.replace('{', '|')
        s1 = s1.replace('},', '\n|')
        s1 = s1.replace('}', '\n')
        s1 = s1.replace(' ', '')
        s1 = s1.replace(',', '; ')
        s1 = s1.replace(':', ' = ')
        s += s1
        s += "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"
        return s


class ScanTable(object):

    def __init__(self, data):

        self.components = data[4]
        self.componentsPropetries = {}
        self.psv = data[4+2*self.components+1]
        self.ssending = data[4+2*self.components+2]
        self.succ_approx = data[4+2*self.components+3]

        for i in range(self.components):
            index = data[5+2*i]
            da = data[5+2*i+1]
            pdic = {'index': index,
                    'DC': (da & 0b1111000) >> 4,
                    'AC': (da & 0b00001111),
                    }
            self.componentsPropetries[i] = pdic

    def __repr__(self):
        s = '\n'
        s += "-----------------------------\n"
        s += "|         Scan Table        |\n"
        s += "-----------------------------\n"
        s += "|                            \n"
        s += "| components # : " + str(self.components) + "\n"
        s += "| P.S.V.: " + str(self.psv) + "\n"
        s += "| SS ending: " + str(self.ssending) + "\n"
        s += "| SA : " + str(self.succ_approx) + "\n"
        s += "-----------------------------\n"
        s += "|         Components        |\n"
        s += "-----------------------------\n"
        s1 = str(self.componentsPropetries)
        s1 = s1.replace(': {', ' -> ')
        s1 = s1.replace('{', '|')
        s1 = s1.replace('},', '\n|')
        s1 = s1.replace('}', '\n')
        s1 = s1.replace(' ', '')
        s1 = s1.replace(',', '; ')
        s1 = s1.replace(':', ' = ')
        s += s1
        s += "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"
        return s


class BitStream(object):

    def __init__(self, data):

        self._bdata = bytearray(data)
        self._bitindex = 0
        self._byteindex = 0

    def seek(self, bits, pos=1):
        if pos == 0:
            pass
        elif pos == 1:
            if bits != 0:
                tot = self.tellbits() + bits
                if tot < 0:
                    self._byteindex = 0
                    self._bitindex = 0
                else:
                    self._byteindex = tot / 8
                    self._bitindex = tot % 8
        elif pos == 2:
            pass
        else:
            pass

    def tell(self):
        return self._byteindex + float(self._bitindex) / 10

    def tellbits(self):
        return self._byteindex * 8 + self._bitindex

    def getBits(self, total_bits=1):

        available_bits = 8 - self._bitindex
        val = self._bdata[self._byteindex] & ((1 << available_bits) - 1)

        if total_bits <= available_bits:
            self._bitindex += total_bits
            if self._bitindex == 8:
                self._bitindex = 0
                self._byteindex += 1
                return val
            else:
                return val >> (8 - self._bitindex)
        else:
            total_bits -= available_bits
            oldpos = self._byteindex + 1
            nbytes = 1+total_bits / 8

            self._bitindex = total_bits % 8
            self._byteindex += nbytes

            for i in self._bdata[oldpos:oldpos+nbytes]:
                val = (val << 8) + i
            available_bits = 8 - self._bitindex
            return val >> available_bits


class QCR2Image(QtCore.QObject):

    decodingProgressChanged = QtCore.pyqtSignal(int)
    decodingStarted = QtCore.pyqtSignal()
    decodingEnded = QtCore.pyqtSignal()
    opened = QtCore.pyqtSignal()
    closed = QtCore.pyqtSignal()
    imageReady = QtCore.pyqtSignal()

    format = "CR2"
    format_description = "Canon Raw format version 2"

    def __init__(self, fname=None):

        QtCore.QObject.__init__(self)

        self.version = 0
        self.isOpened = False
        self._canceled = False
        self.__decoding_progress = 0

        if fname is not None:
            self.filename = fname
            self.fp = open(self.filename, 'rb')
            self.open()

    def __del__(self):
        self.close()

    def cancel(self):
        self._canceled = True

    def load(self, fname=None, ifd=3):
        if (not self.isOpened):
            if fname is None:
                raise SyntaxError("unknown file name")
            else:
                self.filename = fname
                self.open()
        if ifd == 3:
            uncropped = self.decodeRawImage()

            bbord = self.Sensor.bottom_border + (self.Sensor.bottom_border % 2)
            tbord = self.Sensor.top_border - (self.Sensor.top_border % 2)
            lbord = self.Sensor.left_border - (self.Sensor.left_border % 2)
            rbord = self.Sensor.right_border + (self.Sensor.right_border % 2)

            #  +---------------------------------------------+ \
            #  |                 TOP BORDER                  | |
            #  |      _________________________________      | |
            #  |  L  |    ^                            |  R  | S
            #  |  E  |    |                            |  I  | E
            #  |  F  |    H                            |  G  | N
            #  |  T  |    E                            |  H  | S
            #  |     |    I                            |  T  | O
            #  |  B  |    G          IMAGE             |     | R
            #  |  O  |    H                            |  B  |
            #  |  R  |    T                            |  O  | H
            #  |  D  |    |                            |  R  | E
            #  |  E  |<---+----------WIDTH------------>|  D  | I
            #  |  R  |    |                            |  E  | G
            #  |     |____V____________________________|  R  | H
            #  |                                             | T
            #  |                BOTTOM BORDER                | |
            #  +---------------------------------------------+ /
            #  \----------------SENSOR WIDTH-----------------/

            if uncropped is not None:
                image = uncropped[tbord:bbord, lbord:rbord].copy()
            else:
                image = None

            gc.collect()
            del uncropped

        elif ifd == 1:
            image = self.extractEmbeddedJpeg()

        if image is not None:
            self.imageReady.emit()

        return image

    def open(self):

        # check header
        if IS_PYTHON_3:
            header = self.fp.read(0x0f)
        else:
            header = bytearray(self.fp.read(0x0f))

        byteorder = header[0:2]
        self.byteorder = byteorder

        # mode setting
        if byteorder == b'II':
            self.mode = "L;16"
        elif byteorder == b'MM':
            self.mode = "L;16B"
        else:
            raise SyntaxError("unknown endian format")

        if (header[2:3] != b'*') or (header[8:10] != b'CR'):
            raise SyntaxError("not a CR2 image file")

        major_version = str(header[0x0a])  # should be 2
        minor_version = str(header[0x0b])  # should be 0

        # and this should be 2.0
        self.version = float(major_version + '.' + minor_version)

        ifd0_offset = _reconstructDataFromString(byteorder, header[4:8])
        ifd3_offset = _reconstructDataFromString(byteorder, header[12:16])

        # the IFD0 for sensor information
        self.IFD0 = self._readIfd(byteorder, ifd0_offset)

        if (EXIF not in self.IFD0.keys()):
            raise SyntaxError("not a CR2 image file")

        exif_offset = self.IFD0[EXIF]

        self.EXIF = self._readIfd(byteorder, exif_offset)

        if (Makernote not in self.EXIF.keys()):
            raise SyntaxError("not a CR2 image file")

        self.MAKERNOTES = self._readIfd(byteorder, self.EXIF[Makernote][2])

        self.Sensor = Sensor(self.MAKERNOTES[SensorInfo])

        bbord = self.Sensor.bottom_border + (self.Sensor.bottom_border % 2)
        tbord = self.Sensor.top_border - (self.Sensor.top_border % 2)
        lbord = self.Sensor.left_border - (self.Sensor.left_border % 2)
        rbord = self.Sensor.right_border + (self.Sensor.right_border % 2)

        self.size = (rbord - lbord, bbord - tbord)

        # the RAW IFD
        self.IFD3 = self._readIfd(byteorder, ifd3_offset)

        if (CR2Slice not in self.IFD3.keys()):
            self.CR2SLICES = (self.IFD3[StripOffset],
                              0,
                              self.IFD3[StripBytesCount],
                              -1,
                              0)
        else:
            self.CR2SLICES = (self.IFD3[StripOffset],
                              self.IFD3[CR2Slice][0],
                              self.IFD3[StripBytesCount],
                              self.IFD3[CR2Slice][1],
                              self.IFD3[CR2Slice][2])

        self.isOpened = True
        self.opened.emit()

    def close(self):
        del self.CR2SLICES
        del self.IFD3
        del self.IFD0
        del self.Sensor
        del self.MAKERNOTES
        del self.EXIF
        self.fp.close()
        self.closed.emit()

    def extractEmbeddedJpeg(self):
        self._canceled = False
        self.decodingStarted.emit()
        self.decodingProgressChanged.emit(100)
        self.decodingEnded.emit()
        pass  # TODO

    def decodeRawImage(self):
        self._canceled = False
        self.decodingStarted.emit()

        self.fp.seek(self.CR2SLICES[0], 0)
        if IS_PYTHON_3:
            rawdata = self.fp.read(self.CR2SLICES[2])
        else:
            rawdata = bytearray(self.fp.read(self.CR2SLICES[2]))

        if rawdata[-2:] != EndOfImageMarker:
            errmsg = "EOI marker does not correspond to end of image"
            raise SyntaxError(errmsg)
        else:
            image_data_end = len(rawdata) - 2

        if rawdata[0:2] != StartOfImageMarker:
            errmsg = "SOI marker does not correspond to start of image"
            raise SyntaxError(errmsg)
        else:
            image_data_start = None

        hts = {}
        # parsing jpeg codes
        i = rawdata.find(b'\xff', 0)

        while (i >= 0):
            # JEPG uses Big Endian, regardless of the file byte ordering
            sect_len = _reconstructDataFromString('MM', rawdata[i+2:i+4]) + 2
            if rawdata[i+1] == b'\x00':
                pass
            elif rawdata[i:i+2] == StartOfImageMarker:
                pass
            elif rawdata[i:i+2] == DhtMarker:
                h = HuffmanTable(rawdata[i:i+sect_len])
                hts[DhtMarker] = h
            elif rawdata[i:i+2] == StartOfFrameMarker:
                hts[StartOfFrameMarker] = FrameTable(rawdata[i:i+sect_len])
            elif rawdata[i:i+2] == StartOfScanMarker:
                hts[StartOfScanMarker] = ScanTable(rawdata[i:i+sect_len])
                image_data_start = i + sect_len
            elif rawdata[i:i+2] == EndOfImageMarker:
                pass
            i = rawdata.find(b'\xff', i+1)

        if type(rawdata) == bytes:
            imdata = rawdata[image_data_start:image_data_end]
            imdata = imdata.replace(b'\xff\x00', b'\xff')
        else:
            imdata = rawdata[image_data_start:image_data_end]
            imdata = imdata.replace('\xff\x00', '\xff')
            imdata = bytearray(imdata)

        del rawdata

        img = self._decompressLosslessJpeg(imdata, hts)

        del imdata

        return img

    def _decompressLosslessJpeg(self, data, hts):

        # NOTE: as written in (1) the raw data is encoded as an image
        #       whith 2 (or 4) components, and have the same height of
        #       raw image but only 1/#components of its width
        components = hts[StartOfFrameMarker].components
        imagew = hts[StartOfFrameMarker].width * components
        imageh = hts[StartOfFrameMarker].height

        if (imagew != self.Sensor.width) or (imageh != self.Sensor.height):
            print("Warning: probably corrupted data!")

        # some usefull constants and variables
        dataend = len(data)
        buff = ba2bs(data[0:tokenlen])
        lenbuff = len(buff)
        datapos = tokenlen
        dataleft = dataend-tokenlen
        half_max_val = (1 << (hts[StartOfFrameMarker].bits - 1))
        predictor = [half_max_val] * components
        psv = hts[StartOfScanMarker].psv

        # computing the size of slices
        if self.CR2SLICES[1] == 0:
            slices_size = self.imagew
        else:
            slices_size = []
            for i in range(self.CR2SLICES[1]):
                slices_size.append(self.CR2SLICES[3])
            slices_size.append(self.CR2SLICES[4])

        # NOTE: For some unknown reason the code runs much more faster
        #       using python2 instead of python3, probably because
        #       python3 does more checks during execution.

        # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< #
        # NOTE: most of the folloding section is needed to speedup
        #       the decompression process because accessing a local
        #       list or rictionary is faster then accessing class
        #       elements or using the len() function.

        masks = hts[DhtMarker].masks[:]
        codes = hts[DhtMarker].codes[0, 0]
        same_tables = True

        for c in hts[DhtMarker].codes.values():
            same_tables &= (c == codes)

        # If the tables are equal, then switching between them
        # is only a waste of time and only one table will be used
        if same_tables:
            kdic = sorted(codes.keys())
            keys_len = {}
            for k in kdic:
                keys_len[k] = len(k)
        else:
            i = 0
            keys_lens = {}
            kdics = {}
            codes = hts[DhtMarker].codes
            indexes = list(codes.keys())
            num_of_indexes = len(indexes)

            # Sorting keys for a faster research
            for c in indexes:
                kdics[c] = sorted(codes[c].keys())
                keys_lens[c] = {}
                for k in kdics[c]:
                    keys_lens[c][k] = len(k)

            kdic = kdics[indexes[0]]
            keys_len = keys_lens[indexes[0]]
        # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< #

        """
        As written in CR2 specifications(1), the image is divided into
        several vertical slices (from lef to right) and then each slice
        is compressed by an huffman encoder.

        Here is an example of an image divided into 3 slices:

                      [a] RAW IMAGE FROM SENSOR
        +--------------------------------------------------+
        |<...............<:::::::::::::::<=================|
        |................::::::::::::::::==================|
        |................::::::::::::::::==================|
        |................::::::::::::::::==================|
        |................::::::::::::::::==================|
        |....SLICE  1....::::SLICE  2::::=====SLICE  3=====|
        |................::::::::::::::::==================|
        |................::::::::::::::::==================|
        |................::::::::::::::::==================|
        |................::::::::::::::::==================|
        |................::::::::::::::::==================|
        |...............>:::::::::::::::>=================>|
        +--------------------------------------------------+

                                  |
                                  V

                       [b] COMPRESSION PROCESS
                   +-----------------+
                   | HUFFMAN ENCODER |
        <011011010 |                 |..> <SLICE2> <SLICE3>
                   |  out <----- in  |
                   +-----------------+

                                  |
                                  V

        The huffman encoder, however, expects the image is passed as
        a sequence of rows, for this reason it "sees" the vertical
        slices as horizontal bunches of pixels.

            [c] RAW IMAGE AS SEEN BY THE HUFFMAN ENCODER
        +--------------------------------------------------+
        |<.................................................|
        |..................................SLICE  1........|
        |..................................................|
        |.........................................><:::::::|
        |::::::::::::::::::::::::::::::::::::::::::::::::::|
        |::::::::::::::::::::::::::SLICE  2::::::::::::::::|
        |::::::::::::::::::::::::::::::::::::::::::::::::::|
        |:::::::::::::::::::::::::::::::::><===============|
        |==================================================|
        |=============================SLICE  3=============|
        |==================================================|
        |=================================================>|
        +--------------------------------------------------+

                                  |
                                  V

        For this reason we cannot decode each slice directly or we will
        have some strange results (I've tried it XD). To revert back to
        the original RAW image, as written in (2), the compressed image
        must be decoded ROW BY ROW (we know the image shape from the
        FrameTable)

                      [d] DECOMPRESSION PROCESS
                   +-----------------+
                   | HUFFMAN ENCODER |
        <011011010 |                 | row n>...<row 3> <row 2> <row 1>
                   |  in -----> out  |
                   +-----------------+

                                  |
                                  V

        The decoded image is now a perfect copy of the [c] RAW image as
        seen by the huffman encoder of the camera. To obtain the actual
        RAW image the data must be reshaped into vertical slices.
        """
        image = []
        rows = xrange(imageh)
        cols = xrange(imagew)

        _update_val = int(imageh / 100.0)

        # Decoding data row by row

        if same_tables:

            # NOTE: This IF statement shuold be inside the
            # 'for key in kdic' statement but even a simple
            # IF repeated rows*cols*X times can slow down the
            # code execution. So it is faster to repeat the
            # whole FOR ... FOR block, even if it is not so cool...

            for row in rows:

                # using list and converting to ndarray later
                # is much faster then using ndarray directly!
                crow = []

                if not row % _update_val:
                    self.__decoding_progress = int(row * 100.0 / imageh)
                    self.decodingProgressChanged.emit(self.__decoding_progress)
                    Qt.QApplication.instance().processEvents()

                    if self._canceled:
                        self._canceled = False
                        return None

                for col in cols:

                    if (lenbuff < MIN_BUFFER_LEN):
                        if datapos <= dataleft:
                            buff += ba2bs(data[datapos:datapos+tokenlen])
                            lenbuff += bittokenlen
                            datapos += tokenlen
                        elif datapos < dataend:
                            buff += ba2bs2(data[datapos:])
                            lenbuff = len(buff)
                            datapos = dataend

                    for key in kdic:
                        off = keys_len[key]
                        if key == buff[0:off]:

                            dlen = codes[key]
                            shift = off+dlen

                            if dlen:
                                sbin = buff[off:shift]
                                # DC additional bits to integer value
                                if sbin[0] == '0':
                                    val = -(int(sbin, 2) ^ masks[dlen])
                                else:
                                    val = int(sbin, 2)
                            else:
                                val = 0

                            if col < components:
                                pred = predictor[col]
                                predictor[col] += val
                            else:

                                try:
                                    pxl = crow[-components]
                                except:
                                    pxl = 0

                                try:
                                    pxt = image[-1][col]
                                except:
                                    pxt = 0

                                try:
                                    pxtl = image[-1][col-components]
                                except:
                                    pxtl = 0

                                pred = getPredictorValue(psv, pxl, pxt, pxtl)

                            crow.append(val+pred)
                            buff = buff[shift:]
                            lenbuff -= shift
                            break

                # This type of check is faster then checking for
                # the correct reading of each huffman key, even
                # if it uses the len() function
                if len(crow) != imagew:
                    raise IOError("Corrupted or invalid CR2 data!")

                image.append(crow)
        else:
            for row in rows:

                # using list and converting to ndarray later
                # is much faster then using ndarray directly!
                crow = []

                if not row % _update_val:
                    self.__decoding_progress = int(row * 100.0 / imageh)
                    self.decodingProgressChanged.emit(self.__decoding_progress)
                    Qt.QApplication.instance().processEvents()

                    if self._canceled:
                        self._canceled = False
                        return None

                for col in cols:

                    if (lenbuff < MIN_BUFFER_LEN):
                        if datapos <= dataleft:
                            buff += ba2bs(data[datapos:datapos+tokenlen])
                            lenbuff += bittokenlen
                            datapos += tokenlen
                        elif datapos < dataend:
                            buff += ba2bs2(data[datapos:])
                            lenbuff = len(buff)
                            datapos = dataend

                    for key in kdic:
                        off = keys_len[key]
                        if key == buff[0:off]:

                            i += 1
                            idx = indexes[i % num_of_indexes]
                            dlen = codes[idx][key]
                            kdic = kdics[idx]
                            keys_len = keys_lens[idx]
                            shift = off + dlen

                            if dlen:
                                sbin = buff[off:shift]

                                # DC additional bits to integer value
                                if sbin[0] == '0':
                                    val = -(int(sbin, 2) ^ masks[dlen])
                                else:
                                    val = int(sbin, 2)
                            else:
                                val = 0

                            if col < components:
                                pred = predictor[col]
                                predictor[col] += val
                            else:

                                try:
                                    pxl = crow[-components]
                                except:
                                    pxl = 0

                                try:
                                    pxt = image[-1][col]
                                except:
                                    pxt = 0

                                try:
                                    pxtl = image[-1][col-components]
                                except:
                                    pxtl = 0

                                pred = getPredictorValue(psv, pxl, pxt, pxtl)

                            crow.append(val + pred)
                            buff = buff[shift:]
                            lenbuff -= shift
                            break

                # This type of check is faster then checking for
                # the correct reading of each huffman key, even
                # if it uses the len() function
                if len(crow) != imagew:
                    raise IOError("Corrupted or invalid CR2 data!")

                image.append(crow)

        # Now we reorder the decoded image into the original slices
        flattened = np.array(image, dtype=np.uint).flatten('C')
        image = np.empty((imageh, imagew), dtype=np.uint16)
        start = 0
        end = 0

        for s in slices_size:
            end += s
            flatarr = np.array(flattened[imageh*start:imageh*end])
            image[:, start:end] = flatarr.reshape((imageh, s))
            start += s
            del flatarr

        del flattened
        self.decodingProgressChanged.emit(100)
        self.decodingEnded.emit()
        return image

    def _readIfd(self, byteorder, offset):
        self.fp.seek(offset, 0)
        raw_ifd = self.fp.read(2)

        # create IFD tags dictionary
        tags = {}

        for i in range(_reconstructDataFromString(byteorder, raw_ifd)):
            data = self.fp.read(12)
            tagID = _reconstructDataFromString(byteorder, data[:2])
            tagType = _reconstructDataFromString(byteorder, data[2:4])
            tagNum = _reconstructDataFromString(byteorder, data[4:8])
            tagValOff = _reconstructDataFromString(byteorder, data[8:12])

            if (tagNum > 1) or (_getTypeSize(tagType) > 4):
                fppos = self.fp.tell()
                self.fp.seek(tagValOff, 0)
                datasize = _getTypeSize(tagType)
                if datasize == -1:
                    val = _getExifValue(self.fp.read(tagNum), tagType)
                elif datasize == -2:
                    tagVal = _getExifValue(tagValOff, tagType)
                    val = ('undefined', tagNum, tagVal)
                else:
                    val = []
                    for i in range(tagNum):
                        data = self.fp.read(datasize)
                        data_off = _reconstructDataFromString(byteorder, data)
                        tagVal = _getExifValue(data_off, tagType)
                        val.append(tagVal)
                self.fp.seek(fppos, 0)
            else:
                val = _getExifValue(tagValOff, tagType)
            if (type(val) == tuple) or (type(val) == list):
                if len(val) == 1:
                    val = val[0]
            tags[tagID] = val
        return tags


def imread(fname):
    cr2img = QCR2Image(fname)
    return cr2img
