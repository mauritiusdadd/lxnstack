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

PROGRAM_VERSION="1.4.4"

if __name__ == "__main__":

    sys.path.append("@RESOURCES_PATH")

    if ('--help' in sys.argv) or ('-h' in sys.argv):
        
        print("\nUsage: lxnstack [OPTION]\n")
        print("Mandatory arguments to long options are mandatory for short options too\n")
        print("  -a, --align[=METHOD]        execute the phase correlation alignment")
        print("                              with the given METHOD. The values allowed")
        print("                              for METHOD are: align-only, derotate-only,")
        print("                              align-derotate, reset. If no METHOD is")
        print("                              specified then align-derotate is used by")
        print("                              default.\n")
        print("  -h, --help                  show this help and exit\n")
        print("  -i, --add-images FILES      load the images from the files FILES\n")
        print("  -m, --user-manual           show the use manual in a web browser")
        print("                              and exit\n")
        print("  -l, --load-project=FILE     load the project from file FILE\n")
        print("  -s, --save-project[=FILE]   save the project to file FILE.")
        print("                              If FILE is not given and a project is alrady")
        print("                              loaded then the current project will be")
        print("                              overwritten. If FILE is not given and no")
        print("                              project is loaded, then an error is raised.\n")
        print("  -S, --stack[=MODE]          stack the images using the mode MODE.")
        print("                              The values allowed for MODE are:  ")
        print("                              average, median, sigma-clipping, minimum,")
        print("                              maximum, stddev, variance, product.")
        print("                              If no MODE is given then the average is")
        print("                              be computed.\n")
        print("      --lightcurve            generate the lightcurves (a project with")
        print("                              lightcurve informations must be loaded).\n")
        print("  -v, --version               print the version of the program")
        print("                              and exit\n")
        sys.exit(0)

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
        utils.trace('loading application settings',verbose=_VERBOSE)
        mainApp.loadSettings()
    except Exception as exc:
        #probably the first execution
        utils.trace('an error has occured while loading the application settings:\n'+str(exc),verbose=True)
        utils.trace('Ignore this warning if it is the first execution after the installation/upgrade.',verbose=True)
        pass

    splash.setValue(100)
    splash.showMessage('Welcome to lxnstack')

    time.sleep(0.5)

    splash.close()
    mainApp.executeCommads()
    #executes
    retval=app.exec_()

    utils.trace('Shutting down...',verbose=_VERBOSE)

    sys.exit(retval)
