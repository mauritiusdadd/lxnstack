# lxnstack is a program to align and stack atronomical images
# Copyright (C) 2013-2014  Maurizio D'Addona <mauritiusdadd@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import utils
from PyQt4 import Qt, QtCore, QtGui


# parent object for all features
class ImageFeature(QtCore.QObject):

    moved = QtCore.pyqtSignal(float, float, str, str)
    resized = QtCore.pyqtSignal(float, float, str, str)
    renamed = QtCore.pyqtSignal(str, str, str)
    selected = QtCore.pyqtSignal(str, str)

    def __init__(self, x=0, y=0, name="", pid=""):

        QtCore.QObject.__init__(self)

        if pid == "":
            self.id = utils.genTimeUID()
        else:
            self.id = str(pid)

        self.x = x
        self.y = y
        self.r = 25
        self.width = 0
        self.height = 0
        self.color = None
        self.name = name
        self.aligned = False
        self.mouse_over = False
        self.mouse_grab = False

    def getPosition(self):
        return (self.x, self.y)

    def getSize(self):
        return (self.width, self.height)

    def getName(self):
        return self.name

    def setPosition(self, x, y):
        self.x = x
        self.y = y

    def setSize(self, w, h):
        self.width = w
        self.height = h

    def setName(self, name):
        self.name = name

    def move(self, newx, newy):
        self.setPosition(newx, newy)
        self.moved.emit(newx, newy, str(self.id), str(self.name))

    def resize(self, neww, newh):
        self.setSize(neww, newh)
        self.resized.emit(neww, newh, str(self.id), str(self.name))

    def rename(self, newname):
        oldname = self.name
        self.name = newname
        self.renamed.emit(self.name, oldname, str(self.id))

    def draw(self, painter):
        raise NotImplementedError


class AlignmentPoint(ImageFeature):

    def draw(self, painter):

        if not isinstance(painter, QtGui.QPainter):
            return False

        x = self.x+0.5
        y = self.y+0.5

        rect1 = Qt.QRectF(x+8, y+10, 45, 15)
        rect2 = Qt.QRectF(x-self.width/2,
                          y-self.height/2,
                          self.width,
                          self.height)

        painter.setFont(Qt.QFont("Arial", 8))
        painter.setCompositionMode(28)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtCore.Qt.white)
        utils.drawMarker(painter, x, y)

        painter.setCompositionMode(0)
        painter.setBrush(QtCore.Qt.blue)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRect(rect1)
        painter.setPen(QtCore.Qt.yellow)
        painter.drawText(rect1,
                         QtCore.Qt.AlignCenter,
                         self.name)

        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRect(rect2)


class Star(ImageFeature):

    def __init__(self, x=0, y=0, name="", pid=""):

        ImageFeature.__init__(self, x, y, name, pid)

        self.x = 0
        self.y = 0
        self.r0 = 0
        self.r1 = 10
        self.r2 = 20
        self.r3 = 30
        self.magnitude = 0
        self.color1 = QtCore.Qt.green
        self.color2 = QtCore.Qt.white
        self.name = name
        self.reference = False

    def draw(self, painter):
        if not isinstance(painter, QtGui.QPainter):
            return False

        painter.setFont(Qt.QFont("Arial", 8))

        if self.mouse_over:
            painter.setCompositionMode(0)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtCore.Qt.red)
        elif self.reference:
            painter.setCompositionMode(0)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtCore.Qt.green)
        else:
            painter.setCompositionMode(28)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtCore.Qt.white)

        painter.drawEllipse(Qt.QPointF(self.x, self.y),
                            self.r1, self.r1)
        painter.drawEllipse(Qt.QPointF(self.x, self.y),
                            self.r2, self.r2)
        painter.drawEllipse(Qt.QPointF(self.x, self.y),
                            self.r3, self.r3)

        painter.setCompositionMode(0)

        if (self.name.strip() != '') and self.mouse_over:
            rect = Qt.QRectF(self.x+self.r3-2,
                             self.y+self.r3-2,
                             45, 15)
            painter.setBrush(QtCore.Qt.blue)
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRect(rect)

            if self.reference is True:
                painter.setPen(QtCore.Qt.green)
            else:
                painter.setPen(QtCore.Qt.yellow)

            painter.drawText(rect,
                             QtCore.Qt.AlignCenter,
                             self.name)
