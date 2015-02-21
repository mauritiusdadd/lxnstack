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

import os
import re
import logging

from PyQt4 import QtGui

import log
import paths
import utils
import translation as tr

DEFAULT = os.path.join(paths.STYLES_PATH, 'default.css')


def readStyleSheet(filename):
    if os.path.isfile(filename):
        try:
            f = open(filename, 'r')
        except Exception as exc:
            utils.showErrorMsgBox(
                tr.tr("Cannot open the stylesheet file '%s'") % filename,
                str(exc))
        else:
            stylesheet = f.read()
            relpath = os.path.dirname(filename)
            # fixing relative URLs
            re_m = r"url\(([^/]+)"
            re_s = r"url({0:s}/\1".format(relpath)
            stylesheet = re.sub(re_m, re_s, stylesheet)
            f.close()
            return stylesheet
    else:
        utils.showErrorMsgBox(
            tr.tr("The stylesheet file '%s' does not exist.") % filename)


def enumarateStyles():
    style_list = []
    for x in QtGui.QStyleFactory.keys():
        style_list.append(str(x).lower())
    return set(style_list)


def _findStyleSheetFiles(path):

    log.log("<lxnstack.styles module>",
            'searching for stylesheets in directory: \''+str(path)+'\'',
            level=logging.DEBUG)
    files = {}

    for element in os.listdir(str(path)):
        elpath = os.path.join(path, element)
        if os.path.isfile(elpath) and element[-4:] == '.css':
            files[element[:-4]] = elpath
            log.log("<lxnstack.styles module>",
                    'found stylesheet: \''+str(element)+'\'',
                    level=logging.DEBUG)
        elif os.path.isdir(elpath):
            for item in _findStyleSheetFiles(elpath).items():
                files[item[0]] = os.path.join(path, item[1])
    return files


def enumarateStylesSheet():

    log.log("<lxnstack.styles module>",
            'enumerating stock stylesheets',
            level=logging.INFO)
    # stock stylesheets
    stock = _findStyleSheetFiles(paths.STYLES_PATH)

    # custom stylesheets
    custom_path = os.path.join(paths.HOME_PATH, 'styles')
    if os.path.exists(custom_path):
        log.log("<lxnstack.styles module>",
                'enumerating custom stylesheets',
                level=logging.INFO)
        custom = _findStyleSheetFiles(custom_path)
        return stock + custom
    else:
        return stock


def setApplicationStyle(style):
    qapp = QtGui.QApplication.instance()
    qapp.setStyle(QtGui.QStyleFactory.create(style))


def setApplicationStyleSheet(filename):
    if filename is not None:
        QtGui.QApplication.instance().setStyleSheet(readStyleSheet(filename))
    else:
        QtGui.QApplication.instance().setStyleSheet('')
