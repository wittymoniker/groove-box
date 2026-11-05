"""Local ownership for application-created Qt painters.

This module never replaces Qt classes or patches unrelated widget subclasses.
The caller owns the paint device; this scope owns only the painter it creates.
"""
from contextlib import contextmanager

from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QThread
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QWidget


@contextmanager
def owned_painter(device):
    """Yield an active painter and end it on every exit path.

    A deleted, busy or off-thread widget yields None: paint handlers must return
    without drawing in that case. Offscreen failures raise instead of silently
    returning an invalid recorded/exported frame. Private QImages may be painted
    on workers; QWidgets and QPixmaps remain on the GUI thread.
    """
    widget = isinstance(device, QWidget)
    if widget and (sip.isdeleted(device) or
                   QThread.currentThread() != device.thread()):
        yield None
        return
    if isinstance(device, QPixmap):
        app = QCoreApplication.instance()
        if app is None or QThread.currentThread() != app.thread():
            raise RuntimeError("QPixmap painting requires the GUI thread")
    if device.paintingActive():
        if widget:
            # Do not begin a second painter, or end somebody else's painter.
            yield None
            return
        raise RuntimeError("Offscreen paint device already has an active painter")
    painter = QPainter()
    try:
        if not painter.begin(device):
            if widget:
                yield None
                return
            raise RuntimeError("Could not begin painting the offscreen image")
        yield painter
    finally:
        # Explicit cleanup also covers retained exception tracebacks/closures.
        # Do not rely on the Python wrapper being destroyed before Qt endPaint.
        if painter.isActive():
            painter.end()
