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

if ('--help' in sys.argv) or ('-h' in sys.argv):
    
    print("\nUsage: lxnstack [OPTION]")
    print("")
    print("Mandatory arguments to long options are mandatory for short options too")
    print("  -h, --help                  show this show this help and exit")
    print("  -m, --user-manual           show the use manual in a web browser and exit")
    print("  -v, --version               print the version of the program and exit\n")
    sys.exit(0)

if ('--user-manual' in sys.argv) or ('-m' in sys.argv):
    show_help = True
    print("Loading user manual...")
else:
    show_help = False
        
if ('--version' in sys.argv) or ('-v' in sys.argv):
    print("\nversion: 1.3.1\n")
    sys.exit(0)
    
#create main QApplication
app = Qt.QApplication(sys.argv)

#import the main application
import main_app

import paths
main_app.loading.setValue(90)
import utils
main_app.loading.setValue(91)


if ('--verbose' in sys.argv) or ('-d' in sys.argv):
    utils._VERBOSE=True
else:
    utils._VERBOSE=False

#set some informations
app.setOrganizationName(utils.PROGRAM)
app.setApplicationName(utils.PROGRAM_NAME)
main_app.loading.setValue(92)

#loading translations
qtr = Qt.QTranslator()
main_app.loading.setValue(93)
lang=utils.getLocale()
main_app.loading.setValue(94)
qtr.load(lang)
main_app.loading.setValue(95)
app.installTranslator(qtr)
main_app.loading.setValue(96)

#create the main application
mainApp = main_app.theApp(app,lang)
main_app.loading.setValue(98)

if show_help:
    mainApp.showUserMan()
    sys.exit(0)
    
mainApp.wnd.show()
main_app.loading.setValue(99)

try:
    mainApp.loadSettings()
except:
    #probably the first execution
    pass

main_app.loading.setValue(100)
del main_app.loading

#executes
sys.exit(app.exec_())
