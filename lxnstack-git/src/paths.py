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

PROGRAM_NAME = 'lxnstack'
PREFIX="" #do not edit PREFIX value, use --prefix option instead.
DATA_PATH=os.path.join(PREFIX,'share')
RESOURCES_PATH=os.path.join(DATA_PATH,PROGRAM_NAME.lower())
DOCS_PATH=os.path.join(DATA_PATH,'doc',PROGRAM_NAME.lower())
LANG_PATH=os.path.join(RESOURCES_PATH,'lang')
UI_PATH=os.path.join(RESOURCES_PATH,'ui')
TEMP_PATH=os.path.join('/tmp',PROGRAM_NAME.lower())
BIN_PATH=os.path.join(PREFIX,'bin')
HOME_PATH=os.path.join(os.path.expandvars('$HOME'),PROGRAM_NAME.lower())
