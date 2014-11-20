#!/usr/bin/env python2

#lxnstack is a program to align and stack atronomical images
#Copyright (C) 2013-2014  Maurizio D'Addona <mauritiusdadd@gmail.com>

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

PROGRAM_VERSION="1.5.0"

if __name__ == "__main__":

    sys.path.append("@RESOURCES_PATH")
    
    import log
    
    batch_mode=False

    if len(sys.argv)>1:
            
        if ('--user-manual' in sys.argv) or ('-m' in sys.argv):
            show_help = True
            print("Loading user manual...")
        else:
            show_help = False
                
        if ('--version' in sys.argv) or ('-v' in sys.argv):
            print("\nversion: "+PROGRAM_VERSION+"\n")
            sys.exit(0)

        args=sys.argv[1:]
        
    else:
        args=[]
        show_help = False
    
    logger = log.createMainLogger()
    
    #create main QApplication
    app = Qt.QApplication(sys.argv)

    import paths
    import utils

    splash=utils.SplashScreen(os.path.join(paths.RESOURCES_PATH,"splashscreen.jpg"),app)
    app.aboutToQuit.connect(splash.close)
    #import the main application
    import main_app

    if ('--verbose' in sys.argv) or ('-d' in sys.argv):
        _VERBOSE=True
    else:
        _VERBOSE=False

    #set some informations
    app.setOrganizationName(utils.PROGRAM)
    app.setApplicationName(utils.PROGRAM_NAME)
    splash.setValue(10)
    splash.showMessage('Loading qt environment...')

    #loading translations
    qtr = Qt.QTranslator()
    splash.setValue(10)
    lang=utils.getLocale()
    splash.setValue(15)
    qtr.load(lang)
    splash.setValue(20)
    app.installTranslator(qtr)
    splash.setValue(25)
    
    splash.showMessage('loading application settings...')
    #create the main application
    mainApp = main_app.theApp(lang,args)
    splash.setValue(90)

    if show_help:
        mainApp.showUserMan()
        sys.exit(0)
        
    mainApp.wnd.show()

    try:
        log.log("lxnstack",'loading application settings')
        mainApp.loadSettings()
    except Exception as exc:
        #probably the first execution
        log.log("lxnstack",'an error has occured while loading the application settings:\n'+str(exc),level=logging.ERROR)
        log.log("lxnstack",'Ignore this warning if it is the first execution after the installation/upgrade.',level=logging.ERROR)
        pass

    splash.setValue(100)
    splash.showMessage('Welcome to lxnstack')

    time.sleep(0.5)

    splash.close()
    mainApp.executeCommads()
            
    retval=app.exec_()

    log.log("lxnstack",'Shutting down...')

    sys.exit(retval)
