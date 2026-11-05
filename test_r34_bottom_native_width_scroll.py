"""Regression contracts for the native-width lower visual/export workspace."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = (ROOT / "groovebox.py").read_text(encoding="utf-8")


def _bottom_scroll_block():
    start = SOURCE.index("        bottom_content = QWidget()")
    end = SOURCE.index("        self.bottom_render_scroll = bottom_scroll", start)
    return SOURCE[start:end]


def test_bottom_workspace_keeps_measured_native_pixel_width():
    block = _bottom_scroll_block()
    assert "_bottom_native = bottom_layout.sizeHint()" in block
    assert "_bottom_floor = bottom_layout.minimumSize()" in block
    assert "_bottom_native_w = max(1, _bottom_native.width(), _bottom_floor.width())" in block
    assert "bottom_content.setMinimumSize(_bottom_native_w, _bottom_native_h)" in block
    assert "bottom_content.resize(_bottom_native_w, _bottom_native_h)" in block
    assert "bottom_content.setMinimumWidth(0)" not in block


def test_bottom_scroll_area_does_not_shrink_canvas_to_viewport():
    block = _bottom_scroll_block()
    assert "bottom_scroll.setWidgetResizable(False)" in block
    assert "bottom_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)" in block
    assert "bottom_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)" in block


def test_bottom_and_top_workspaces_remain_independent_scroll_areas():
    assert "self.top_ui_scroll = top_scroll" in SOURCE
    assert "self.bottom_render_scroll = bottom_scroll" in SOURCE
    assert 'bottom_scroll.setObjectName("grooveboxVisualExportScroll")' in SOURCE
    assert 'top_scroll.setObjectName("grooveboxWorkstationScroll")' in SOURCE
