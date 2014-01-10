#!/usr/bin/env python2

#lxnstack is a program to align and stack atronomical images
#Copyright (C) 2013  Maurizio D'Addona <mauritiusdadd@gmail.com>

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
import sys, os, time

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
    print("\nversion: 1.4.0\n")
    sys.exit(0)
    
#create main QApplication
app = Qt.QApplication(sys.argv)

import paths
import utils

splash=utils.SplashScreen(os.path.join(paths.RESOURCES_PATH,"splashscreen.jpg"),app)

#import the main application
import main_app

if ('--verbose' in sys.argv) or ('-d' in sys.argv):
    utils._VERBOSE=True
else:
    utils._VERBOSE=False

#set some informations
app.setOrganizationName(utils.PROGRAM)
app.setApplicationName(utils.PROGRAM_NAME)
splash.setValue(10)
splash.showMessage('Loading qt environment...')

#loading translations
qtr = Qt.QTranslator()
splash.setValue(30)
lang=utils.getLocale()
splash.setValue(50)
qtr.load(lang)
splash.setValue(60)
app.installTranslator(qtr)
splash.setValue(80)

splash.showMessage('loading application settings...')
#create the main application
mainApp = main_app.theApp(app,lang)
splash.setValue(90)

if show_help:
    mainApp.showUserMan()
    sys.exit(0)
    
mainApp.wnd.show()

try:
    utils.trace('loading application settings')
    mainApp.loadSettings()
except Exception as exc:
    #probably the first execution
    utils.trace('an error has occured while loading the application settings:\n'+str(exc))
    utils.trace('Ignore this warning if it is the first execution after the installation/upgrade.')
    pass

splash.setValue(100)
splash.showMessage('Welcome to lxnstack')

time.sleep(1)

splash.close()
#executes
retval=app.exec_()

utils.trace('Shutting down...')

sys.exit(retval)
