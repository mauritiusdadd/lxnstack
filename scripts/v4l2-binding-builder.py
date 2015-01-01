#! /usr/bin/env python2

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

import sys
import os
import platform
import re

videodev2_header = """
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
import os

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

"""


def striplines(text, chars=None):
    s = ''
    for line in text.splitlines():
        s += line.strip(chars)+'\n'
    return s


def indentlines(text, n=1):
    s = ''
    for line in text.splitlines():
        s += ('    '*n)+line+'\n'
    return s


def multireplace(text, obs, val):
    text = text
    for i in obs:
        text = text.replace(i, val)
    return text


def rfind_sep(text, start=0, end=-1, seps=' \t\n'):
    if end < 0:
        pos = len(text)-1
    else:
        pos = end

    while pos >= start:
        c = text[pos]
        if c in seps:
            while pos >= start:
                pos -= 1
                c = text[pos]
                if c not in seps:
                    return pos+1
        pos -= 1
    return -1


def rfindword(text, start=0, end=-1, seps=' \t\n'):
    sep2 = rfind_sep(text, start, end)
    sep1 = rfind_sep(text, start, sep2-1)
    word = text[sep1:sep2]
    return word


class cobject(object):

    def __init__(self):
        self.type = "unknown"
        self.name = ""
        self.aliases = []
        self.childs = {}
        self.props = {}
        self.var = []
        self._rawtext = ""
        self.structure = ""
        self.anonymous = False
        self.packed = False

    def toPy(self):
        if self.type == 'enum':
            s = self.name+' = ctypes.c_uint\n\n'
            for v in self.var:
                s += str(v.name)+' =  '+str(v.value)+'\n'
            s += '\n'
        else:
            if self.type == 'struct':
                pytytpe = "ctypes.Structure"
            elif self.type == 'union':
                pytytpe = "ctypes.Union"
            else:
                print self.type

            s = "class "+self.name+'('+pytytpe+'):\n'
            _empty = True
            anons = []
            if len(self.childs) > 0:
                child_keys = self.childs.keys()
                child_keys.sort()
                for cid in child_keys:
                    c = self.childs[cid]
                    s += "    #"+c.id+'\n'
                    s += indentlines(c.toPy())
                    if c.anonymous:
                        anons.append(c.name)

            if self.packed:
                _empty = False
                s += '\n    _pack_=1\n'

            # if len(anons)>0:
            #     _empty=False
            #     s+="\n    _anonymous_ = ("
            #     for a in anons:
            #         s+="\""+a+"\","
            #     s+=')\n'

            # checking for self-references
            self_recursive = False
            for v in self.var:
                if ((v.type == "ctypes.POINTER("+self.name+")") or
                        (v.type == self.name)):
                    self_recursive = True

            if self_recursive:
                if _empty:
                    s += '    pass\n'
                s += "\n"+self.name+"._fields_ = [\n"
                for v in self.var:
                    s += "    (\'"+str(v.name)+"\',"+str(v.type)
                    if v.psize is not None:
                        s += '*'+str(v.psize)
                    s += '),\n'
                s += "]\n"
            else:
                s += "\n    _fields_ = [\n"
                for v in self.var:
                    s += "        (\'"+str(v.name)+"\',"+str(v.type)
                    if v.psize is not None:
                        s += '*'+str(v.psize)
                    s += '),\n'
                s += "    ]\n"
        return s

    def __str__(self):
        s = self.type + " -> "+self.name

        if self.aliases:
            s += " :"
            for p in self.aliases:
                s += ' '+str(p)
        s += '\n'

        for p in self.props:
            s += "    +-> "+str(p)+' =  '+str(self.props[p])+'\n'

        for v in self.var:
            s += "    +-> "+str(v.name)+" : "+str(v.type)
            if v.psize is not None:
                s += '*'+str(v.psize)
            if v.value is not None:
                s += ' =  '+str(v.value)
            s += '\n'

        if self.childs:
            s += "    |\n"
            child_keys = self.childs.keys()
            child_keys.sort()
            for cid in child_keys:
                c = self.childs[cid]
                s += indentlines(str(c))
        else:
            s += "\n"
        return s


class cdocument(cobject):

    def __init__(self, header=''):
        cobject.__init__(self)
        self._doc_structure = None
        self.header = header

    def toPy(self, fname):
        outfile = open(fname, "w")
        outfile.write(self.header)
        outfile.write(str(self))
        outfile.close()

    def __str__(self):

        s = ""

        if self._doc_structure is not None:
            s = self._doc_structure
            for c in self.childs.values():
                s = s.replace(c.id, c.toPy())
        else:
            child_keys = self.childs.keys()
            child_keys.sort()
            for cid in child_keys:
                c = self.childs[cid]
                s += "\nprint(\"loading object "+c.id+'\")\n'
                s += indentlines(c.toPy(), 0)
        return s


class cvar(object):

    def __init__(self):
        self.id = ""
        self.type = None
        self.name = ""
        self.comment = ""
        self.value = None
        self.psize = None


class cparser(object):

    def __init__(self, fname, header=''):
        self._indent_order = 0
        self.fname = fname
        self._header = header
        self.file = open(fname, "r")

        self._global_count = 0
        self._dic = {}
        self.seps = ' \n\t'
        self.types = ['enum', 'struct', 'union', 'class']
        self._rosetta = {
            '__user': '',
            '__u64': "ctypes.c_uint64",
            '__u32': "ctypes.c_uint32",
            '__le32': 'ctypes.c_uint32',
            '__u16': "ctypes.c_uint16",
            '__u8': "ctypes.c_uint8",
            '__s64': "ctypes.c_int64",
            '__s32': "ctypes.c_int32",
            '__s16': "ctypes.c_int16",
            '__s8': "ctypes.c_int8",
            'unsigned long long': "ctypes.c_ulonglong",
            'unsigned long': "ctypes.c_ulong",
            'unsigned int': "ctypes.c_uint",
            'unsigned short': "ctypes.c_ushort",
            'unsigned': "ctypes.c_uint",
            'long long': "ctypes.c_longlong",
            'long': "ctypes.c_long",
            'int': "ctypes.c_int",
            'short': "ctypes.c_short",
            'char *': "ctypes.c_char_p",
            'char': "ctypes.c_char",
            'void *': "ctypes.c_void_p"}

    def parse(self):
        self._global_count = 0
        data = self.file.read()
        data = self._cprep_commonreplace(data)

        maindoc = cdocument(self._header)
        maindoc.name = "main-document"

        newtoken = self._c_parse(striplines(data), maindoc)

        while '/*' in newtoken:
            comm_start = newtoken.find('/*')
            comm_end = newtoken.find('*/', comm_start)

            recommented = "\n#"+newtoken[comm_start+2:comm_end]
            recommented = recommented.replace("\n*", "\n")
            recommented = recommented.replace("\n", "\n#")
            newtoken = newtoken[:comm_start]+recommented+newtoken[comm_end+2:]

        newtoken = re.sub("#define[ \t]+(.+?\(.+?\))[\t ]+(.+?)[ \t]*?\n",
                          'def \\1:\n  return \\2\n',
                          newtoken)

        newtoken = re.sub("#define[ \t]+(.+?)[\t ]+(.+?)[ \t]*?\n",
                          '\\1 = \\2\n',
                          newtoken)

        newtoken = re.sub("[ \t]*typedef[ \t]+(.+?)[\t ]+(.+?)[ \t]*?;",
                          '\\2 = \\1\n',
                          newtoken)

        newtoken = re.sub("[ \t]*struct[ \t]+",
                          ' ',
                          newtoken)

        maindoc._doc_structure = newtoken.replace('\t', ' ')

        maindoc.toPy(
            os.path.splitext(
                os.path.basename(self.fname)
                )[0].replace('-', '_') +
            "_tmp.py")

    def _cprep_commonreplace(self, text):
        text = text.replace("\\\n", "")

        text = re.sub('__attribute__[ ]\(', '__attribute__(', text)

        # text = text.replace("//", "#").replace("*/", "")

        text = re.sub('//*$', '', text)
        text = re.sub('#if.*\n', '', text)
        text = re.sub('#endif.*\n', '', text)
        # text = re.sub('#define(.)*\n', '\\1', text)

        rkeys = self._rosetta.keys()
        rkeys.sort()
        rkeys.reverse()

        for key in rkeys:
            print key
            val = self._rosetta[key]+' '
            re_key = key.replace('*', '\*').replace(' ', '['+self.seps+']*')
            text = re.sub('\\b'+key+'\\b', val, text)

        return text.replace('||', '|').replace('&&', '&')

    def _getBrakets(self, text, o='{', c='}'):
        graps = 0
        for i in text:
            if o == i:
                graps += 1
            elif c == i:
                graps -= 1
        return graps

    def _c_parse(self, text, pnode):

        shadow = ""
        # parsing enums
        start = text.find('{')
        end = 0
        count = 0
        oid = ""

        while start > 0:
            count += 1
            self._global_count += 1
            oid = "$OBJ-{0:05X}".format(self._global_count)

            prev_end = end
            end = text.find('}', start)

            sep3 = rfind_sep(text, prev_end, start, self.seps)
            sep2 = rfind_sep(text, prev_end, sep3-1, self.seps)
            sep1 = rfind_sep(text, prev_end, sep2-1, self.seps)

            obj_type = text[sep1:sep2].strip(self.seps)
            obj_name = text[sep2:sep3].strip(self.seps)

            node = cobject()

            if '{' in text[start+1:end-1]:
                while self._getBrakets(text[start+1:end-1]):
                    end = text.find('}', end+1)
                semicolon_end = text.find(';', end)
                self._indent_order += 1
                obj_inner = self._c_parse(text[start+1:end-1], node)
            else:
                semicolon_end = text.find(';', end)
                obj_inner = text[start+1:end-1]

            fallback_names = []

            for fn in text[end+1:semicolon_end].split():
                alias = fn.strip(self.seps)

                if '__attribute__' in alias:
                    if '(packed)' in alias[13:]:
                        node.packed = True
                elif alias != '':
                    fallback_names.append(alias)

            if obj_type not in self.types:
                # unnamed object
                if obj_name in self.types:
                    obj_type = obj_name
                    obj_name = '_'+obj_type[0]+str(self._global_count)

                if len(fallback_names) > 0:
                    uname = fallback_names[0]
                else:
                    uname = obj_name
                shadow += text[prev_end:sep2] +
                shadow += obj_type+" "+obj_name+" "+uname+";"
                anon = True
            else:
                shadow += text[prev_end:sep1]+'\n\n'+oid
                anon = False

            print("found "+obj_type+" \'"+obj_name+"\'")

            node.anonymous = anon
            node.name = obj_name
            node.type = obj_type
            node.id = oid
            node.aliases = fallback_names
            node._rawtext = obj_inner
            pnode.childs[oid] = node
            self.processvariables(obj_inner, node)

            end = semicolon_end+1
            start = text.find('{', end)

        shadow += text[end:]
        return shadow

    def processvariables(self, text, pnode):

        text = re.sub('/\*.*?\*/', '', text, flags=re.DOTALL)

        if pnode.type == 'enum':
            self._enum_work(text, pnode)
        elif pnode.type == 'struct':
            self._struct_work(text, pnode)
        elif pnode.type == 'union':
            self._struct_work(text, pnode)

    def _enum_work(self, text, pnode):
        val = 0
        for var in text.split(','):
            var = var.strip(self.seps)
            if var != '':
                if '=' in var:
                    name, val = var.split('=')
                else:
                    val += 1
                    name = var

                v = cvar()
                v.name = name.strip(self.seps)
                v.value = str(val).strip(self.seps)
                pnode.var.append(v)

    def _struct_work(self, text, pnode):
        self._struct_common(text, pnode)

    def union_work(self, text, pnode):
        self._struct_common(text, pnode)

    def _struct_common(self, text, pnode):
        for var in text.split(';'):
            var = var.strip(self.seps)
            if var:
                var = re.sub('\* *', '*', var)
                fields = var.split()

                if len(fields) > 1:
                    v = cvar()
                    if fields[0] in self.types:
                        cname = fields[2]
                        ctype = fields[1]
                    else:
                        cname = fields[1]
                        ctype = fields[0]

                    if '*' in cname:
                        cname = cname[1:]
                        ctype = "ctypes.POINTER("+ctype+")"

                    if '[' in cname:
                        if ']' not in cname:
                            raise SyntaxError("Corrupted header file!")
                        else:
                            bs = cname.find('[')
                            be = cname.find(']')
                            psize = cname[bs+1:be]
                            cname = cname[:bs]
                    else:
                        psize = None

                    v.name = cname
                    v.type = ctype
                    v.psize = psize

                    if (('#' in cname) or ('#' in ctype)):
                        print("")
                        print("  ############################################")
                        print("  # WARINING: Invalid syntax in header file! #")
                        print("  #     some definitions will be missing     #")
                        print("  ############################################")
                        print("")
                    else:
                        pnode.var.append(v)
                else:
                    print text
                    print var
                    print fields
                    raise SyntaxError("Corrupted header file!")

if __name__ == "__main__":
    uname = platform.uname()

    mod_dir = os.path.join('usr', 'lib', 'modules')
    unm_dir = os.path.join(mod_dir, uname[2])
    inc_dir = os.path.join(unm_dir, 'build')
    lnx_dir = os.path.join(inc_dir, 'include', 'uapi', 'linux')

    vdev2_fname = os.path.join(lnx_dir, 'videodev2.h')
    v4l2_ctrl_fname = os.path.join(lnx_dir, 'v4l2-controls.h')

    there_is_errors = False
    if not os.path.exists(vdev2_fname):
        print("ERROR: cannot locat videodev2.h")
        there_is_errors = True

    if not os.path.exists(v4l2_ctrl_fname_2):
        print("ERROR: cannot locat v4l2-controls.h")
        there_is_errors = True

    if there_is_errors:
        sys.exit(1)
    else:
        cp = cparser(vdev2_fname, videodev2_header)
        cp.parse()

        cp = cparser(v4l2_ctrl_fname)
        cp.parse()
