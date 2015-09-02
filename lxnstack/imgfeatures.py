# lxnstack is a program to align and stack atronomical images
# Copyright (C) 2013-2015  Maurizio D'Addona <mauritiusdadd@gmail.com>
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
    moved_rt = QtCore.pyqtSignal(float, float, str, str)
    moved_ft = QtCore.pyqtSignal(float, float, str, str)
    resized = QtCore.pyqtSignal(float, float, str, str)
    renamed = QtCore.pyqtSignal(str, str, str)
    selected = QtCore.pyqtSignal(str, str)

    def __init__(self, x=0, y=0, name="", pid=""):

        QtCore.QObject.__init__(self)

        if pid == "":
            self.id = utils.genTimeUID()
        else:
            self.id = str(pid)
        self._parent = None
        self.x = x
        self.y = y
        self.r = 7
        self.width = 0
        self.height = 0
        self.color = None
        self.name = name
        self.aligned = False
        self.mouse_over = False
        self.mouse_grab = False
        self.fixed = False

    def setParent(self, parent=None):
        """
        setParent(parent=None)

        set the parent Frame of the object
        """
        if parent is None:
            self._parent = None
        elif not isinstance(parent, utils.Frame):
            raise TypeError("parent must be a utils.Frame object")
        else:
            self._parent = parent

    def isFixed(self):
        return bool(self.fixed)

    def getParent(self):
        return self._parent

    def getFTPosition(self):
        """
        getFTPosition()

        If the object has no parent Frame, this function returns
        the save value of getAbsolutePosition(), otherwise the
        function getForwardTPosition(x, y) of its parent Frame
        object is used to compute the result.
        """
        if self._parent is None:
            return self.getAbsolutePosition()
        else:
            ax, ay = self.getAbsolutePosition()
            return self._parent.getForwardTPosition(ax, ay)

    def getRTPosition(self):
        """
        getRTPosition()

        If the object has no parent Frame, this function returns
        the save value of getAbsolutePosition(), otherwise the
        function getReverseTPosition(x, y) of its parent Frame
        object is used to compute the result.
        """
        if self._parent is None:
            return self.getAbsolutePosition()
        else:
            ax, ay = self.getAbsolutePosition()
            return self._parent.getReverseTPosition(ax, ay)

    def getAbsolutePosition(self):
        """
        getAbsolutePosition()

        returns the absolute position, misured in pixels, of
        the ImageFeature in the form of (x, y). If the object
        has a parent Frame, the position is intended as relative
        to the top-left corner of the parent image.
        """
        return (self.x, self.y)

    def getSize(self):
        return (self.width, self.height)

    def getName(self):
        return self.name

    def setPosition(self, x, y):
        """
        setPosition()

        This funciton sets the position of the ImageFeature.
        If the object has no parent Frame, this function is
        equivalent to setAbsolutePosition(x, y), otherwise the
        function getForwardTPosition(x, y) of its parent Frame
        object is used to compute object position.
        """
        if self._parent is None:
            return self.setAbsolutePosition(x, y)
        else:
            rx, ry = self._parent.getForwardTPosition(x, y)
            self.setAbsolutePosition(rx, ry)

    def setAbsolutePosition(self, x, y):
        """
        setAbsolutePosition(x, y)

        set the position, misured in pixels, of the ImageFeature.
        If the object has a parent Frame, the position is intended
        as relative to the top-left corner of the parent image.
        """
        self.x = x
        self.y = y

    def setSize(self, w, h):
        self.width = w
        self.height = h

    def setName(self, name):
        self.name = name

    def move(self, newx, newy):
        if (newx, newy) == self.getAbsolutePosition():
            return
        self.setAbsolutePosition(newx, newy)
        rx, ry = self.getRTPosition()
        fx, fy = self.getFTPosition()
        self.moved.emit(newx, newy, str(self.id), str(self.name))
        self.moved_ft.emit(fx, fy, str(self.id), str(self.name))
        self.moved_rt.emit(rx, ry, str(self.id), str(self.name))

    def resize(self, neww, newh):
        if (neww, newh) == self.getSize():
            return
        self.setSize(neww, newh)
        self.resized.emit(neww, newh, str(self.id), str(self.name))

    def rename(self, newname):
        oldname = self.name
        if oldname == newname:
            return
        self.setName(newname)
        self.renamed.emit(self.name, oldname, str(self.id))

    def draw(self, painter):
        raise NotImplementedError


class AlignmentPoint(ImageFeature):

    def draw(self, painter):

        if not isinstance(painter, QtGui.QPainter):
            return False

        x = self.x+0.5
        y = self.y+0.5

        l = 4
        r = self.r

        rect1 = Qt.QRectF(x+8, y+10, 45, 15)
        rect2 = Qt.QRectF(x-self.width/2,
                          y-self.height/2,
                          self.width,
                          self.height)

        painter.setFont(Qt.QFont("Arial", 8))
        painter.setCompositionMode(28)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtCore.Qt.white)

        # drawing marker
        painter.drawEllipse(Qt.QPointF(x, y), r, r)
        painter.drawLine(Qt.QPointF(x-r-l, y), Qt.QPointF(x-r+l, y))
        painter.drawLine(Qt.QPointF(x+r-l, y), Qt.QPointF(x+r+l, y))
        painter.drawLine(Qt.QPointF(x, y-l-r), Qt.QPointF(x, y-r+l))
        painter.drawLine(Qt.QPointF(x, y+r+l), Qt.QPointF(x, y+r-l))

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

        self.x = x
        self.y = y
        self.r0 = 0
        self.r1 = 10
        self.r2 = 20
        self.r3 = 30
        self.magnitude = 0
        self.color1 = QtCore.Qt.green
        self.color2 = QtCore.Qt.white
        self.name = name
        self.reference = False
        self.fixed = True

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

        cx = self.x + 0.5
        cy = self.y + 0.5

        r1 = self.r1 - 0.5
        r2 = self.r2 - 0.5
        r3 = self.r3 - 0.5

        painter.drawEllipse(Qt.QPointF(cx, cy), r1, r1)
        painter.drawEllipse(Qt.QPointF(cx, cy), r2, r2)
        painter.drawEllipse(Qt.QPointF(cx, cy), r3, r3)

        painter.setCompositionMode(0)

        if (self.name.strip() != '') and self.mouse_over:
            rect = Qt.QRectF(cx+r3-2, cy+r3-2, 50, 15)
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
