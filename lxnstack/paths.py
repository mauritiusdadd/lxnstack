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


#Paths used for installation process and program execution
import os
from pkg_resources import resource_filename


PROGRAM_NAME = 'lxnstack'
PREFIX='/usr'
DATA_PATH=resource_filename('lxnstack', 'data')
RESOURCES_PATH=os.path.join(PREFIX,'share',PROGRAM_NAME.lower())
DOCS_PATH=os.path.join(RESOURCES_PATH,'doc',PROGRAM_NAME.lower())
ICONS_PATH=os.path.join(DATA_PATH,'icons')
LANG_PATH=os.path.join(DATA_PATH,'lang')
UI_PATH=os.path.join(DATA_PATH,'ui')
TEMP_PATH=os.path.join('/tmp',PROGRAM_NAME.lower())
HOME_PATH=os.path.join(os.path.expandvars('$HOME'),PROGRAM_NAME.lower())
CAPTURED_PATH=os.path.join(HOME_PATH,'captured')
