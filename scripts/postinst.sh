#!/bin/sh 
xdg-icon-resource install --context mimetypes --size 64 /usr/share/lxnstack/lxnstack.png application-lxnstack-project
xdg-mime install /usr/share/lxnstack/lxnstack-project.xml
xdg-mime default /usr/share/applications/lxnstack.desktop application/lxnstack-project
update-desktop-database -q
