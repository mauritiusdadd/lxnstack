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
