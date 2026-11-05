import os, sys, time, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt6.QtWidgets import QApplication
import performance as P
_KEEP = []


def _app():
    # Fetched when the test runs: another suite may delete the shared QApplication
    # after this module was imported (holding it from import time aborts Qt).
    a = QApplication.instance()
    if a is None:
        a = QApplication([]); _KEEP.append(a)
    return a


def _pump(cond, secs=8):
    t = time.time()
    while time.time() - t < secs and not cond():
        _app().processEvents(); time.sleep(0.02)
    return cond()


def test_drop_copy_filter_hidden_and_path_box():
    home = os.path.expanduser("~")
    work = tempfile.mkdtemp(dir=home); src = tempfile.mkdtemp(dir=home)
    for n in ("song.wav", ".secret", "notes.txt"):
        open(os.path.join(work, n), "w").write("x")
    open(os.path.join(src, "dropped.wav"), "w").write("payload")
    _app()
    d = P.FileManagerDialog(None, work)
    assert _pump(lambda: d.list_widget.count() == 2)                 # hidden file not listed
    d.chk_hidden.setChecked(True); assert _pump(lambda: d.list_widget.count() == 3)
    d.edit_filter.setText("wav")
    assert [d.list_widget.item(i).isHidden() for i in range(d.list_widget.count())].count(False) == 1
    d.edit_filter.setText("")
    d._copy_into_dir([os.path.join(src, "dropped.wav")])
    assert _pump(lambda: os.path.exists(os.path.join(work, "dropped.wav")))
    d._copy_into_dir([os.path.join(src, "dropped.wav")])             # second copy never overwrites
    assert _pump(lambda: os.path.exists(os.path.join(work, "dropped (2).wav")))
    d.edit_path.setText(src); d._go_typed_path()
    assert d._dir == os.path.abspath(src)
