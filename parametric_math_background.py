"""Low-cost ParametricMathBackground for independent Groovebox windows."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget
import math

class ParametricMathBackground(QWidget):
    """Static sparse Meum/phi lattice; paints once on expose/resize only."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ParametricMathBackground")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._phase = 0.0
    def paintEvent(self, event):
        p=QPainter(self)
        if not p.isActive(): return
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w,h=self.width(),self.height(); step=max(44,min(w,h)//9)
        p.setPen(QPen(QColor(42,155,184,26),1))
        for x in range(0,w,step): p.drawLine(x,0,x,h)
        for y in range(0,h,step): p.drawLine(0,y,w,y)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(QColor(242,190,92,36),1))
        last=None
        for i in range(0,max(2,w),max(4,w//160 or 4)):
            t=i/max(1,w-1); yy=int(h*(.52+.13*math.sin(6.283185307179586*1.19758*t)+.07*math.sin(6.283185307179586*1.61803*t)))
            if last is not None: p.drawLine(last[0],last[1],i,yy)
            last=(i,yy)
        p.end()
