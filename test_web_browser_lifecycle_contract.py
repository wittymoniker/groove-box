from pathlib import Path

ROOT = Path(__file__).resolve().parent

def test_webengine_page_is_released_before_profile():
    s=(ROOT/'web_browser_tab.py').read_text(errors='replace')
    fn=s[s.index('    def shutdown_webengine'):s.index('    def closeEvent',s.index('    def shutdown_webengine'))]
    assert 'downloadRequested' in fn and 'permissionRequested' in fn and '.disconnect(slot)' in fn
    assert 'view.setPage(None)' in fn
    assert 'page.deleteLater()' in fn
    assert 'QCoreApplication.sendPostedEvents' in fn
    assert fn.index('page.deleteLater()') < fn.index('profile.deleteLater()')

def test_performance_hide_does_not_destroy_reusable_browser():
    s=(ROOT/'performance.py').read_text(errors='replace')
    close=s[s.index('    def closeEvent(self, event):', s.index('class Performance')):]
    close=close[:close.index('\n    def ', 10)]
    assert 'shutdown_webengine' not in close
    assert 'WA_DeleteOnClose, False' in (ROOT/'groovebox.py').read_text(errors='replace')
