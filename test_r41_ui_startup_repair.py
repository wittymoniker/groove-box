from pathlib import Path

ROOT = Path(__file__).resolve().parent
GROOVE = (ROOT / "groovebox.py").read_text(encoding="utf-8")


def test_math_background_is_reasserted_after_full_ui_and_stylesheet_build():
    init = GROOVE[GROOVE.index("        self.init_ui_components()"):]
    init = init[:init.index("        self._install_math_symbol_numeric_overlays()") + 100]
    assert "R41.1_UI_POST_LAYOUT_BACKGROUND_REATTACH_20261104" in init
    assert "_final_cw = self.centralWidget()" in init
    assert "_ensure_single_math_background(" in init
    assert "self.parametric_background.lower()" in init
    assert "self._sync_parametric_background_geometry" in init


def test_main_workspace_is_realized_behind_startup_modal_as_fallback():
    startup = GROOVE[GROOVE.index("def launch_startup_mode_selector"):
                     GROOVE.index("# R31_QT_PAINT_OWNERSHIP_GUARD_20261104")]
    assert "R41.1_STARTUP_MAIN_WINDOW_FALLBACK_20261104" in startup
    assert "player.showNormal()" in startup
    assert "player.show()" in startup
    assert "player.lower()" in startup
    assert "dlg.exec()" in startup
