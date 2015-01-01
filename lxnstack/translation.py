# lxnstack is a program to align and stack atronomical images
# Copyright (C) 2013-2015  Maurizio D'Addona <mauritiusdadd@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import logging

from PyQt4 import QtCore

import paths
import log


def tr(s):
    news = QtCore.QCoreApplication.translate('@default', s)
    if type(news) == str:
        # python3 return str...
        return news
    else:
        # ...while python2 return QString
        # that must be converted to str
        try:
            return str(news.toAscii())
        except:
            return str(news)


def getLocale():
    try:
        settings = QtCore.QSettings()
        settings.beginGroup("settings")
        lang = str(settings.value("language_file", None, str))
        settings.endGroup()

        if not os.path.isfile(lang):
            raise Exception('no valid file')

        log.log("<translation module>",
                "Using language file \""+lang+"\"",
                level=logging.INFO)
        return lang

    except Exception:
        local = 'lang_'+str(QtCore.QLocale.system().name())+'.qm'
        lang = os.path.join(paths.LANG_PATH, local)

        settings = QtCore.QSettings()
        settings.beginGroup("settings")

        if os.path.exists(lang):
            current_language = lang
            log.log("<translation module>",
                    "Using fallback language file \""+lang+"\"",
                    level=logging.INFO)
        else:
            current_language = local
            log.log("<translation module>",
                    "Using fallback locale \""+local+"\"",
                    level=logging.INFO)

        settings.setValue("language_file", current_language)
        settings.endGroup()
        return current_language
