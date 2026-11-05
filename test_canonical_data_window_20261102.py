import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt6.QtWidgets import QApplication, QComboBox, QLineEdit, QPlainTextEdit, QLabel
import groovebox as g

_qa = QApplication.instance() or QApplication([])


def test_canonical_data_window_filter_and_sections():
    app = g.MathematiciansGrooveboxApp()
    dlg = app._open_canonical_data()
    assert dlg is not None
    sect = dlg.findChild(QComboBox); flt = dlg.findChild(QLineEdit); view = dlg.findChild(QPlainTextEdit)
    assert sect.count() > 1 and "seed" in view.toPlainText()
    flt.setText("zzz_no_such_text_zzz")
    assert "no lines match" in view.toPlainText()
    flt.setText("")
    sect.setCurrentIndex(sect.findText("seed"))
    assert '"seed"' in view.toPlainText() and "bpm" not in view.toPlainText()
    assert any("instrument sequences" in l.text() for l in dlg.findChildren(QLabel))
    dlg.close()
