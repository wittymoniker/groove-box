"""R32: Live Player (and every non-modal tool window) minimises on its own; OS-style arrange actions."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("GROOVEBOX_DATA_DIR", os.path.join(os.path.dirname(__file__), ".test-data-r32"))
import pytest


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    global _QA
    _QA = QApplication.instance() or QApplication([])
    import groovebox as g
    w = g.MathematiciansGrooveboxApp()
    w.show()
    _QA.processEvents()
    return w


def test_live_player_is_independent_of_main(app):
    from PyQt6.QtWidgets import QApplication
    from live_player import LivePlayerWindow
    lp = LivePlayerWindow(app)
    lp.show()
    QApplication.processEvents()
    h = lp.windowHandle()
    assert h is not None
    assert h.transientParent() is None            # not a satellite of Main any more
    assert lp.parent() is app                      # Qt ownership (host) kept
    lp.showMinimized()
    QApplication.processEvents()
    assert lp.isMinimized()
    assert not app.isMinimized()
    lp.showNormal()
    lp.close()


def test_modal_dialog_keeps_owner(app):
    # Groovebox's own compat layer turns most source dialogs non-modal; a window that is
    # still modal, or opts out with grooveboxKeepOwner, must keep its owner.
    import window_manager as wm
    from PyQt6.QtWidgets import QDialog
    from PyQt6.QtCore import Qt
    d = QDialog(app)
    d.setWindowModality(Qt.WindowModality.ApplicationModal)
    if wm.is_modal(d):          # the app compat layer may have relaxed it already
        assert wm.make_independent(d) is False
    e = QDialog(app); e.setProperty("grooveboxKeepOwner", True)
    assert wm.make_independent(e) is False


def test_manager_installed_with_arrange_actions(app):
    import window_manager as wm
    from PyQt6.QtWidgets import QApplication, QMenu
    m = wm.manager()
    assert m is not None
    menu = QMenu()
    m.build_arrange_menu(menu)
    assert len([a for a in menu.actions() if not a.isSeparator()]) >= 10
    m.tile_all(); m.cascade_all(); m.minimize_all(); m.restore_all(); m.next_window()
    QApplication.processEvents()
    assert not app.isMinimized()


def test_export_queue_windows_are_independent(app):
    """R32.1 (user report): the Export Jobs and Render Queue windows behaved like dialogs of Main."""
    from PyQt6.QtWidgets import QApplication, QDialog
    from PyQt6.QtCore import Qt
    jobs = app.show_export_jobs()
    rq = app.render_queue_dialog()
    QApplication.processEvents()
    for w in (jobs, rq):
        assert not isinstance(w, QDialog)
        assert w.windowModality() == Qt.WindowModality.NonModal
        h = w.windowHandle()
        assert h is not None and h.transientParent() is None
        w.showMinimized(); QApplication.processEvents()
        assert w.isMinimized() and not app.isMinimized()
        w.showNormal()
    # the finish report must not block the main window
    rq._queue_items, rq._queue_done, rq._queue_failed = [{"key": "wav"}], ["wav"], []
    rq._finish_queue(); QApplication.processEvents()
    assert rq._finish_box is not None and rq._finish_box.windowModality() == Qt.WindowModality.NonModal
    rq.close(); jobs.close()


def test_geometry_memory_roundtrip(app, tmp_path):
    import window_manager as wm
    from PyQt6.QtWidgets import QApplication, QDialog
    d = QDialog(app)
    d.setWindowTitle("R32 geometry probe")
    d.show(); QApplication.processEvents()
    d.setGeometry(100, 120, 420, 300); QApplication.processEvents()
    wm.remember_geometry(d)
    d.hide()
    e = QDialog(app); e.setWindowTitle("R32 geometry probe")
    e.show(); QApplication.processEvents()
    assert (e.width(), e.height()) == (420, 300)
    e.hide()
