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

import os
import sys
import shutil
sys.path.append('src')
import paths

args = sys.argv

PREFIX='/usr'
IGNORE_PREFIX = False

for arg in args:
    if '--prefix=' in arg:
        PREFIX=arg[9:]
        if not os.path.isdir(PREFIX):
            print('ERROR: the installation directory does not exist!')
            sys.exit(1)
    if arg=='--ignore-prefix':
        IGNORE_PREFIX = True
    
    if arg=='--help':
        print('usage: install [OPTIONS]\n')
        print(' OPTIONS:')
        print(' \t--help : \t\t show this help message.')
        print(' \t--prefix=\"URL" : \t set the installation directory')
        print(' \t                  \t to URL, by default it is "/usr"')
        print(' \t--ignore-prefix : \t does not add the prefix URL to')
        print(' \t                  \t program main path (useful when')
        print(' \t                  \t creating PKGBUILD for archlinux.')
        exit(0)
        
#if dst exists, files will be overwritten
def _copytree2(src,dst):
    if not(os.path.exists(dst)):
            os.makedirs(dst)
    elif os.path.isfile(dst):
        print("Error coping files:")
        print(" destination exists but is not a dyrectory!")
        print(" destination = "+dst)
        raise IOError
        
    for f in os.listdir(src):
        s = os.path.join(src,f)
        d = os.path.join(dst,f)
        if os.path.isfile(s):
            shutil.copyfile(s,d)
        elif os.path.isdir(s):
            _copytree2(s,d)
            
def getPath(pth):
    rp = os.path.abspath(os.path.join(PREFIX,pth))
    return rp
            
def doInstallation():
    try:
        if not(os.path.isdir(getPath(paths.BIN_PATH))):
            os.makedirs(getPath(paths.BIN_PATH))
        
        if not(os.path.isdir(getPath(paths.RESOURCES_PATH))):
            os.makedirs(getPath(paths.RESOURCES_PATH))
                
        if os.path.isdir(getPath(paths.DOCS_PATH)):
            shutil.rmtree(getPath(paths.DOCS_PATH))
        
        if not(os.path.isdir(getPath(paths.LANG_PATH))):
            os.makedirs(getPath(paths.LANG_PATH))
        
        if not(os.path.isdir(getPath(paths.UI_PATH))):
            os.makedirs(getPath(paths.UI_PATH))
        
        icons_path=os.path.join(getPath(paths.DATA_PATH),'icons')
        if not(os.path.isdir(icons_path)):
            #this should never be executed
            os.makedirs(icons_path)

        apps_path=os.path.join(getPath(paths.DATA_PATH),'applications')
        if not(os.path.isdir(apps_path)):
            #this should never be executed
            os.makedirs(apps_path)

        license_path = os.path.join(getPath(paths.DATA_PATH),'licenses',paths.PROGRAM_NAME.lower())
        if not(os.path.isdir(license_path)):
            os.makedirs(license_path)

        shutil.copy('./src/main_app.py', getPath(paths.RESOURCES_PATH))
        shutil.copy('./src/utils.py', getPath(paths.RESOURCES_PATH))
        shutil.copy('./src/cr2plugin.py', getPath(paths.RESOURCES_PATH))
        #shutil.copy('./src/paths.py', getPath(paths.RESOURCES_PATH))
        shutil.copy('./src/lxnstack.png', getPath(paths.RESOURCES_PATH))
        shutil.copy('./src/splashscreen.jpg', getPath(paths.RESOURCES_PATH))
        shutil.copy('./src/lxnstack-project.xml', getPath(paths.RESOURCES_PATH))
        shutil.copy('./src/lxnstack.png', icons_path)
        shutil.copy('./src/lxnstack.desktop',apps_path)
        shutil.copy('./src/doc/gpl-3.0.txt',license_path)
        
        f=open('./src/lxnstack.py','r')
        data=f.read()
        f.close()
        
        f=open('./src/paths.py','r')
        paths_data=f.read()
        f.close()
                
        if IGNORE_PREFIX:
            data=data.replace('@RESOURCES_PATH',os.path.join('/usr',paths.RESOURCES_PATH,))
            paths_data=paths_data.replace('PREFIX=""','PREFIX=\'/usr\'')
        else:
            data=data.replace('@RESOURCES_PATH',getPath(paths.RESOURCES_PATH))
            paths_data=paths_data.replace('PREFIX=""','PREFIX=\''+PREFIX+'\'')
        
        f=open(os.path.join(getPath(paths.RESOURCES_PATH),'lxnstack.py'),'w')
        f.write(data)
        f.close()
                
        f=open(os.path.join(getPath(paths.RESOURCES_PATH),'paths.py'),'w')
        f.write(paths_data)
        f.close()
        
        _copytree2('./src/ui', getPath(paths.UI_PATH))
        _copytree2('./src/doc', getPath(paths.DOCS_PATH))
        _copytree2('./src/lang', getPath(paths.LANG_PATH))
               
        ln_bin_src=os.path.join(getPath(paths.RESOURCES_PATH),'lxnstack.py')
        ln_bin_dst=os.path.join(getPath(paths.BIN_PATH),'lxnstack')
        
        #TODO:make relative symbolic link instead of hard link
        if os.path.exists(ln_bin_dst) and not os.path.isdir(ln_bin_dst):
            os.remove(ln_bin_dst)
            
        if os.system('ln -f -s -r -T '+ln_bin_src+' '+ln_bin_dst)!=0:
            print "\nMaybe you have an old version of ln\nUsing python natives funtions...\n"
            relpath = os.path.relpath(getPath(paths.RESOURCES_PATH),getPath(paths.BIN_PATH))
            if os.path.exists(ln_bin_dst):
                os.remove(ln_bin_dst)
            os.symlink(os.path.join(relpath,'lxnstack.py'),ln_bin_dst)
            print "DONE"
            
        os.system('chmod +x '+ln_bin_dst)
        
        if not IGNORE_PREFIX:
            icon=os.path.join(icons_path,'lxnstack.png')
            if (os.system('xdg-icon-resource install --context mimetypes --size 64 '+icon+' application-lxnstack-project')!=0):
                print('\nCannot registe MIME type icon.')
                print('Assure xdg-utils is installed correclty!')
            elif (os.system('xdg-mime install ./src/lxnstack-project.xml')!=0):
                print('\nCannot update MIME database.')
                print('Assure xdg-utils is installed correclty!')
            elif (os.system('update-desktop-database -q')!=0):
                print('\nCannot update *.desktop database.')
                print('Please, restart the computer to apply the changes')
            else:
                print('installation completed.')
            
    except Exception as exc:
        print('\nCannot continue the installation process:')
        print(str(exc)+'\n')
        print('Assure you have the permission to write')
        print('file into installation directory.\n')
        print('Maybe you need to be super user to install')
        print('the program.\n')

doInstallation()
