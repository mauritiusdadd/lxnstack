#!/usr/bin/env python2

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
sys.path.append("@RESOURCES_PATH")
import paths
import utils
#create main QApplication
app = Qt.QApplication(sys.argv)

#set some informations
app.setOrganizationName(utils.PROGRAM)
app.setApplicationName(utils.PROGRAM_NAME)

#loading translations
qtr = Qt.QTranslator()
lang=utils.getLocale()
qtr.load(lang)
app.installTranslator(qtr)

#import the main application
import main_app

#create the main application
mainApp = main_app.theApp(app,lang)
mainApp.wnd.show()
try:
    mainApp.loadSettings()
except:
    #probably the first execution
    pass
#executes
sys.exit(app.exec_())
