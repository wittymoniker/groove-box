import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PyQt6.QtWidgets import QApplication
import groovebox as g
import mcc_media as mm
_qa = QApplication.instance() or QApplication([])


def test_picture_to_mcc_and_back_through_app_converter():
    from PIL import Image
    d = tempfile.mkdtemp()
    arr = (np.random.default_rng(3).integers(0, 255, (24, 32, 3))).astype(np.uint8)
    png = os.path.join(d, "a.png"); Image.fromarray(arr).save(png)
    app = g.MathematiciansGrooveboxApp()
    assert app.acceptDrops() and app._convertible_media(png)
    done, failed = app.convert_media_paths([png], show_result=False)
    assert not failed and done[0].endswith(".MCC") and app._convertible_media(done[0])
    done2, failed2 = app.convert_media_paths([done[0]], show_result=False)
    assert not failed2 and done2[0].lower().endswith(".png")
    assert np.array_equal(np.asarray(Image.open(done2[0]).convert("RGB")), arr)
