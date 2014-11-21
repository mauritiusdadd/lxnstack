#lxnstack is a program to align and stack atronomical images
#Copyright (C) 2013-2014  Maurizio D'Addona <mauritiusdadd@gmail.com>

#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.
 
import os
import logging, logging.handlers
import paths
import inspect

LOGGERNAME = "lxnstack-root-logger"
LOG_FILE = os.path.join(paths.HOME_PATH,'lxnstack.log')

class LogContext(object):

    def __getitem__(self, key):
        if key == 'host':
            return 'localhost'
        raise KeyError(key)

    def __iter__(self):
        return iter(['host'])

def createMainLogger(verbosity=logging.DEBUG):
    formatter = logging.Formatter(fmt='[%(levelname)s] %(asctime)s - %(traceback)s - %(message)s')

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(verbosity)
    
    file_handler = logging.handlers.RotatingFileHandler(LOG_FILE,backupCount=5)
    file_handler.doRollover()
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    logger = logging.getLogger(LOGGERNAME)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

def log(module, message, level=logging.DEBUG, *arg, **args):
    caller=inspect.stack()[1][3]
    
    traceback = str(module)+'.'+str(caller)
    
    args['traceback']=str(traceback)
    
    for each_message in str(message).splitlines():
        logging.getLogger(LOGGERNAME).log(level, each_message, extra=args)

