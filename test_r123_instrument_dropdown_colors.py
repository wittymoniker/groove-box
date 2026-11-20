"""R123: every row of the selected-instrument dropdown is painted in that instrument's assigned colour."""
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC = (Path(__file__).resolve().parent / "groovebox.py").read_text(encoding="utf-8")


def test_main_window_wires_colour_source():
    assert "self.instrument_selector_dropdown.set_color_source(self._r32_instrument_color)" in SRC
    assert SRC.count("GROOVEBOX_R123_INSTRUMENT_DROPDOWN_COLORS_20261119") >= 2


def test_rows_paint_assigned_colours_under_transparent_item_stylesheet():
    QtWidgets = pytest.importorskip("PyQt6.QtWidgets")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    import groovebox as g
    app.setStyleSheet("QComboBox QAbstractItemView::item { background-color: transparent; }")
    keys = ["Sine", "Saw", "FM", "Noise"]
    pal = {"Sine": "#7dd3fc", "Saw": "#ff7a90", "FM": "#2ecc71", "Noise": "#1a1a6b"}
    c = g._InstrumentKeyCombo({"Saw": "Renamed Saw"})
    c.addItems(keys)
    c.set_color_source(pal.get)
    c.resize(300, 40); c.show(); c.showPopup(); app.processEvents()
    v = c.view(); img = v.grab().toImage()
    for row, k in enumerate(keys):
        r = v.visualRect(v.model().index(row, 0))
        assert img.pixelColor(r.left() + 6, r.center().y()).name() == pal[k]
    assert g._instrument_text_color("#1a1a6b").name() == "#ffffff"
    assert g._instrument_text_color("#7dd3fc").name() == "#05070b"
    c.hidePopup(); c.close()
