# lxnstack is a program to align and stack atronomical images
# Copyright (C) 2013-2015  Maurizio D'Addona <mauritiusdadd@gmail.com>
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

import logging
import platform
import ctypes
import ctypes.util

import log
from v4l2_controls import *

#
# NOTE: This header is generated from <linux/videodev2.h> using the
#       scriptv4l2-binding-builder.py that can be found in the source
#       code of lxnstack. The script only translate the header
#       form c to python so you may want to edit this document in
#       order to fix parsing errors.
#

try:

    #
    # This section is needed to access the libv4l2.so functions
    #

    libv4l2 = ctypes.cdll.LoadLibrary(ctypes.util.find_library("v4l2"))

    libv4l2.v4l2_open.argtype = [ctypes.c_char_p, ctypes.c_int8]
    libv4l2.v4l2_open.restype = ctypes.c_int8
    v4l2_open = libv4l2.v4l2_open

    # NOTE: the v4l2_fd_open function here is almost useless
    #       because it is already called inside v4l2_open.
    libv4l2.v4l2_fd_open.argtype = [ctypes.c_int8, ctypes.c_int8]
    libv4l2.v4l2_fd_open.restype = ctypes.c_int8
    v4l2_fd_open = libv4l2.v4l2_fd_open

    libv4l2.v4l2_read.argtype = [ctypes.c_int8,
                                 ctypes.c_uint32,
                                 ctypes.c_uint32]
    libv4l2.v4l2_read.restype = ctypes.c_int8
    v4l2_read = libv4l2.v4l2_read

    v4l2_close = libv4l2.v4l2_close

    libv4l2.v4l2_mmap.argtype = [ctypes.c_void_p, ctypes.c_uint32,
                                 ctypes.c_int8, ctypes.c_int8,
                                 ctypes.c_int8, ctypes.c_uint64]
    libv4l2.v4l2_mmap.restype = ctypes.c_void_p
    v4l2_mmap = libv4l2.v4l2_mmap

    v4l2_munmap = libv4l2.v4l2_munmap

    libv4l2.v4l2_ioctl.argtype = [ctypes.c_uint8,
                                  ctypes.c_uint8,
                                  ctypes.c_void_p]
    libv4l2.v4l2_ioctl.restype = ctypes.c_int8
    v4l2_ioctl = libv4l2.v4l2_ioctl

    libv4l2.__errno_location.restype = ctypes.POINTER(ctypes.c_int)

    def v4l2_errno():
        err = libv4l2.__errno_location()
        return err.contents.value

    # Disable all format conversion done by libv4l2 (reduces libv4l2
    # functionality to offering v4l2_read() even on devices which
    # don't implement read())
    V4L2_DISABLE_CONVERSION = 0x01
    # Report not only real but also emulated formats with the ENUM_FMT ioctl
    V4L2_ENABLE_ENUM_FMT_EMULATION = 0x02

    HAS_LIBV4L2 = True
    log.log("<videodev2 module>",
            "FOUND LIBV42",
            level=logging.DEBUG)
except:
    log.log("<videodev2 module>",
            "LIBV42 NOT FOUND",
            level=logging.DEBUG)
    HAS_LIBV4L2 = False

#
# Code translated from c to python from ioctl.h
#

if platform.machine().startswith('mips'):
    _IOC_NRBITS = 8
    _IOC_TYPEBITS = 8
    _IOC_SIZEBITS = 13
    _IOC_DIRBITS = 3

    _IOC_NRSHIFT = 0
    _IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
    _IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
    _IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS

    _IOC_SLMASK = 255

    _IOC_NONE = 1
    _IOC_WRITE = 2
    _IOC_READ = 4

    def _IOC(dir_, type_, nr, size):
        return ((dir_ << _IOC_DIRSHIFT) |
                (ord(type_) << _IOC_TYPESHIFT) |
                (nr << _IOC_NRSHIFT) |
                ((size & _IOC_SLMASK) << _IOC_SIZESHIFT))

elif platform.machine().startswith('ppc'):
    _IOC_NRBITS = 8
    _IOC_TYPEBITS = 8
    _IOC_SIZEBITS = 13
    _IOC_DIRBITS = 3

    _IOC_NRSHIFT = 0
    _IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
    _IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
    _IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS

    _IOC_NONE = 1
    _IOC_WRITE = 2
    _IOC_READ = 4

    def _IOC(dir_, type_, nr, size):
        return ((dir_ << _IOC_DIRSHIFT) |
                (ord(type_) << _IOC_TYPESHIFT) |
                (nr << _IOC_NRSHIFT) |
                ((size) << _IOC_SIZESHIFT))

elif platform.machine().startswith('sparc'):

    _IOC_NRBITS = 8
    _IOC_TYPEBITS = 8
    _IOC_SIZEBITS = 8
    _IOC_RESVBITS = 5
    _IOC_DIRBITS = 3

    _IOC_NRSHIFT = 0
    _IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
    _IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
    _IOC_RESVSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS
    _IOC_DIRSHIFT = _IOC_RESVSHIFT + _IOC_RESVBITS

    _IOC_NONE = 0
    _IOC_WRITE = 1
    _IOC_READ = 2

    def _IOC(dir_, type_, nr, size):
        return ((dir_ << _IOC_DIRSHIFT) |
                (ord(type_) << _IOC_TYPESHIFT) |
                (nr << _IOC_NRSHIFT) |
                (size << _IOC_SIZESHIFT))
else:

    #
    # It should be compatible with several architecture
    #

    _IOC_NRBITS = 8
    _IOC_TYPEBITS = 8
    _IOC_SIZEBITS = 14
    _IOC_DIRBITS = 2

    _IOC_NRSHIFT = 0
    _IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
    _IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
    _IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS

    _IOC_NONE = 0
    _IOC_WRITE = 1
    _IOC_READ = 2

    def _IOC(dir_, type_, nr, size):
        return ((dir_ << _IOC_DIRSHIFT) |
                (ord(type_) << _IOC_TYPESHIFT) |
                (nr << _IOC_NRSHIFT) |
                (size << _IOC_SIZESHIFT))


def _IOC_TYPECHECK(t):
    return ctypes.sizeof(t)


def _IO(type_, nr):
    return _IOC(_IOC_NONE, type_, nr, 0)


def _IOW(type_, nr, size):
    return _IOC(_IOC_WRITE, type_, nr, _IOC_TYPECHECK(size))


def _IOR(type_, nr, size):
    return _IOC(_IOC_READ, type_, nr, _IOC_TYPECHECK(size))


def _IOWR(type_, nr, size):
    return _IOC(_IOC_READ | _IOC_WRITE, type_, nr, _IOC_TYPECHECK(size))


class timeval(ctypes.Structure):
    _fields_ = [('secs', ctypes.c_long),
                ('usecs', ctypes.c_long)]


class timespec(ctypes.Structure):
    _fields_ = [('tv_sec', ctypes.c_long),
                ('tv_nsec', ctypes.c_long)]

#
#  Video for Linux Two header file
#
#  Copyright (C) 1999-2012 the contributors
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  Alternatively you can redistribute this file under the terms of the
#  BSD license as stated below:
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions
#  are met:
#  1. Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#  2. Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in
#     the documentation and/or other materials provided with the
#     distribution.
#  3. The names of its contributors may not be used to endorse or promote
#     products derived from this software without specific prior written
#     permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#  OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
#  TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
#  PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
#  LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
#  NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Header file for v4l or V4L2 drivers and applications
# with public API.
# All kernel-specific stuff were moved to media/v4l2-dev.h, so
# no  *
# See http://linuxtv.org for more info
#
# Author: Bill Dirks <bill@thedirks.org>
#  Justin Schoeman
#              Hans Verkuil <hverkuil@xs4all.nl>
#  et al.
#
# define _UAPI__LINUX_VIDEODEV2_H

# include <sys/time.h>
# include <linux/compiler.h>
# include <linux/ioctl.h>
# include <linux/types.h>
# include <linux/v4l2-common.h>
# include <linux/v4l2-controls.h>


#
# Common stuff for both V4L1 and V4L2
# Moved from videodev.h
#
VIDEO_MAX_FRAME = 32
VIDEO_MAX_PLANES = 8


#
# M I S C E L L A N E O U S
#


#  Four-character-code (FOURCC)
def v4l2_fourcc(a, b, c, d):
    return ord(a) | (ord(b) << 8) | (ord(c) << 16) | (ord(d) << 24)


def v4l2_fourcc_string(val):
    a = chr(255 & val)
    b = chr(255 & (val >> 8))
    c = chr(255 & (val >> 16))
    d = chr(255 & (val >> 24))
    return a+b+c+d


#
# E N U M S
#

v4l2_field = ctypes.c_uint

V4L2_FIELD_ANY = 0
V4L2_FIELD_NONE = 1
V4L2_FIELD_TOP = 2
V4L2_FIELD_BOTTOM = 3
V4L2_FIELD_INTERLACED = 4
V4L2_FIELD_SEQ_TB = 5
V4L2_FIELD_SEQ_BT = 6
V4L2_FIELD_ALTERNATE = 7
V4L2_FIELD_INTERLACED_TB = 8
V4L2_FIELD_INTERLACED_BT = 9


def V4L2_FIELD_HAS_TOP(field):
    return (
        (field) == V4L2_FIELD_TOP |
        (field) == V4L2_FIELD_INTERLACED |
        (field) == V4L2_FIELD_INTERLACED_TB |
        (field) == V4L2_FIELD_INTERLACED_BT |
        (field) == V4L2_FIELD_SEQ_TB |
        (field) == V4L2_FIELD_SEQ_BT
    )


def V4L2_FIELD_HAS_BOTTOM(field):
    return (
        (field) == V4L2_FIELD_BOTTOM |
        (field) == V4L2_FIELD_INTERLACED |
        (field) == V4L2_FIELD_INTERLACED_TB |
        (field) == V4L2_FIELD_INTERLACED_BT |
        (field) == V4L2_FIELD_SEQ_TB |
        (field) == V4L2_FIELD_SEQ_BT
    )


def V4L2_FIELD_HAS_BOTH(field):
    return (
        (field) == V4L2_FIELD_INTERLACED |
        (field) == V4L2_FIELD_INTERLACED_TB |
        (field) == V4L2_FIELD_INTERLACED_BT |
        (field) == V4L2_FIELD_SEQ_TB |
        (field) == V4L2_FIELD_SEQ_BT
    )

v4l2_buf_type = ctypes.c_uint

V4L2_BUF_TYPE_VIDEO_CAPTURE = 1
V4L2_BUF_TYPE_VIDEO_OUTPUT = 2
V4L2_BUF_TYPE_VIDEO_OVERLAY = 3
V4L2_BUF_TYPE_VBI_CAPTURE = 4
V4L2_BUF_TYPE_VBI_OUTPUT = 5
V4L2_BUF_TYPE_SLICED_VBI_CAPTURE = 6
V4L2_BUF_TYPE_SLICED_VBI_OUTPUT = 7
V4L2_BUF_TYPE_VIDEO_OUTPUT_OVERLAY = 8
V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE = 9
V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE = 10
V4L2_BUF_TYPE_PRIVATE = 0x80


def V4L2_TYPE_IS_MULTIPLANAR(type_):
    return ((type_) == V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE |
            (type_) == V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE)


def V4L2_TYPE_IS_OUTPUT(type_):
    return ((type_) == V4L2_BUF_TYPE_VIDEO_OUTPUT |
            (type_) == V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE |
            (type_) == V4L2_BUF_TYPE_VIDEO_OVERLAY |
            (type_) == V4L2_BUF_TYPE_VIDEO_OUTPUT_OVERLAY |
            (type_) == V4L2_BUF_TYPE_VBI_OUTPUT |
            (type_) == V4L2_BUF_TYPE_SLICED_VBI_OUTPUT)

v4l2_tuner_type = ctypes.c_uint

V4L2_TUNER_RADIO = 1
V4L2_TUNER_ANALOG_TV = 2
V4L2_TUNER_DIGITAL_TV = 3

v4l2_memory = ctypes.c_uint

V4L2_MEMORY_MMAP = 1
V4L2_MEMORY_USERPTR = 2
V4L2_MEMORY_OVERLAY = 3
V4L2_MEMORY_DMABUF = 4

# see also http://vektor.theorem.ca/graphics/ycbcr/

v4l2_colorspace = ctypes.c_uint

V4L2_COLORSPACE_SMPTE170M = 1
V4L2_COLORSPACE_SMPTE240M = 2
V4L2_COLORSPACE_REC709 = 3
V4L2_COLORSPACE_BT878 = 4
V4L2_COLORSPACE_470_SYSTEM_M = 5
V4L2_COLORSPACE_470_SYSTEM_BG = 6
V4L2_COLORSPACE_JPEG = 7
V4L2_COLORSPACE_SRGB = 8

v4l2_priority = ctypes.c_uint

V4L2_PRIORITY_UNSET = 0
V4L2_PRIORITY_BACKGROUND = 1
V4L2_PRIORITY_INTERACTIVE = 2
V4L2_PRIORITY_RECORD = 3
V4L2_PRIORITY_DEFAULT = V4L2_PRIORITY_INTERACTIVE


class v4l2_rect(ctypes.Structure):

    _fields_ = [
        ('left', ctypes.c_int32),
        ('top', ctypes.c_int32),
        ('width', ctypes.c_uint32),
        ('height', ctypes.c_uint32),
    ]


class v4l2_fract(ctypes.Structure):

    _fields_ = [
        ('numerator', ctypes.c_uint32),
        ('denominator', ctypes.c_uint32),
    ]


#
# v4l2_capability - Describes V4L2 device caps returned by VIDIOC_QUERYCAP
#
# @driver:    name of the driver module (e.g. "bttv")
# @card:    name of the card (e.g. "Hauppauge WinTV")
# @bus_info:    name of the bus (e.g. "PCI:" + pci_name(pci_dev) )
# @version:    KERNEL_VERSION
# @capabilities: capabilities of the physical device as a whole
# @device_caps:  capabilities accessed via this particular device (node)
# @reserved:    reserved fields for future extensions
#

class v4l2_capability(ctypes.Structure):

    _fields_ = [
        ('driver', ctypes.c_char*16),
        ('card', ctypes.c_char*32),
        ('bus_info', ctypes.c_char*32),
        ('version', ctypes.c_uint32),
        ('capabilities', ctypes.c_uint32),
        ('device_caps', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*3),
    ]


# Values for 'capabilities' field
V4L2_CAP_VIDEO_CAPTURE = 0x00000001
# Is a video capture device
V4L2_CAP_VIDEO_OUTPUT = 0x00000002
# Is a video output device
V4L2_CAP_VIDEO_OVERLAY = 0x00000004
# Can do video overlay
V4L2_CAP_VBI_CAPTURE = 0x00000010
# Is a raw VBI capture device
V4L2_CAP_VBI_OUTPUT = 0x00000020
# Is a raw VBI output device
V4L2_CAP_SLICED_VBI_CAPTURE = 0x00000040
# Is a sliced VBI capture device
V4L2_CAP_SLICED_VBI_OUTPUT = 0x00000080
# Is a sliced VBI output device
V4L2_CAP_RDS_CAPTURE = 0x00000100
# RDS data capture
V4L2_CAP_VIDEO_OUTPUT_OVERLAY = 0x00000200
# Can do video output overlay
V4L2_CAP_HW_FREQ_SEEK = 0x00000400
# Can do hardware frequency seek
V4L2_CAP_RDS_OUTPUT = 0x00000800
# Is an RDS encoder


# Is a video capture device that supports multiplanar formats
V4L2_CAP_VIDEO_CAPTURE_MPLANE = 0x00001000

# Is a video output device that supports multiplanar formats
V4L2_CAP_VIDEO_OUTPUT_MPLANE = 0x00002000

# Is a video mem-to-mem device that supports multiplanar formats
V4L2_CAP_VIDEO_M2M_MPLANE = 0x00004000

# Is a video mem-to-mem device
V4L2_CAP_VIDEO_M2M = 0x00008000

V4L2_CAP_TUNER = 0x00010000
# has a tuner
V4L2_CAP_AUDIO = 0x00020000
# has audio support
V4L2_CAP_RADIO = 0x00040000
# is a radio device
V4L2_CAP_MODULATOR = 0x00080000
# has a modulator

V4L2_CAP_READWRITE = 0x01000000
# read/write systemcalls
V4L2_CAP_ASYNCIO = 0x02000000
# async I/O
V4L2_CAP_STREAMING = 0x04000000
# streaming I/O ioctls

V4L2_CAP_DEVICE_CAPS = 0x80000000
# sets device capabilities field


#
# V I D E O   I M A G E   F O R M A T
#

class v4l2_pix_format(ctypes.Structure):

    _fields_ = [
        ('width', ctypes.c_uint32),
        ('height', ctypes.c_uint32),
        ('pixelformat', ctypes.c_uint32),
        ('field', ctypes.c_uint32),
        ('bytesperline', ctypes.c_uint32),
        ('sizeimage', ctypes.c_uint32),
        ('colorspace', ctypes.c_uint32),
        ('priv', ctypes.c_uint32),
    ]


#      Pixel format         FOURCC                          depth  Description

# RGB formats
V4L2_PIX_FMT_RGB332 = v4l2_fourcc('R', 'G', 'B', '1')
#  8  RGB-3-3-2
V4L2_PIX_FMT_RGB444 = v4l2_fourcc('R', '4', '4', '4')
# 16  xxxxrrrr ggggbbbb
V4L2_PIX_FMT_RGB555 = v4l2_fourcc('R', 'G', 'B', 'O')
# 16  RGB-5-5-5
V4L2_PIX_FMT_RGB565 = v4l2_fourcc('R', 'G', 'B', 'P')
# 16  RGB-5-6-5
V4L2_PIX_FMT_RGB555X = v4l2_fourcc('R', 'G', 'B', 'Q')
# 16  RGB-5-5-5 BE
V4L2_PIX_FMT_RGB565X = v4l2_fourcc('R', 'G', 'B', 'R')
# 16  RGB-5-6-5 BE
V4L2_PIX_FMT_BGR666 = v4l2_fourcc('B', 'G', 'R', 'H')
# 18  BGR-6-6-6
V4L2_PIX_FMT_BGR24 = v4l2_fourcc('B', 'G', 'R', '3')
# 24  BGR-8-8-8
V4L2_PIX_FMT_RGB24 = v4l2_fourcc('R', 'G', 'B', '3')
# 24  RGB-8-8-8
V4L2_PIX_FMT_BGR32 = v4l2_fourcc('B', 'G', 'R', '4')
# 32  BGR-8-8-8-8
V4L2_PIX_FMT_RGB32 = v4l2_fourcc('R', 'G', 'B', '4')
# 32  RGB-8-8-8-8


# Grey formats
V4L2_PIX_FMT_GREY = v4l2_fourcc('G', 'R', 'E', 'Y')
#  8  Greyscale
V4L2_PIX_FMT_Y4 = v4l2_fourcc('Y', '0', '4', ' ')
#  4  Greyscale
V4L2_PIX_FMT_Y6 = v4l2_fourcc('Y', '0', '6', ' ')
#  6  Greyscale
V4L2_PIX_FMT_Y10 = v4l2_fourcc('Y', '1', '0', ' ')
# 10  Greyscale
V4L2_PIX_FMT_Y12 = v4l2_fourcc('Y', '1', '2', ' ')
# 12  Greyscale
V4L2_PIX_FMT_Y16 = v4l2_fourcc('Y', '1', '6', ' ')
# 16  Greyscale


# Grey bit-packed formats
V4L2_PIX_FMT_Y10BPACK = v4l2_fourcc('Y', '1', '0', 'B')
# 10  Greyscale bit-packed


# Palette formats
V4L2_PIX_FMT_PAL8 = v4l2_fourcc('P', 'A', 'L', '8')
#  8  8-bit palette


# Chrominance formats
V4L2_PIX_FMT_UV8 = v4l2_fourcc('U', 'V', '8', ' ')
#  8  UV 4:4


# Luminance+Chrominance formats
V4L2_PIX_FMT_YVU410 = v4l2_fourcc('Y', 'V', 'U', '9')
#  9  YVU 4:1:0
V4L2_PIX_FMT_YVU420 = v4l2_fourcc('Y', 'V', '1', '2')
# 12  YVU 4:2:0
V4L2_PIX_FMT_YUYV = v4l2_fourcc('Y', 'U', 'Y', 'V')
# 16  YUV 4:2:2
V4L2_PIX_FMT_YYUV = v4l2_fourcc('Y', 'Y', 'U', 'V')
# 16  YUV 4:2:2
V4L2_PIX_FMT_YVYU = v4l2_fourcc('Y', 'V', 'Y', 'U')
# 16 YVU 4:2:2
V4L2_PIX_FMT_UYVY = v4l2_fourcc('U', 'Y', 'V', 'Y')
# 16  YUV 4:2:2
V4L2_PIX_FMT_VYUY = v4l2_fourcc('V', 'Y', 'U', 'Y')
# 16  YUV 4:2:2
V4L2_PIX_FMT_YUV422P = v4l2_fourcc('4', '2', '2', 'P')
# 16  YVU422 planar
V4L2_PIX_FMT_YUV411P = v4l2_fourcc('4', '1', '1', 'P')
# 16  YVU411 planar
V4L2_PIX_FMT_Y41P = v4l2_fourcc('Y', '4', '1', 'P')
# 12  YUV 4:1:1
V4L2_PIX_FMT_YUV444 = v4l2_fourcc('Y', '4', '4', '4')
# 16  xxxxyyyy uuuuvvvv
V4L2_PIX_FMT_YUV555 = v4l2_fourcc('Y', 'U', 'V', 'O')
# 16  YUV-5-5-5
V4L2_PIX_FMT_YUV565 = v4l2_fourcc('Y', 'U', 'V', 'P')
# 16  YUV-5-6-5
V4L2_PIX_FMT_YUV32 = v4l2_fourcc('Y', 'U', 'V', '4')
# 32  YUV-8-8-8-8
V4L2_PIX_FMT_YUV410 = v4l2_fourcc('Y', 'U', 'V', '9')
#  9  YUV 4:1:0
V4L2_PIX_FMT_YUV420 = v4l2_fourcc('Y', 'U', '1', '2')
# 12  YUV 4:2:0
V4L2_PIX_FMT_HI240 = v4l2_fourcc('H', 'I', '2', '4')
#  8  8-bit color
V4L2_PIX_FMT_HM12 = v4l2_fourcc('H', 'M', '1', '2')
#  8  YUV 4:2:0 16x16 macroblocks
V4L2_PIX_FMT_M420 = v4l2_fourcc('M', '4', '2', '0')
# 12  YUV 4:2:0 2 lines y, 1 line uv interleaved


# two planes -- one Y, one Cr + Cb interleaved
V4L2_PIX_FMT_NV12 = v4l2_fourcc('N', 'V', '1', '2')
# 12  Y/CbCr 4:2:0
V4L2_PIX_FMT_NV21 = v4l2_fourcc('N', 'V', '2', '1')
# 12  Y/CrCb 4:2:0
V4L2_PIX_FMT_NV16 = v4l2_fourcc('N', 'V', '1', '6')
# 16  Y/CbCr 4:2:2
V4L2_PIX_FMT_NV61 = v4l2_fourcc('N', 'V', '6', '1')
# 16  Y/CrCb 4:2:2
V4L2_PIX_FMT_NV24 = v4l2_fourcc('N', 'V', '2', '4')
# 24  Y/CbCr 4:4:4
V4L2_PIX_FMT_NV42 = v4l2_fourcc('N', 'V', '4', '2')
# 24  Y/CrCb 4:4:4


# two non contiguous planes - one Y, one Cr + Cb interleaved
V4L2_PIX_FMT_NV12M = v4l2_fourcc('N', 'M', '1', '2')
# 12  Y/CbCr 4:2:0
V4L2_PIX_FMT_NV21M = v4l2_fourcc('N', 'M', '2', '1')
# 21  Y/CrCb 4:2:0
V4L2_PIX_FMT_NV16M = v4l2_fourcc('N', 'M', '1', '6')
# 16  Y/CbCr 4:2:2
V4L2_PIX_FMT_NV61M = v4l2_fourcc('N', 'M', '6', '1')
# 16  Y/CrCb 4:2:2
V4L2_PIX_FMT_NV12MT = v4l2_fourcc('T', 'M', '1', '2')
# 12  Y/CbCr 4:2:0 64x32 macroblocks
V4L2_PIX_FMT_NV12MT_16X16 = v4l2_fourcc('V', 'M', '1', '2')
# 12  Y/CbCr 4:2:0 16x16 macroblocks


# three non contiguous planes - Y, Cb, Cr
V4L2_PIX_FMT_YUV420M = v4l2_fourcc('Y', 'M', '1', '2')
# 12  YUV420 planar
V4L2_PIX_FMT_YVU420M = v4l2_fourcc('Y', 'M', '2', '1')
# 12  YVU420 planar


# Bayer formats - see http://www.siliconimaging.com/RGB%20Bayer.htm
V4L2_PIX_FMT_SBGGR8 = v4l2_fourcc('B', 'A', '8', '1')
#  8  BGBG.. GRGR..
V4L2_PIX_FMT_SGBRG8 = v4l2_fourcc('G', 'B', 'R', 'G')
#  8  GBGB.. RGRG..
V4L2_PIX_FMT_SGRBG8 = v4l2_fourcc('G', 'R', 'B', 'G')
#  8  GRGR.. BGBG..
V4L2_PIX_FMT_SRGGB8 = v4l2_fourcc('R', 'G', 'G', 'B')
#  8  RGRG.. GBGB..
V4L2_PIX_FMT_SBGGR10 = v4l2_fourcc('B', 'G', '1', '0')
# 10  BGBG.. GRGR..
V4L2_PIX_FMT_SGBRG10 = v4l2_fourcc('G', 'B', '1', '0')
# 10  GBGB.. RGRG..
V4L2_PIX_FMT_SGRBG10 = v4l2_fourcc('B', 'A', '1', '0')
# 10  GRGR.. BGBG..
V4L2_PIX_FMT_SRGGB10 = v4l2_fourcc('R', 'G', '1', '0')
# 10  RGRG.. GBGB..
V4L2_PIX_FMT_SBGGR12 = v4l2_fourcc('B', 'G', '1', '2')
# 12  BGBG.. GRGR..
V4L2_PIX_FMT_SGBRG12 = v4l2_fourcc('G', 'B', '1', '2')
# 12  GBGB.. RGRG..
V4L2_PIX_FMT_SGRBG12 = v4l2_fourcc('B', 'A', '1', '2')
# 12  GRGR.. BGBG..
V4L2_PIX_FMT_SRGGB12 = v4l2_fourcc('R', 'G', '1', '2')
# 12  RGRG.. GBGB..

# 10bit raw bayer a-law compressed to 8 bits
V4L2_PIX_FMT_SBGGR10ALAW8 = v4l2_fourcc('a', 'B', 'A', '8')
V4L2_PIX_FMT_SGBRG10ALAW8 = v4l2_fourcc('a', 'G', 'A', '8')
V4L2_PIX_FMT_SGRBG10ALAW8 = v4l2_fourcc('a', 'g', 'A', '8')
V4L2_PIX_FMT_SRGGB10ALAW8 = v4l2_fourcc('a', 'R', 'A', '8')

# 10bit raw bayer DPCM compressed to 8 bits
V4L2_PIX_FMT_SBGGR10DPCM8 = v4l2_fourcc('b', 'B', 'A', '8')
V4L2_PIX_FMT_SGBRG10DPCM8 = v4l2_fourcc('b', 'G', 'A', '8')
V4L2_PIX_FMT_SGRBG10DPCM8 = v4l2_fourcc('B', 'D', '1', '0')
V4L2_PIX_FMT_SRGGB10DPCM8 = v4l2_fourcc('b', 'R', 'A', '8')

#
# 10bit raw bayer, expanded to 16 bits
# xxxxrrrrrrrrrrxxxxgggggggggg xxxxggggggggggxxxxbbbbbbbbbb...
#
V4L2_PIX_FMT_SBGGR16 = v4l2_fourcc('B', 'Y', 'R', '2')
# 16  BGBG.. GRGR..


# compressed formats
V4L2_PIX_FMT_MJPEG = v4l2_fourcc('M', 'J', 'P', 'G')
# Motion-JPEG
V4L2_PIX_FMT_JPEG = v4l2_fourcc('J', 'P', 'E', 'G')
# JFIF JPEG
V4L2_PIX_FMT_DV = v4l2_fourcc('d', 'v', 's', 'd')
# 1394
V4L2_PIX_FMT_MPEG = v4l2_fourcc('M', 'P', 'E', 'G')
# MPEG-1/2/4 Multiplexed
V4L2_PIX_FMT_H264 = v4l2_fourcc('H', '2', '6', '4')
# H264 with start codes
V4L2_PIX_FMT_H264_NO_SC = v4l2_fourcc('A', 'V', 'C', '1')
# H264 without start codes
V4L2_PIX_FMT_H264_MVC = v4l2_fourcc('M', '2', '6', '4')
# H264 MVC
V4L2_PIX_FMT_H263 = v4l2_fourcc('H', '2', '6', '3')
# H263
V4L2_PIX_FMT_MPEG1 = v4l2_fourcc('M', 'P', 'G', '1')
# MPEG-1 ES
V4L2_PIX_FMT_MPEG2 = v4l2_fourcc('M', 'P', 'G', '2')
# MPEG-2 ES
V4L2_PIX_FMT_MPEG4 = v4l2_fourcc('M', 'P', 'G', '4')
# MPEG-4 part 2 ES
V4L2_PIX_FMT_XVID = v4l2_fourcc('X', 'V', 'I', 'D')
# Xvid
V4L2_PIX_FMT_VC1_ANNEX_G = v4l2_fourcc('V', 'C', '1', 'G')
# SMPTE 421M Annex G compliant stream
V4L2_PIX_FMT_VC1_ANNEX_L = v4l2_fourcc('V', 'C', '1', 'L')
# SMPTE 421M Annex L compliant stream
V4L2_PIX_FMT_VP8 = v4l2_fourcc('V', 'P', '8', '0')
# VP8


#  Vendor-specific formats
V4L2_PIX_FMT_CPIA1 = v4l2_fourcc('C', 'P', 'I', 'A')
# cpia1 YUV
V4L2_PIX_FMT_WNVA = v4l2_fourcc('W', 'N', 'V', 'A')
# Winnov hw compress
V4L2_PIX_FMT_SN9C10X = v4l2_fourcc('S', '9', '1', '0')
# SN9C10x compression
V4L2_PIX_FMT_SN9C20X_I420 = v4l2_fourcc('S', '9', '2', '0')
# SN9C20x YUV 4:2:0
V4L2_PIX_FMT_PWC1 = v4l2_fourcc('P', 'W', 'C', '1')
# pwc older webcam
V4L2_PIX_FMT_PWC2 = v4l2_fourcc('P', 'W', 'C', '2')
# pwc newer webcam
V4L2_PIX_FMT_ET61X251 = v4l2_fourcc('E', '6', '2', '5')
# ET61X251 compression
V4L2_PIX_FMT_SPCA501 = v4l2_fourcc('S', '5', '0', '1')
# YUYV per line
V4L2_PIX_FMT_SPCA505 = v4l2_fourcc('S', '5', '0', '5')
# YYUV per line
V4L2_PIX_FMT_SPCA508 = v4l2_fourcc('S', '5', '0', '8')
# YUVY per line
V4L2_PIX_FMT_SPCA561 = v4l2_fourcc('S', '5', '6', '1')
# compressed GBRG bayer
V4L2_PIX_FMT_PAC207 = v4l2_fourcc('P', '2', '0', '7')
# compressed BGGR bayer
V4L2_PIX_FMT_MR97310A = v4l2_fourcc('M', '3', '1', '0')
# compressed BGGR bayer
V4L2_PIX_FMT_JL2005BCD = v4l2_fourcc('J', 'L', '2', '0')
# compressed RGGB bayer
V4L2_PIX_FMT_SN9C2028 = v4l2_fourcc('S', 'O', 'N', 'X')
# compressed GBRG bayer
V4L2_PIX_FMT_SQ905C = v4l2_fourcc('9', '0', '5', 'C')
# compressed RGGB bayer
V4L2_PIX_FMT_PJPG = v4l2_fourcc('P', 'J', 'P', 'G')
# Pixart 73xx JPEG
V4L2_PIX_FMT_OV511 = v4l2_fourcc('O', '5', '1', '1')
# ov511 JPEG
V4L2_PIX_FMT_OV518 = v4l2_fourcc('O', '5', '1', '8')
# ov518 JPEG
V4L2_PIX_FMT_STV0680 = v4l2_fourcc('S', '6', '8', '0')
# stv0680 bayer
V4L2_PIX_FMT_TM6000 = v4l2_fourcc('T', 'M', '6', '0')
# tm5600/tm60x0
V4L2_PIX_FMT_CIT_YYVYUY = v4l2_fourcc('C', 'I', 'T', 'V')
# one line of Y then 1 line of VYUY
V4L2_PIX_FMT_KONICA420 = v4l2_fourcc('K', 'O', 'N', 'I')
# YUV420 planar in blocks of 256 pixels
V4L2_PIX_FMT_JPGL = v4l2_fourcc('J', 'P', 'G', 'L')
# JPEG-Lite
V4L2_PIX_FMT_SE401 = v4l2_fourcc('S', '4', '0', '1')
# se401 janggu compressed rgb
V4L2_PIX_FMT_S5C_UYVY_JPG = v4l2_fourcc('S', '5', 'C', 'I')
# S5C73M3 interleaved UYVY/JPEG


#
# F O R M A T   E N U M E R A T I O N
#

class v4l2_fmtdesc(ctypes.Structure):

    _fields_ = [
        ('index', ctypes.c_uint32),
        ('type', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('description', ctypes.c_char*32),
        ('pixelformat', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*4),
    ]


V4L2_FMT_FLAG_COMPRESSED = 0x0001
V4L2_FMT_FLAG_EMULATED = 0x0002


# Experimental Frame Size and frame rate enumeration

#
# F R A M E   S I Z E   E N U M E R A T I O N
#

v4l2_frmsizetypes = ctypes.c_uint

V4L2_FRMSIZE_TYPE_DISCRETE = 1
V4L2_FRMSIZE_TYPE_CONTINUOUS = 2
V4L2_FRMSIZE_TYPE_STEPWISE = 3


class v4l2_frmsize_discrete(ctypes.Structure):

    _fields_ = [
        ('width', ctypes.c_uint32),
        ('height', ctypes.c_uint32),
    ]


class v4l2_frmsize_stepwise(ctypes.Structure):

    _fields_ = [
        ('min_width', ctypes.c_uint32),
        ('max_width', ctypes.c_uint32),
        ('step_width', ctypes.c_uint32),
        ('min_height', ctypes.c_uint32),
        ('max_height', ctypes.c_uint32),
        ('step_height', ctypes.c_uint32),
    ]


class v4l2_frmsizeenum(ctypes.Structure):
    # $OBJ-00010
    class _u16(ctypes.Union):

        _fields_ = [
            ('discrete', v4l2_frmsize_discrete),
            ('stepwise', v4l2_frmsize_stepwise),
        ]

    _fields_ = [
        ('index', ctypes.c_uint32),
        ('pixel_format', ctypes.c_uint32),
        ('type', ctypes.c_uint32),
        ('_u16', _u16),
        ('reserved', ctypes.c_uint32*2),
    ]


#
# F R A M E   R A T E   E N U M E R A T I O N
#

v4l2_frmivaltypes = ctypes.c_uint

V4L2_FRMIVAL_TYPE_DISCRETE = 1
V4L2_FRMIVAL_TYPE_CONTINUOUS = 2
V4L2_FRMIVAL_TYPE_STEPWISE = 3


class v4l2_frmival_stepwise(ctypes.Structure):

    _fields_ = [
        ('min', v4l2_fract),
        ('max', v4l2_fract),
        ('step', v4l2_fract),
    ]


class v4l2_frmivalenum(ctypes.Structure):
    # $OBJ-00014
    class _u20(ctypes.Union):

        _fields_ = [
            ('discrete', v4l2_fract),
            ('stepwise', v4l2_frmival_stepwise),
        ]

    _fields_ = [
        ('index', ctypes.c_uint32),
        ('pixel_format', ctypes.c_uint32),
        ('width', ctypes.c_uint32),
        ('height', ctypes.c_uint32),
        ('type', ctypes.c_uint32),
        ('_u20', _u20),
        ('reserved', ctypes.c_uint32*2),
    ]


#
# T I M E C O D E
#

class v4l2_timecode(ctypes.Structure):

    _fields_ = [
        ('type', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('frames', ctypes.c_uint8),
        ('seconds', ctypes.c_uint8),
        ('minutes', ctypes.c_uint8),
        ('hours', ctypes.c_uint8),
        ('userbits', ctypes.c_uint8*4),
    ]


#  Type
V4L2_TC_TYPE_24FPS = 1
V4L2_TC_TYPE_25FPS = 2
V4L2_TC_TYPE_30FPS = 3
V4L2_TC_TYPE_50FPS = 4
V4L2_TC_TYPE_60FPS = 5


#  Flags
V4L2_TC_FLAG_DROPFRAME = 0x0001
# "drop-frame" mode
V4L2_TC_FLAG_COLORFRAME = 0x0002
V4L2_TC_USERBITS_field = 0x000C
V4L2_TC_USERBITS_USERDEFINED = 0x0000
V4L2_TC_USERBITS_8BITCHARS = 0x0008

# The above is based on SMPTE timecodes


class v4l2_jpegcompression(ctypes.Structure):

    _fields_ = [
        ('quality', ctypes.c_int),
        ('APPn', ctypes.c_int),
        ('APP_len', ctypes.c_int),
        ('APP_data', ctypes.c_char*60),
        ('COM_len', ctypes.c_int),
        ('COM_data', ctypes.c_char*60),
        ('jpeg_markers', ctypes.c_uint32),
    ]


#
# M E M O R Y - M A P P I N G   B U F F E R S
#

class v4l2_requestbuffers(ctypes.Structure):

    _fields_ = [
        ('count', ctypes.c_uint32),
        ('type', ctypes.c_uint32),
        ('memory', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*2),
    ]


#
# struct v4l2_plane - plane info for multi-planar buffers
# @bytesused:  number of bytes occupied by data in the plane (payload)
# @length:  size of this plane (NOT the payload) in bytes
# @mem_offset:  when memory in the associated struct v4l2_buffer is
#   V4L2_MEMORY_MMAP, equals the offset from the start of
#   the device memory for this plane (or is a "cookie" that
#   should be passed to mmap() called on the video node)
# @userptr:  when memory is V4L2_MEMORY_USERPTR, a userspace pointer
#   pointing to this plane
# @fd:   when memory is V4L2_MEMORY_DMABUF, a userspace file
#   descriptor associated with this plane
# @data_offset: offset in the plane to the start of data; usually 0,
#   unless there is a header in front of the data
#
# Multi-planar buffers consist of one or more planes, e.g. an YCbCr buffer
# with two planes can have one plane for Y, and another for interleaved CbCr
# components. Each plane can reside in a separate memory buffer, or even in
# a completely separate memory node (e.g. in embedded devices).
#

class v4l2_plane(ctypes.Structure):
    # $OBJ-00019
    class _u25(ctypes.Union):

        _fields_ = [
            ('mem_offset', ctypes.c_uint32),
            ('userptr', ctypes.c_uint32),
            ('fd', ctypes.c_int32),
        ]

    _fields_ = [
        ('bytesused', ctypes.c_uint32),
        ('length', ctypes.c_uint32),
        ('m', _u25),
        ('data_offset', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*11),
    ]


#
# struct v4l2_buffer - video buffer info
# @index: id number of the buffer
# @type: enum v4l2_buf_type; buffer type (type == *_MPLANE for
#  multiplanar buffers);
# @bytesused: number of bytes occupied by data in the buffer (payload);
#  unused (set to 0) for multiplanar buffers
# @flags: buffer informational flags
# @field: enum v4l2_field; field order of the image in the buffer
# @timestamp: frame timestamp
# @timecode: frame timecode
# @sequence: sequence count of this frame
# @memory: enum v4l2_memory; the method, in which the actual video data is
#  passed
# @offset: for non-multiplanar buffers with memory == V4L2_MEMORY_MMAP;
#  offset from the start of the device memory for this plane,
#  (or a "cookie" that should be passed to mmap() as offset)
# @userptr: for non-multiplanar buffers with memory == V4L2_MEMORY_USERPTR;
#  a userspace pointer pointing to this buffer
# @fd:  for non-multiplanar buffers with memory == V4L2_MEMORY_DMABUF;
#  a userspace file descriptor associated with this buffer
# @planes: for multiplanar buffers; userspace pointer to the array of plane
#  info structs for this buffer
# @length: size in bytes of the buffer (NOT its payload) for single-plane
#  buffers (when type != *_MPLANE); number of elements in the
#  planes array for multi-plane buffers
# @input: input number from which the video data has has been captured
#
# Contains data exchanged by application and driver using one of the Streaming
# I/O methods.
#

class v4l2_buffer(ctypes.Structure):
    # $OBJ-0001B
    class _u27(ctypes.Union):

        _fields_ = [
            ('offset', ctypes.c_uint32),
            ('userptr', ctypes.c_uint32),
            ('planes', ctypes.POINTER(v4l2_plane)),
            ('fd', ctypes.c_int32),
        ]

    _fields_ = [
        ('index', ctypes.c_uint32),
        ('type', ctypes.c_uint32),
        ('bytesused', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('field', ctypes.c_uint32),
        ('timestamp', timeval),
        ('timecode', v4l2_timecode),
        ('sequence', ctypes.c_uint32),
        ('memory', ctypes.c_uint32),
        ('m', _u27),
        ('length', ctypes.c_uint32),
        ('reserved2', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32),
    ]


#  Flags for 'flags' field
V4L2_BUF_FLAG_MAPPED = 0x0001
# Buffer is mapped (flag)
V4L2_BUF_FLAG_QUEUED = 0x0002
# Buffer is queued for processing
V4L2_BUF_FLAG_DONE = 0x0004
# Buffer is ready
V4L2_BUF_FLAG_KEYFRAME = 0x0008
# Image is a keyframe (I-frame)
V4L2_BUF_FLAG_PFRAME = 0x0010
# Image is a P-frame
V4L2_BUF_FLAG_BFRAME = 0x0020
# Image is a B-frame

# Buffer is ready, but the data contained within is corrupted.
V4L2_BUF_FLAG_ERROR = 0x0040
V4L2_BUF_FLAG_TIMECODE = 0x0100
# timecode field is valid
V4L2_BUF_FLAG_PREPARED = 0x0400
# Buffer is prepared for queuing

# Cache handling flags
V4L2_BUF_FLAG_NO_CACHE_INVALIDATE = 0x0800
V4L2_BUF_FLAG_NO_CACHE_CLEAN = 0x1000

# Timestamp type
V4L2_BUF_FLAG_TIMESTAMP_MASK = 0xe000
V4L2_BUF_FLAG_TIMESTAMP_UNKNOWN = 0x0000
V4L2_BUF_FLAG_TIMESTAMP_MONOTONIC = 0x2000
V4L2_BUF_FLAG_TIMESTAMP_COPY = 0x4000


#
# struct v4l2_exportbuffer - export of video buffer as DMABUF file descriptor
#
# @index: id number of the buffer
# @type: enum v4l2_buf_type; buffer type (type == *_MPLANE for
#  multiplanar buffers);
# @plane: index of the plane to be exported, 0 for single plane queues
# @flags: flags for newly created file, currently only O_CLOEXEC is
#  supported, refer to manual of open syscall for more details
# @fd:  file descriptor associated with DMABUF (set by driver)
#
# Contains data used for exporting a video buffer as DMABUF file descriptor.
# The buffer is identified by a 'cookie' returned by VIDIOC_QUERYBUF
# (identical to the cookie used to mmap() the buffer to userspace). All
# reserved fields must be set to zero. The field reserved0 is expected to
# become a structure 'type' allowing an alternative layout of the structure
# content. Therefore this field should not be used for any other extensions.
#

class v4l2_exportbuffer(ctypes.Structure):

    _fields_ = [
        ('type', ctypes.c_uint32),
        ('index', ctypes.c_uint32),
        ('plane', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('fd', ctypes.c_int32),
        ('reserved', ctypes.c_uint32*11),
    ]


#
# O V E R L A Y   P R E V I E W
#

class v4l2_framebuffer(ctypes.Structure):

    _fields_ = [
        ('capability', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('base', ctypes.POINTER(ctypes.c_void_p)),
        ('fmt', v4l2_pix_format),
    ]


#  Flags for the 'capability' field. Read only
V4L2_FBUF_CAP_EXTERNOVERLAY = 0x0001
V4L2_FBUF_CAP_CHROMAKEY = 0x0002
V4L2_FBUF_CAP_LIST_CLIPPING = 0x0004
V4L2_FBUF_CAP_BITMAP_CLIPPING = 0x0008
V4L2_FBUF_CAP_LOCAL_ALPHA = 0x0010
V4L2_FBUF_CAP_GLOBAL_ALPHA = 0x0020
V4L2_FBUF_CAP_LOCAL_INV_ALPHA = 0x0040
V4L2_FBUF_CAP_SRC_CHROMAKEY = 0x0080

#  Flags for the 'flags' field.
V4L2_FBUF_FLAG_PRIMARY = 0x0001
V4L2_FBUF_FLAG_OVERLAY = 0x0002
V4L2_FBUF_FLAG_CHROMAKEY = 0x0004
V4L2_FBUF_FLAG_LOCAL_ALPHA = 0x0008
V4L2_FBUF_FLAG_GLOBAL_ALPHA = 0x0010
V4L2_FBUF_FLAG_LOCAL_INV_ALPHA = 0x0020
V4L2_FBUF_FLAG_SRC_CHROMAKEY = 0x0040


class v4l2_clip(ctypes.Structure):
    pass

v4l2_clip._fields_ = [
    ('c', v4l2_rect),
    ('next', ctypes.POINTER(v4l2_clip)),
]


class v4l2_window(ctypes.Structure):

    _fields_ = [
        ('w', v4l2_rect),
        ('field', ctypes.c_uint32),
        ('chromakey', ctypes.c_uint32),
        ('clips', ctypes.POINTER(v4l2_clip)),
        ('clipcount', ctypes.c_uint32),
        ('bitmap', ctypes.POINTER(ctypes.c_void_p)),
        ('global_alpha', ctypes.c_uint8),
    ]


#
# C A P T U R E   P A R A M E T E R S
#

class v4l2_captureparm(ctypes.Structure):

    _fields_ = [
        ('capability', ctypes.c_uint32),
        ('capturemode', ctypes.c_uint32),
        ('timeperframe', v4l2_fract),
        ('extendedmode', ctypes.c_uint32),
        ('readbuffers', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*4),
    ]


#  Flags for 'capability' and 'capturemode' fields
V4L2_MODE_HIGHQUALITY = 0x0001
#  High quality imaging mode
V4L2_CAP_TIMEPERFRAME = 0x1000
#  timeperframe field is supported


class v4l2_outputparm(ctypes.Structure):

    _fields_ = [
        ('capability', ctypes.c_uint32),
        ('outputmode', ctypes.c_uint32),
        ('timeperframe', v4l2_fract),
        ('extendedmode', ctypes.c_uint32),
        ('writebuffers', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*4),
    ]


#
# I N P U T   I M A G E   C R O P P I N G
#

class v4l2_cropcap(ctypes.Structure):

    _fields_ = [
        ('type', ctypes.c_uint32),
        ('bounds', v4l2_rect),
        ('defrect', v4l2_rect),
        ('pixelaspect', v4l2_fract),
    ]


class v4l2_crop(ctypes.Structure):

    _fields_ = [
        ('type', ctypes.c_uint32),
        ('c', v4l2_rect),
    ]


#
# struct v4l2_selection - selection info
# @type: buffer type (do not use *_MPLANE types)
# @target: Selection target, used to choose one of possible rectangles;
#  defined in v4l2-common.h; V4L2_SEL_TGT_* .
# @flags: constraints flags, defined in v4l2-common.h; V4L2_SEL_FLAG_*.
# @r:  coordinates of selection window
# @reserved: for future use, rounds structure size to 64 bytes, set to zero
#
# Hardware may use multiple helper windows to process a video stream.
# The structure is used to exchange this selection areas between
# an application and a driver.
#

class v4l2_selection(ctypes.Structure):

    _fields_ = [
        ('type', ctypes.c_uint32),
        ('target', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('r', v4l2_rect),
        ('reserved', ctypes.c_uint32*9),
    ]


#
#      A N A L O G   V I D E O   S T A N D A R D
#

v4l2_std_id = ctypes.c_uint64

# one bit for each
V4L2_STD_PAL_B = 0x00000001
V4L2_STD_PAL_B1 = 0x00000002
V4L2_STD_PAL_G = 0x00000004
V4L2_STD_PAL_H = 0x00000008
V4L2_STD_PAL_I = 0x00000010
V4L2_STD_PAL_D = 0x00000020
V4L2_STD_PAL_D1 = 0x00000040
V4L2_STD_PAL_K = 0x00000080

V4L2_STD_PAL_M = 0x00000100
V4L2_STD_PAL_N = 0x00000200
V4L2_STD_PAL_Nc = 0x00000400
V4L2_STD_PAL_60 = 0x00000800

V4L2_STD_NTSC_M = 0x00001000
# BTSC
V4L2_STD_NTSC_M_JP = 0x00002000
# EIA-J
V4L2_STD_NTSC_443 = 0x00004000
V4L2_STD_NTSC_M_KR = 0x00008000
# FM A2

V4L2_STD_SECAM_B = 0x00010000
V4L2_STD_SECAM_D = 0x00020000
V4L2_STD_SECAM_G = 0x00040000
V4L2_STD_SECAM_H = 0x00080000
V4L2_STD_SECAM_K = 0x00100000
V4L2_STD_SECAM_K1 = 0x00200000
V4L2_STD_SECAM_L = 0x00400000
V4L2_STD_SECAM_LC = 0x00800000


# ATSC/HDTV
V4L2_STD_ATSC_8_VSB = 0x01000000
V4L2_STD_ATSC_16_VSB = 0x02000000


# FIXME:
# Although std_id is 64 bits, there is an issue on PPC32 architecture that
# makes switch(ctypes.c_uint64) to break. So, there's a hack on v4l2-common.c
# rounding this value to 32 bits.
# As, currently, the max value is for V4L2_STD_ATSC_16_VSB (30 bits wide),
# it should work fine. However, if needed to add more than two standards,
# v4l2-common.c should be fixed.
#


#
# Some macros to merge video standards in order to make live easier for the
# drivers and V4L2 applications
#


#
# "Common" NTSC/M - It should be noticed that V4L2_STD_NTSC_443 is
# Missing here.
#
V4L2_STD_NTSC = (V4L2_STD_NTSC_M |
                 V4L2_STD_NTSC_M_JP |
                 V4L2_STD_NTSC_M_KR)

# Secam macros
V4L2_STD_SECAM_DK = (V4L2_STD_SECAM_D |
                     V4L2_STD_SECAM_K |
                     V4L2_STD_SECAM_K1)

# All Secam Standards
V4L2_STD_SECAM = (V4L2_STD_SECAM_B |
                  V4L2_STD_SECAM_G |
                  V4L2_STD_SECAM_H |
                  V4L2_STD_SECAM_DK |
                  V4L2_STD_SECAM_L |
                  V4L2_STD_SECAM_LC)

# PAL macros
V4L2_STD_PAL_BG = (V4L2_STD_PAL_B |
                   V4L2_STD_PAL_B1 |
                   V4L2_STD_PAL_G)

V4L2_STD_PAL_DK = (V4L2_STD_PAL_D |
                   V4L2_STD_PAL_D1 |
                   V4L2_STD_PAL_K)

#
# "Common" PAL - This macro is there to be compatible with the old
# V4L1 concept of "PAL": /BGDKHI.
# Several PAL standards are missing here: /M, /N and /Nc
#
V4L2_STD_PAL = (V4L2_STD_PAL_BG |
                V4L2_STD_PAL_DK |
                V4L2_STD_PAL_H |
                V4L2_STD_PAL_I)

# Chroma "agnostic" standards
V4L2_STD_B = (V4L2_STD_PAL_B |
              V4L2_STD_PAL_B1 |
              V4L2_STD_SECAM_B)

V4L2_STD_G = (V4L2_STD_PAL_G |
              V4L2_STD_SECAM_G)

V4L2_STD_H = (V4L2_STD_PAL_H |
              V4L2_STD_SECAM_H)

V4L2_STD_L = (V4L2_STD_SECAM_L |
              V4L2_STD_SECAM_LC)

V4L2_STD_GH = (V4L2_STD_G |
               V4L2_STD_H)

V4L2_STD_DK = (V4L2_STD_PAL_DK |
               V4L2_STD_SECAM_DK)

V4L2_STD_BG = (V4L2_STD_B |
               V4L2_STD_G)

V4L2_STD_MN = (V4L2_STD_PAL_M |
               V4L2_STD_PAL_N |
               V4L2_STD_PAL_Nc |
               V4L2_STD_NTSC)


# Standards where MTS/BTSC stereo could be found
V4L2_STD_MTS = (V4L2_STD_NTSC_M |
                V4L2_STD_PAL_M |
                V4L2_STD_PAL_N |
                V4L2_STD_PAL_Nc)


# Standards for Countries with 60Hz Line frequency
V4L2_STD_525_60 = (V4L2_STD_PAL_M |
                   V4L2_STD_PAL_60 |
                   V4L2_STD_NTSC |
                   V4L2_STD_NTSC_443)

# Standards for Countries with 50Hz Line frequency
V4L2_STD_625_50 = (V4L2_STD_PAL |
                   V4L2_STD_PAL_N |
                   V4L2_STD_PAL_Nc |
                   V4L2_STD_SECAM)

V4L2_STD_ATSC = (V4L2_STD_ATSC_8_VSB |
                 V4L2_STD_ATSC_16_VSB)

# Macros with none and all analog standards
V4L2_STD_UNKNOWN = 0
V4L2_STD_ALL = (V4L2_STD_525_60 |
                V4L2_STD_625_50)


class v4l2_standard(ctypes.Structure):

    _fields_ = [
        ('index', ctypes.c_uint32),
        ('id', v4l2_std_id),
        ('name', ctypes.c_char*24),
        ('frameperiod', v4l2_fract),
        ('framelines', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*4),
    ]


#
# D V  B T T I M I N G S
#


# struct v4l2_bt_timings - BT.656/BT.1120 timing data
# @width: total width of the active video in pixels
# @height: total height of the active video in lines
# @interlaced: Interlaced or progressive
# @polarities: Positive or negative polarities
# @pixelclock: Pixel clock in HZ. Ex. 74.25MHz->74250000
# @hfrontporch:Horizontal front porch in pixels
# @hsync: Horizontal Sync length in pixels
# @hbackporch: Horizontal back porch in pixels
# @vfrontporch:Vertical front porch in lines
# @vsync: Vertical Sync length in lines
# @vbackporch: Vertical back porch in lines
# @il_vfrontporch:Vertical front porch for the even field
#  (aka field 2) of interlaced field formats
# @il_vsync: Vertical Sync length for the even field
#  (aka field 2) of interlaced field formats
# @il_vbackporch:Vertical back porch for the even field
#  (aka field 2) of interlaced field formats
# @standards: Standards the timing belongs to
# @flags: Flags
# @reserved: Reserved fields, must be zeroed.
#
# A note regarding vertical interlaced timings: height refers to the total
# height of the active video frame (= two fields). The blanking timings refer
# to the blanking of each field. So the height of the total frame is
# calculated as follows:
#
# tot_height = height + vfrontporch + vsync + vbackporch +
#                       il_vfrontporch + il_vsync + il_vbackporch
#
# The active height of each field is height / 2.
#

class v4l2_bt_timings(ctypes.Structure):

    _pack_ = 1

    _fields_ = [
        ('width', ctypes.c_uint32),
        ('height', ctypes.c_uint32),
        ('interlaced', ctypes.c_uint32),
        ('polarities', ctypes.c_uint32),
        ('pixelclock', ctypes.c_uint64),
        ('hfrontporch', ctypes.c_uint32),
        ('hsync', ctypes.c_uint32),
        ('hbackporch', ctypes.c_uint32),
        ('vfrontporch', ctypes.c_uint32),
        ('vsync', ctypes.c_uint32),
        ('vbackporch', ctypes.c_uint32),
        ('il_vfrontporch', ctypes.c_uint32),
        ('il_vsync', ctypes.c_uint32),
        ('il_vbackporch', ctypes.c_uint32),
        ('standards', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*14),
    ]


# Interlaced or progressive format
V4L2_DV_PROGRESSIVE = 0
V4L2_DV_INTERLACED = 1


# Polarities. If bit is not set, it is assumed to be negative polarity
V4L2_DV_VSYNC_POS_POL = 0x00000001
V4L2_DV_HSYNC_POS_POL = 0x00000002


# Timings standards
V4L2_DV_BT_STD_CEA861 = 1 << 0  # CEA-861 Digital TV Profile
V4L2_DV_BT_STD_DMT = 1 << 1  # VESA Discrete Monitor Timings
V4L2_DV_BT_STD_CVT = 1 << 2  # VESA Coordinated Video Timings
V4L2_DV_BT_STD_GTF = 1 << 3  # VESA Generalized Timings Formula


# Flags


# CVT/GTF specific: timing uses reduced blanking (CVT) or the 'Secondary
# GTF' curve (GTF). In both cases the horizontal and/or vertical blanking
# intervals are reduced, allowing a higher resolution over the same
# bandwidth. This is a read-only flag.
V4L2_DV_FL_REDUCED_BLANKING = (1 << 0)

# CEA-861 specific: set for CEA-861 formats with a framerate of a multiple
# of six. These formats can be optionally played at 1 / 1.001 speed.
# This is a read-only flag.
V4L2_DV_FL_CAN_REDUCE_FPS = (1 << 1)

# CEA-861 specific: only valid for video transmitters, the flag is cleared
# by receivers.
# If the framerate of the format is a multiple of six, then the pixelclock
# used to set up the transmitter is divided by 1.001 to make it compatible
# with 60 Hz based standards such as NTSC and PAL-M that use a framerate of
# 29.97 Hz. Otherwise this flag is cleared. If the transmitter can't generate
# such frequencies, then the flag will also be cleared.
V4L2_DV_FL_REDUCED_FPS = (1 << 2)

# Specific to interlaced formats: if set, then field 1 is really one half-line
# longer and field 2 is really one half-line shorter, so each field has
# exactly the same number of half-lines. Whether half-lines can be detected
# or used depends on the hardware.
V4L2_DV_FL_HALF_LINE = (1 << 3)


# A few useful defines to calculate the total blanking and frame sizes
def V4L2_DV_BT_BLANKING_WIDTH(bt):
    return (bt.hfrontporch + bt.hsync + bt.hbackporch)


def V4L2_DV_BT_FRAME_WIDTH(bt):
    return (bt.width + V4L2_DV_BT_BLANKING_WIDTH(bt))


def V4L2_DV_BT_BLANKING_HEIGHT(bt):
    return (bt.vfrontporch + bt.vsync + bt.vbackporch +
            bt.il_vfrontporch + bt.il_vsync + bt.il_vbackporch)


def V4L2_DV_BT_FRAME_HEIGHT(bt):
    return (bt.height + V4L2_DV_BT_BLANKING_HEIGHT(bt))


# struct v4l2_dv_timings - DV timings
# @type: the type of the timings
# @bt: BT656/1120 timings
#

class v4l2_dv_timings(ctypes.Structure):
    # $OBJ-00028
    class _u40(ctypes.Union):

        _fields_ = [
            ('bt', v4l2_bt_timings),
            ('reserved', ctypes.c_uint32*32),
        ]

    _pack_ = 1

    _fields_ = [
        ('type', ctypes.c_uint32),
        ('_u40', _u40),
    ]


# Values for the type field
V4L2_DV_BT_656_1120 = 0
# BT.656/1120 timing type


# struct v4l2_enum_dv_timings - DV timings enumeration
# @index: enumeration index
# @reserved: must be zeroed
# @timings: the timings for the given index
#

class v4l2_enum_dv_timings(ctypes.Structure):

    _fields_ = [
        ('index', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*3),
        ('timings', v4l2_dv_timings),
    ]


# struct v4l2_bt_timings_cap - BT.656/BT.1120 timing capabilities
# @min_width:  width in pixels
# @max_width:  width in pixels
# @min_height:  height in lines
# @max_height:  height in lines
# @min_pixelclock: Pixel clock in HZ. Ex. 74.25MHz->74250000
# @max_pixelclock: Pixel clock in HZ. Ex. 74.25MHz->74250000
# @standards:  Supported standards
# @capabilities: Supported capabilities
# @reserved:  Must be zeroed
#

class v4l2_bt_timings_cap(ctypes.Structure):

    _pack_ = 1

    _fields_ = [
        ('min_width', ctypes.c_uint32),
        ('max_width', ctypes.c_uint32),
        ('min_height', ctypes.c_uint32),
        ('max_height', ctypes.c_uint32),
        ('min_pixelclock', ctypes.c_uint64),
        ('max_pixelclock', ctypes.c_uint64),
        ('standards', ctypes.c_uint32),
        ('capabilities', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*16),
    ]


# Supports interlaced formats
V4L2_DV_BT_CAP_INTERLACED = (1 << 0)

# Supports progressive formats
V4L2_DV_BT_CAP_PROGRESSIVE = (1 << 1)

# Supports CVT/GTF reduced blanking
V4L2_DV_BT_CAP_REDUCED_BLANKING = (1 << 2)

# Supports custom formats
V4L2_DV_BT_CAP_CUSTOM = (1 << 3)


# struct v4l2_dv_timings_cap - DV timings capabilities
# @type: the type of the timings (same as in struct v4l2_dv_timings)
# @bt:  the BT656/1120 timings capabilities
#

class v4l2_dv_timings_cap(ctypes.Structure):
    # $OBJ-0002C
    class _u44(ctypes.Union):

        _fields_ = [
            ('bt', v4l2_bt_timings_cap),
            ('raw_data', ctypes.c_uint32*32),
        ]

    _fields_ = [
        ('type', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*3),
        ('_u44', _u44),
    ]


#
# V I D E O   I N P U T S
#

class v4l2_input(ctypes.Structure):

    _fields_ = [
        ('index', ctypes.c_uint32),
        ('name', ctypes.c_char*32),
        ('type', ctypes.c_uint32),
        ('audioset', ctypes.c_uint32),
        ('tuner', ctypes.c_uint32),
        ('std', v4l2_std_id),
        ('status', ctypes.c_uint32),
        ('capabilities', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*3),
    ]


#  Values for the 'type' field
V4L2_INPUT_TYPE_TUNER = 1
V4L2_INPUT_TYPE_CAMERA = 2

# field 'status' - general
V4L2_IN_ST_NO_POWER = 0x00000001
# Attached device is off
V4L2_IN_ST_NO_SIGNAL = 0x00000002
V4L2_IN_ST_NO_COLOR = 0x00000004


# field 'status' - sensor orientation

# If sensor is mounted upside down set both bits
V4L2_IN_ST_HFLIP = 0x00000010
# Frames are flipped horizontally
V4L2_IN_ST_VFLIP = 0x00000020
# Frames are flipped vertically


# field 'status' - analog
V4L2_IN_ST_NO_H_LOCK = 0x00000100
# No horizontal sync lock
V4L2_IN_ST_COLOR_KILL = 0x00000200
# Color killer is active


# field 'status' - digital
V4L2_IN_ST_NO_SYNC = 0x00010000
# No synchronization lock
V4L2_IN_ST_NO_EQU = 0x00020000
# No equalizer lock
V4L2_IN_ST_NO_CARRIER = 0x00040000
# Carrier recovery failed


# field 'status' - VCR and set-top box
V4L2_IN_ST_MACROVISION = 0x01000000
# Macrovision detected
V4L2_IN_ST_NO_ACCESS = 0x02000000
# Conditional access denied
V4L2_IN_ST_VTR = 0x04000000
# VTR time constant


# capabilities flags
V4L2_IN_CAP_DV_TIMINGS = 0x00000002
# Supports S_DV_TIMINGS
V4L2_IN_CAP_CUSTOM_TIMINGS = V4L2_IN_CAP_DV_TIMINGS
# For compatibility
V4L2_IN_CAP_STD = 0x00000004
# Supports S_STD


#
# V I D E O   O U T P U T S
#

class v4l2_output(ctypes.Structure):

    _fields_ = [
        ('index', ctypes.c_uint32),
        ('name', ctypes.c_char*32),
        ('type', ctypes.c_uint32),
        ('audioset', ctypes.c_uint32),
        ('modulator', ctypes.c_uint32),
        ('std', v4l2_std_id),
        ('capabilities', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*3),
    ]


#  Values for the 'type' field
V4L2_OUTPUT_TYPE_MODULATOR = 1
V4L2_OUTPUT_TYPE_ANALOG = 2
V4L2_OUTPUT_TYPE_ANALOGVGAOVERLAY = 3


# capabilities flags
V4L2_OUT_CAP_DV_TIMINGS = 0x00000002
# Supports S_DV_TIMINGS
V4L2_OUT_CAP_CUSTOM_TIMINGS = V4L2_OUT_CAP_DV_TIMINGS
# For compatibility
V4L2_OUT_CAP_STD = 0x00000004
# Supports S_STD


#
# C O N T R O L S
#

class v4l2_control(ctypes.Structure):

    _fields_ = [
        ('id', ctypes.c_uint32),
        ('value', ctypes.c_int32),
    ]


class v4l2_ext_control(ctypes.Structure):
    # $OBJ-00031
    class _u49(ctypes.Union):

        _fields_ = [
            ('value', ctypes.c_int32),
            ('value64', ctypes.c_int64),
            ('string', ctypes.POINTER(ctypes.c_char)),
        ]

    _pack_ = 1

    _fields_ = [
        ('id', ctypes.c_uint32),
        ('size', ctypes.c_uint32),
        ('reserved2', ctypes.c_uint32*1),
        ('_u49', _u49),
    ]


class v4l2_ext_controls(ctypes.Structure):

    _fields_ = [
        ('ctrl_class', ctypes.c_uint32),
        ('count', ctypes.c_uint32),
        ('error_idx', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*2),
        ('controls', ctypes.POINTER(v4l2_ext_control)),
    ]


V4L2_CTRL_ID_MASK = (0x0fffffff)


def V4L2_CTRL_ID2CLASS(id):
    return ((id) & 0x0fff0000)


def V4L2_CTRL_DRIVER_PRIV(id):
    return (((id) & 0xffff) >= 0x1000)


v4l2_ctrl_type = ctypes.c_uint

V4L2_CTRL_TYPE_INTEGER = 1
V4L2_CTRL_TYPE_BOOLEAN = 2
V4L2_CTRL_TYPE_MENU = 3
V4L2_CTRL_TYPE_BUTTON = 4
V4L2_CTRL_TYPE_INTEGER64 = 5
V4L2_CTRL_TYPE_CTRL_CLASS = 6
V4L2_CTRL_TYPE_STRING = 7
V4L2_CTRL_TYPE_BITMASK = 8
V4L2_CTRL_TYPE_INTEGER_MENU = 9


#  Used in the VIDIOC_QUERYCTRL ioctl for querying controls

class v4l2_queryctrl(ctypes.Structure):

    _fields_ = [
        ('id', ctypes.c_uint32),
        ('type', ctypes.c_uint32),
        ('name', ctypes.c_char*32),
        ('minimum', ctypes.c_int32),
        ('maximum', ctypes.c_int32),
        ('step', ctypes.c_int32),
        ('default_value', ctypes.c_int32),
        ('flags', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*2),
    ]


#  Used in the VIDIOC_QUERYMENU ioctl for querying menu items

class v4l2_querymenu(ctypes.Structure):
    # $OBJ-00036
    class _u54(ctypes.Union):

        _fields_ = [
            ('name', ctypes.c_char*32),
            ('value', ctypes.c_int64),
        ]

    _pack_ = 1

    _fields_ = [
        ('id', ctypes.c_uint32),
        ('index', ctypes.c_uint32),
        ('_u54', _u54),
        ('reserved', ctypes.c_uint32),
    ]


#  Control flags
V4L2_CTRL_FLAG_DISABLED = 0x0001
V4L2_CTRL_FLAG_GRABBED = 0x0002
V4L2_CTRL_FLAG_READ_ONLY = 0x0004
V4L2_CTRL_FLAG_UPDATE = 0x0008
V4L2_CTRL_FLAG_INACTIVE = 0x0010
V4L2_CTRL_FLAG_SLIDER = 0x0020
V4L2_CTRL_FLAG_WRITE_ONLY = 0x0040
V4L2_CTRL_FLAG_VOLATILE = 0x0080


#  Query flag, to be ORed with the control ID
V4L2_CTRL_FLAG_NEXT_CTRL = 0x80000000


#  User-class control IDs defined by V4L2
V4L2_CID_MAX_CTRLS = 1024

#  IDs reserved for driver specific controls
V4L2_CID_PRIVATE_BASE = 0x08000000


#
# T U N I N G
#

class v4l2_tuner(ctypes.Structure):

    _fields_ = [
        ('index', ctypes.c_uint32),
        ('name', ctypes.c_char*32),
        ('type', ctypes.c_uint32),
        ('capability', ctypes.c_uint32),
        ('rangelow', ctypes.c_uint32),
        ('rangehigh', ctypes.c_uint32),
        ('rxsubchans', ctypes.c_uint32),
        ('audmode', ctypes.c_uint32),
        ('signal', ctypes.c_int32),
        ('afc', ctypes.c_int32),
        ('reserved', ctypes.c_uint32*4),
    ]


class v4l2_modulator(ctypes.Structure):

    _fields_ = [
        ('index', ctypes.c_uint32),
        ('name', ctypes.c_char*32),
        ('capability', ctypes.c_uint32),
        ('rangelow', ctypes.c_uint32),
        ('rangehigh', ctypes.c_uint32),
        ('txsubchans', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*4),
    ]


#  Flags for the 'capability' field
V4L2_TUNER_CAP_LOW = 0x0001
V4L2_TUNER_CAP_NORM = 0x0002
V4L2_TUNER_CAP_HWSEEK_BOUNDED = 0x0004
V4L2_TUNER_CAP_HWSEEK_WRAP = 0x0008
V4L2_TUNER_CAP_STEREO = 0x0010
V4L2_TUNER_CAP_LANG2 = 0x0020
V4L2_TUNER_CAP_SAP = 0x0020
V4L2_TUNER_CAP_LANG1 = 0x0040
V4L2_TUNER_CAP_RDS = 0x0080
V4L2_TUNER_CAP_RDS_BLOCK_IO = 0x0100
V4L2_TUNER_CAP_RDS_CONTROLS = 0x0200
V4L2_TUNER_CAP_FREQ_BANDS = 0x0400
V4L2_TUNER_CAP_HWSEEK_PROG_LIM = 0x0800


#  Flags for the 'rxsubchans' field
V4L2_TUNER_SUB_MONO = 0x0001
V4L2_TUNER_SUB_STEREO = 0x0002
V4L2_TUNER_SUB_LANG2 = 0x0004
V4L2_TUNER_SUB_SAP = 0x0004
V4L2_TUNER_SUB_LANG1 = 0x0008
V4L2_TUNER_SUB_RDS = 0x0010


#  Values for the 'audmode' field
V4L2_TUNER_MODE_MONO = 0x0000
V4L2_TUNER_MODE_STEREO = 0x0001
V4L2_TUNER_MODE_LANG2 = 0x0002
V4L2_TUNER_MODE_SAP = 0x0002
V4L2_TUNER_MODE_LANG1 = 0x0003
V4L2_TUNER_MODE_LANG1_LANG2 = 0x0004


class v4l2_frequency(ctypes.Structure):

    _fields_ = [
        ('tuner', ctypes.c_uint32),
        ('type', ctypes.c_uint32),
        ('frequency', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*8),
    ]


V4L2_BAND_MODULATION_VSB = (1 << 1)
V4L2_BAND_MODULATION_FM = (1 << 2)
V4L2_BAND_MODULATION_AM = (1 << 3)


class v4l2_frequency_band(ctypes.Structure):

    _fields_ = [
        ('tuner', ctypes.c_uint32),
        ('type', ctypes.c_uint32),
        ('index', ctypes.c_uint32),
        ('capability', ctypes.c_uint32),
        ('rangelow', ctypes.c_uint32),
        ('rangehigh', ctypes.c_uint32),
        ('modulation', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*9),
    ]


class v4l2_hw_freq_seek(ctypes.Structure):

    _fields_ = [
        ('tuner', ctypes.c_uint32),
        ('type', ctypes.c_uint32),
        ('seek_upward', ctypes.c_uint32),
        ('wrap_around', ctypes.c_uint32),
        ('spacing', ctypes.c_uint32),
        ('rangelow', ctypes.c_uint32),
        ('rangehigh', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*5),
    ]


#
# R D S
#

class v4l2_rds_data(ctypes.Structure):

    _pack_ = 1

    _fields_ = [
        ('lsb', ctypes.c_uint8),
        ('msb', ctypes.c_uint8),
        ('block', ctypes.c_uint8),
    ]


V4L2_RDS_BLOCK_MSK = 0x7
V4L2_RDS_BLOCK_A = 0
V4L2_RDS_BLOCK_B = 1
V4L2_RDS_BLOCK_C = 2
V4L2_RDS_BLOCK_D = 3
V4L2_RDS_BLOCK_C_ALT = 4
V4L2_RDS_BLOCK_INVALID = 7

V4L2_RDS_BLOCK_CORRECTED = 0x40
V4L2_RDS_BLOCK_ERROR = 0x80


#
# A U D I O
#

class v4l2_audio(ctypes.Structure):

    _fields_ = [
        ('index', ctypes.c_uint32),
        ('name', ctypes.c_char*32),
        ('capability', ctypes.c_uint32),
        ('mode', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*2),
    ]


#  Flags for the 'capability' field
V4L2_AUDCAP_STEREO = 0x00001
V4L2_AUDCAP_AVL = 0x00002


#  Flags for the 'mode' field
V4L2_AUDMODE_AVL = 0x00001


class v4l2_audioout(ctypes.Structure):

    _fields_ = [
        ('index', ctypes.c_uint32),
        ('name', ctypes.c_char*32),
        ('capability', ctypes.c_uint32),
        ('mode', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*2),
    ]


#
# M P E G   S E R V I C E S
#
# NOTE: EXPERIMENTAL API
#
V4L2_ENC_IDX_FRAME_I = 0
V4L2_ENC_IDX_FRAME_P = 1
V4L2_ENC_IDX_FRAME_B = 2
V4L2_ENC_IDX_FRAME_MASK = 0xf


class v4l2_enc_idx_entry(ctypes.Structure):

    _fields_ = [
        ('offset', ctypes.c_uint64),
        ('pts', ctypes.c_uint64),
        ('length', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*2),
    ]


V4L2_ENC_IDX_ENTRIES = (64)


class v4l2_enc_idx(ctypes.Structure):

    _fields_ = [
        ('entries', ctypes.c_uint32),
        ('entries_cap', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*4),
        ('entry', v4l2_enc_idx_entry*V4L2_ENC_IDX_ENTRIES),
    ]


V4L2_ENC_CMD_START = (0)
V4L2_ENC_CMD_STOP = (1)
V4L2_ENC_CMD_PAUSE = (2)
V4L2_ENC_CMD_RESUME = (3)


# Flags for V4L2_ENC_CMD_STOP
V4L2_ENC_CMD_STOP_AT_GOP_END = (1 << 0)


class v4l2_encoder_cmd(ctypes.Structure):
    # $OBJ-00042
    class _u67(ctypes.Union):
        # $OBJ-00043
        class _s67(ctypes.Structure):

            _fields_ = [
                ('data', ctypes.c_uint32*8),
            ]

        _fields_ = [
            ('raw', _s67),
        ]

    _fields_ = [
        ('cmd', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('_u67', _u67),
    ]


# Decoder commands
V4L2_DEC_CMD_START = (0)
V4L2_DEC_CMD_STOP = (1)
V4L2_DEC_CMD_PAUSE = (2)
V4L2_DEC_CMD_RESUME = (3)


# Flags for V4L2_DEC_CMD_START
V4L2_DEC_CMD_START_MUTE_AUDIO = (1 << 0)


# Flags for V4L2_DEC_CMD_PAUSE
V4L2_DEC_CMD_PAUSE_TO_BLACK = (1 << 0)


# Flags for V4L2_DEC_CMD_STOP
V4L2_DEC_CMD_STOP_TO_BLACK = (1 << 0)
V4L2_DEC_CMD_STOP_IMMEDIATELY = (1 << 1)


# Play format requirements (returned by the driver):


# The decoder has no special format requirements
V4L2_DEC_START_FMT_NONE = (0)

# The decoder requires full GOPs
V4L2_DEC_START_FMT_GOP = (1)


# The structure must be zeroed before use by the application
# This ensures it can be extended safely in the future.

class v4l2_decoder_cmd(ctypes.Structure):

    # $OBJ-00045
    class _u72(ctypes.Union):

        # $OBJ-00046
        class _s70(ctypes.Structure):

            _fields_ = [
                ('pts', ctypes.c_uint64),
            ]

        # $OBJ-00047
        class _s71(ctypes.Structure):

            _fields_ = [
                ('speed', ctypes.c_int32),
                ('format', ctypes.c_uint32),
            ]

        # $OBJ-00048
        class _s72(ctypes.Structure):

            _fields_ = [
                ('data', ctypes.c_uint32*16),
            ]

        _fields_ = [
            ('stop', _s70),
            ('start', _s71),
            ('raw', _s72),
        ]

    _fields_ = [
        ('cmd', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('_u72', _u72),
    ]


#
# D A T A   S E R V I C E S   ( V B I )
#
# Data services API by Michael Schimek
#


# Raw VBI

class v4l2_vbi_format(ctypes.Structure):

    _fields_ = [
        ('sampling_rate', ctypes.c_uint32),
        ('offset', ctypes.c_uint32),
        ('samples_per_line', ctypes.c_uint32),
        ('sample_format', ctypes.c_uint32),
        ('start', ctypes.c_int32*2),
        ('count', ctypes.c_uint32*2),
        ('flags', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*2),
    ]


#  VBI flags
V4L2_VBI_UNSYNC = (1 << 0)
V4L2_VBI_INTERLACED = (1 << 1)


# Sliced VBI
#
#    This implements is a proposal V4L2 API to allow SLICED VBI
# required for some hardware encoders. It should change without
# notice in the definitive implementation.
#

class v4l2_sliced_vbi_format(ctypes.Structure):

    _fields_ = [
        ('service_set', ctypes.c_uint16),
        ('service_lines', ctypes.c_uint16*2),
        ('io_size', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*2),
    ]


# Teletext World System Teletext
# (WST), defined on ITU-R BT.653-2
V4L2_SLICED_TELETEXT_B = (0x0001)

# Video Program System, defined on ETS 300 231
V4L2_SLICED_VPS = (0x0400)

# Closed Caption, defined on EIA-608
V4L2_SLICED_CAPTION_525 = (0x1000)

# Wide Screen System, defined on ITU-R BT1119.1
V4L2_SLICED_WSS_625 = (0x4000)

V4L2_SLICED_VBI_525 = (V4L2_SLICED_CAPTION_525)
V4L2_SLICED_VBI_625 = (V4L2_SLICED_TELETEXT_B |
                       V4L2_SLICED_VPS |
                       V4L2_SLICED_WSS_625)


class v4l2_sliced_vbi_cap(ctypes.Structure):

    _fields_ = [
        ('service_set', ctypes.c_uint16),
        ('service_lines', ctypes.c_uint16*2),
        ('type', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*3),
    ]


class v4l2_sliced_vbi_data(ctypes.Structure):

    _fields_ = [
        ('id', ctypes.c_uint32),
        ('field', ctypes.c_uint32),
        ('line', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32),
        ('data', ctypes.c_uint8*48),
    ]


#
# Sliced VBI data inserted into MPEG Streams
#

#
# V4L2_MPEG_STREAM_VBI_FMT_IVTV:
#
# Structure of payload contained in an MPEG 2 Private Stream 1 PES Packet in an
# MPEG-2 Program Pack that contains V4L2_MPEG_STREAM_VBI_FMT_IVTV Sliced VBI
# data
#
# Note, the MPEG-2 Program Pack and Private Stream 1 PES packet header
# definitions are not included here.  See the MPEG-2 specifications for details
# on these headers.
#

# Line type IDs
V4L2_MPEG_VBI_IVTV_TELETEXT_B = (1)
V4L2_MPEG_VBI_IVTV_CAPTION_525 = (4)
V4L2_MPEG_VBI_IVTV_WSS_625 = (5)
V4L2_MPEG_VBI_IVTV_VPS = (7)


class v4l2_mpeg_vbi_itv0_line(ctypes.Structure):

    _pack_ = 1

    _fields_ = [
        ('id', ctypes.c_uint8),
        ('data', ctypes.c_uint8*42),
    ]


class v4l2_mpeg_vbi_itv0(ctypes.Structure):

    _pack_ = 1

    _fields_ = [
        ('linemask', ctypes.c_uint32*2),
        ('line', v4l2_mpeg_vbi_itv0_line*35),
    ]


class v4l2_mpeg_vbi_ITV0(ctypes.Structure):

    _pack_ = 1

    _fields_ = [
        ('line', v4l2_mpeg_vbi_itv0_line*36),
    ]


V4L2_MPEG_VBI_IVTV_MAGIC0 = "itv0"
V4L2_MPEG_VBI_IVTV_MAGIC1 = "ITV0"


class v4l2_mpeg_vbi_fmt_ivtv(ctypes.Structure):

    # $OBJ-00051
    class _u81(ctypes.Union):

        _fields_ = [
            ('itv0', v4l2_mpeg_vbi_itv0),
            ('ITV0', v4l2_mpeg_vbi_ITV0),
        ]

    _pack_ = 1

    _fields_ = [
        ('magic', ctypes.c_uint8*4),
        ('_u81', _u81),
    ]


#
# A G G R E G A T E   S T R U C T U R E S
#


#
# struct v4l2_plane_pix_format - additional, per-plane format definition
# @sizeimage:  maximum size in bytes required for data, for which
#   this plane will be used
# @bytesperline: distance in bytes between the leftmost pixels in two
#   adjacent lines
#

class v4l2_plane_pix_format(ctypes.Structure):

    _pack_ = 1

    _fields_ = [
        ('sizeimage', ctypes.c_uint32),
        ('bytesperline', ctypes.c_uint16),
        ('reserved', ctypes.c_uint16*7),
    ]


#
# struct v4l2_pix_format_mplane - multiplanar format definition
# @width:  image width in pixels
# @height:  image height in pixels
# @pixelformat: little endian four character code (fourcc)
# @field:  enum v4l2_field; field order (for interlaced video)
# @colorspace:  enum v4l2_colorspace; supplemental to pixelformat
# @plane_fmt:  per-plane information
# @num_planes:  number of planes for this format
#

class v4l2_pix_format_mplane(ctypes.Structure):

    _pack_ = 1

    _fields_ = [
        ('width', ctypes.c_uint32),
        ('height', ctypes.c_uint32),
        ('pixelformat', ctypes.c_uint32),
        ('field', ctypes.c_uint32),
        ('colorspace', ctypes.c_uint32),
        ('plane_fmt', v4l2_plane_pix_format*VIDEO_MAX_PLANES),
        ('num_planes', ctypes.c_uint8),
        ('reserved', ctypes.c_uint8*11),
    ]


#
# struct v4l2_format - stream data format
# @type: enum v4l2_buf_type; type of the data stream
# @pix: definition of an image format
# @pix_mp: definition of a multiplanar image format
# @win: definition of an overlaid image
# @vbi: raw VBI capture or output parameters
# @sliced: sliced VBI capture or output parameters
# @raw_data: placeholder for future extensions and custom formats
#

class v4l2_format(ctypes.Structure):

    # $OBJ-00055
    class _u85(ctypes.Union):

        _fields_ = [
            ('pix', v4l2_pix_format),
            ('pix_mp', v4l2_pix_format_mplane),
            ('win', v4l2_window),
            ('vbi', v4l2_vbi_format),
            ('sliced', v4l2_sliced_vbi_format),
            ('raw_data', ctypes.c_uint8*200),
        ]

    _fields_ = [
        ('type', ctypes.c_uint32),
        ('fmt', _u85),
    ]


# Stream type-dependent parameters
#

class v4l2_streamparm(ctypes.Structure):
    # $OBJ-00057
    class _u87(ctypes.Union):

        _fields_ = [
            ('capture', v4l2_captureparm),
            ('output', v4l2_outputparm),
            ('raw_data', ctypes.c_uint8*200),
        ]

    _fields_ = [
        ('type', ctypes.c_uint32),
        ('parm', _u87),
    ]


#
# E V E N T S
#

V4L2_EVENT_ALL = 0
V4L2_EVENT_VSYNC = 1
V4L2_EVENT_EOS = 2
V4L2_EVENT_CTRL = 3
V4L2_EVENT_FRAME_SYNC = 4
V4L2_EVENT_PRIVATE_START = 0x08000000


# Payload for V4L2_EVENT_VSYNC

class v4l2_event_vsync(ctypes.Structure):

    _pack_ = 1

    _fields_ = [
        ('field', ctypes.c_uint8),
    ]


# Payload for V4L2_EVENT_CTRL
V4L2_EVENT_CTRL_CH_VALUE = (1 << 0)
V4L2_EVENT_CTRL_CH_FLAGS = (1 << 1)
V4L2_EVENT_CTRL_CH_RANGE = (1 << 2)


class v4l2_event_ctrl(ctypes.Structure):
    # $OBJ-0005A
    class _u90(ctypes.Union):

        _fields_ = [
            ('value', ctypes.c_int32),
            ('value64', ctypes.c_int64),
        ]

    _fields_ = [
        ('changes', ctypes.c_uint32),
        ('type', ctypes.c_uint32),
        ('_u90', _u90),
        ('flags', ctypes.c_uint32),
        ('minimum', ctypes.c_int32),
        ('maximum', ctypes.c_int32),
        ('step', ctypes.c_int32),
        ('default_value', ctypes.c_int32),
    ]


class v4l2_event_frame_sync(ctypes.Structure):

    _fields_ = [
        ('frame_sequence', ctypes.c_uint32),
    ]


class v4l2_event(ctypes.Structure):
    # $OBJ-0005D
    class _u93(ctypes.Union):

        _fields_ = [
            ('vsync', v4l2_event_vsync),
            ('ctrl', v4l2_event_ctrl),
            ('frame_sync', v4l2_event_frame_sync),
            ('data', ctypes.c_uint8*64),
        ]

    _fields_ = [
        ('type', ctypes.c_uint32),
        ('u', _u93),
        ('pending', ctypes.c_uint32),
        ('sequence', ctypes.c_uint32),
        ('timestamp', timespec),
        ('id', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*8),
    ]


V4L2_EVENT_SUB_FL_SEND_INITIAL = (1 << 0)
V4L2_EVENT_SUB_FL_ALLOW_FEEDBACK = (1 << 1)


class v4l2_event_subscription(ctypes.Structure):

    _fields_ = [
        ('type', ctypes.c_uint32),
        ('id', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*5),
    ]


#
# A D V A N C E D   D E B U G G I N G
#
# NOTE: EXPERIMENTAL API, NEVER RELY ON THIS IN APPLICATIONS!
# FOR DEBUGGING, TESTING AND INTERNAL USE ONLY!
#


# VIDIOC_DBG_G_REGISTER and VIDIOC_DBG_S_REGISTER

V4L2_CHIP_MATCH_BRIDGE = 0
# Match against chip ID on the bridge (0 for the bridge)
V4L2_CHIP_MATCH_SUBDEV = 4
# Match against subdev index


# The following four defines are no longer in use
V4L2_CHIP_MATCH_HOST = V4L2_CHIP_MATCH_BRIDGE
V4L2_CHIP_MATCH_I2C_DRIVER = 1
# Match against I2C driver name
V4L2_CHIP_MATCH_I2C_ADDR = 2
# Match against I2C 7-bit address
V4L2_CHIP_MATCH_AC97 = 3
# Match against ancillary AC97 chip


class v4l2_dbg_match(ctypes.Structure):

    # $OBJ-00060
    class _u96(ctypes.Union):

        _fields_ = [
            ('addr', ctypes.c_uint32),
            ('name', ctypes.c_char*32),
        ]

    _pack_ = 1

    _fields_ = [
        ('type', ctypes.c_uint32),
        ('_u96', _u96),
    ]


class v4l2_dbg_register(ctypes.Structure):

    _pack_ = 1

    _fields_ = [
        ('match', v4l2_dbg_match),
        ('size', ctypes.c_uint32),
        ('reg', ctypes.c_uint64),
        ('val', ctypes.c_uint64),
    ]


V4L2_CHIP_FL_READABLE = (1 << 0)
V4L2_CHIP_FL_WRITABLE = (1 << 1)


# VIDIOC_DBG_G_CHIP_INFO

class v4l2_dbg_chip_info(ctypes.Structure):

    _pack_ = 1

    _fields_ = [
        ('match', v4l2_dbg_match),
        ('name', ctypes.c_char*32),
        ('flags', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32*32),
    ]


#
# struct v4l2_create_buffers - VIDIOC_CREATE_BUFS argument
# @index: on return, index of the first created buffer
# @count: entry: number of requested buffers,
#  return: number of created buffers
# @memory: enum v4l2_memory; buffer memory type
# @format: frame format, for which buffers are requested
# @reserved: future extensions
#

class v4l2_create_buffers(ctypes.Structure):

    _fields_ = [
        ('index', ctypes.c_uint32),
        ('count', ctypes.c_uint32),
        ('memory', ctypes.c_uint32),
        ('format', v4l2_format),
        ('reserved', ctypes.c_uint32*8),
    ]


#
# I O C T L   C O D E S   F O R   V I D E O   D E V I C E S
#

VIDIOC_QUERYCAP = _IOR('V',  0, v4l2_capability)
VIDIOC_RESERVED = _IO('V',  1)
VIDIOC_ENUM_FMT = _IOWR('V',  2, v4l2_fmtdesc)
VIDIOC_G_FMT = _IOWR('V',  4, v4l2_format)
VIDIOC_S_FMT = _IOWR('V',  5, v4l2_format)
VIDIOC_REQBUFS = _IOWR('V',  8, v4l2_requestbuffers)
VIDIOC_QUERYBUF = _IOWR('V',  9, v4l2_buffer)
VIDIOC_G_FBUF = _IOR('V', 10, v4l2_framebuffer)
VIDIOC_S_FBUF = _IOW('V', 11, v4l2_framebuffer)
VIDIOC_OVERLAY = _IOW('V', 14, ctypes.c_int)
VIDIOC_QBUF = _IOWR('V', 15, v4l2_buffer)
VIDIOC_EXPBUF = _IOWR('V', 16, v4l2_exportbuffer)
VIDIOC_DQBUF = _IOWR('V', 17, v4l2_buffer)
VIDIOC_STREAMON = _IOW('V', 18, ctypes.c_int)
VIDIOC_STREAMOFF = _IOW('V', 19, ctypes.c_int)
VIDIOC_G_PARM = _IOWR('V', 21, v4l2_streamparm)
VIDIOC_S_PARM = _IOWR('V', 22, v4l2_streamparm)
VIDIOC_G_STD = _IOR('V', 23, v4l2_std_id)
VIDIOC_S_STD = _IOW('V', 24, v4l2_std_id)
VIDIOC_ENUMSTD = _IOWR('V', 25, v4l2_standard)
VIDIOC_ENUMINPUT = _IOWR('V', 26, v4l2_input)
VIDIOC_G_CTRL = _IOWR('V', 27, v4l2_control)
VIDIOC_S_CTRL = _IOWR('V', 28, v4l2_control)
VIDIOC_G_TUNER = _IOWR('V', 29, v4l2_tuner)
VIDIOC_S_TUNER = _IOW('V', 30, v4l2_tuner)
VIDIOC_G_AUDIO = _IOR('V', 33, v4l2_audio)
VIDIOC_S_AUDIO = _IOW('V', 34, v4l2_audio)
VIDIOC_QUERYCTRL = _IOWR('V', 36, v4l2_queryctrl)
VIDIOC_QUERYMENU = _IOWR('V', 37, v4l2_querymenu)
VIDIOC_G_INPUT = _IOR('V', 38, ctypes.c_int)
VIDIOC_S_INPUT = _IOWR('V', 39, ctypes.c_int)
VIDIOC_G_OUTPUT = _IOR('V', 46, ctypes.c_int)
VIDIOC_S_OUTPUT = _IOWR('V', 47, ctypes.c_int)
VIDIOC_ENUMOUTPUT = _IOWR('V', 48, v4l2_output)
VIDIOC_G_AUDOUT = _IOR('V', 49, v4l2_audioout)
VIDIOC_S_AUDOUT = _IOW('V', 50, v4l2_audioout)
VIDIOC_G_MODULATOR = _IOWR('V', 54, v4l2_modulator)
VIDIOC_S_MODULATOR = _IOW('V', 55, v4l2_modulator)
VIDIOC_G_FREQUENCY = _IOWR('V', 56, v4l2_frequency)
VIDIOC_S_FREQUENCY = _IOW('V', 57, v4l2_frequency)
VIDIOC_CROPCAP = _IOWR('V', 58, v4l2_cropcap)
VIDIOC_G_CROP = _IOWR('V', 59, v4l2_crop)
VIDIOC_S_CROP = _IOW('V', 60, v4l2_crop)
VIDIOC_G_JPEGCOMP = _IOR('V', 61, v4l2_jpegcompression)
VIDIOC_S_JPEGCOMP = _IOW('V', 62, v4l2_jpegcompression)
VIDIOC_QUERYSTD = _IOR('V', 63, v4l2_std_id)
VIDIOC_TRY_FMT = _IOWR('V', 64, v4l2_format)
VIDIOC_ENUMAUDIO = _IOWR('V', 65, v4l2_audio)
VIDIOC_ENUMAUDOUT = _IOWR('V', 66, v4l2_audioout)
VIDIOC_G_PRIORITY = _IOR('V', 67, ctypes.c_uint32)  # enum v4l2_priority
VIDIOC_S_PRIORITY = _IOW('V', 68, ctypes.c_uint32)  # enum v4l2_priority
VIDIOC_G_SLICED_VBI_CAP = _IOWR('V', 69, v4l2_sliced_vbi_cap)
VIDIOC_LOG_STATUS = _IO('V', 70)
VIDIOC_G_EXT_CTRLS = _IOWR('V', 71, v4l2_ext_controls)
VIDIOC_S_EXT_CTRLS = _IOWR('V', 72, v4l2_ext_controls)
VIDIOC_TRY_EXT_CTRLS = _IOWR('V', 73, v4l2_ext_controls)
VIDIOC_ENUM_FRAMESIZES = _IOWR('V', 74, v4l2_frmsizeenum)
VIDIOC_ENUM_FRAMEINTERVALS = _IOWR('V', 75, v4l2_frmivalenum)
VIDIOC_G_ENC_INDEX = _IOR('V', 76, v4l2_enc_idx)
VIDIOC_ENCODER_CMD = _IOWR('V', 77, v4l2_encoder_cmd)
VIDIOC_TRY_ENCODER_CMD = _IOWR('V', 78, v4l2_encoder_cmd)


# Experimental, meant for debugging, testing and internal use.
# Only implemented if CONFIG_VIDEO_ADV_DEBUG is defined.
# You must be root to use these ioctls. Never use these in applications!
VIDIOC_DBG_S_REGISTER = _IOW('V', 79, v4l2_dbg_register)
VIDIOC_DBG_G_REGISTER = _IOWR('V', 80, v4l2_dbg_register)
VIDIOC_S_HW_FREQ_SEEK = _IOW('V', 82, v4l2_hw_freq_seek)
VIDIOC_S_DV_TIMINGS = _IOWR('V', 87, v4l2_dv_timings)
VIDIOC_G_DV_TIMINGS = _IOWR('V', 88, v4l2_dv_timings)
VIDIOC_DQEVENT = _IOR('V', 89, v4l2_event)
VIDIOC_SUBSCRIBE_EVENT = _IOW('V', 90, v4l2_event_subscription)
VIDIOC_UNSUBSCRIBE_EVENT = _IOW('V', 91, v4l2_event_subscription)


# Experimental, the below two ioctls may change over the next couple of kernel
# versions
VIDIOC_CREATE_BUFS = _IOWR('V', 92, v4l2_create_buffers)
VIDIOC_PREPARE_BUF = _IOWR('V', 93, v4l2_buffer)


# Experimental selection API
VIDIOC_G_SELECTION = _IOWR('V', 94, v4l2_selection)
VIDIOC_S_SELECTION = _IOWR('V', 95, v4l2_selection)


# Experimental, these two ioctls may change over the next couple of kernel
# versions.
VIDIOC_DECODER_CMD = _IOWR('V', 96, v4l2_decoder_cmd)
VIDIOC_TRY_DECODER_CMD = _IOWR('V', 97, v4l2_decoder_cmd)


# Experimental, these three ioctls may change over the next couple of kernel
# versions.
VIDIOC_ENUM_DV_TIMINGS = _IOWR('V',  98, v4l2_enum_dv_timings)
VIDIOC_QUERY_DV_TIMINGS = _IOR('V',  99, v4l2_dv_timings)
VIDIOC_DV_TIMINGS_CAP = _IOWR('V', 100, v4l2_dv_timings_cap)


# Experimental, this ioctl may change over the next couple of kernel
# versions.
VIDIOC_ENUM_FREQ_BANDS = _IOWR('V', 101, v4l2_frequency_band)


# Experimental, meant for debugging, testing and internal use.
# Never use these in applications!
VIDIOC_DBG_G_CHIP_INFO = _IOWR('V', 102, v4l2_dbg_chip_info)


# Reminder: when adding new ioctls please add support for them to
# drivers/media/video/v4l2-compat-ioctl32.c as well!

BASE_VIDIOC_PRIVATE = 192
# 192-255 are private
