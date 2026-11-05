"""GROOVEBOX_UNIFIED_EXPORT_20261101 + GROOVEBOX_NAMEERROR_FIX_20261101 regression contract."""
import os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
SRC = (ROOT / "groovebox.py").read_text(encoding="utf-8")


_APP = None


import pytest


@pytest.fixture(scope="module", autouse=True)
def _release_qapplication():
    """Do not leave a QApplication behind: other suites assert the process has none."""
    # The shared QApplication is kept: deleting it aborted every later suite that
    # had already fetched it (no suite requires a QApplication-free process).
    yield


def _dialog():
    global _APP
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])   # keep a reference: a GC'd QApplication aborts Qt
    import export_dialog as E

    class Host:
        export_counter = 3
        _last_audio_bitrate_kbps = 256
        def _default_export_part_count(self): return 8
        def _export_frame_size(self): return (1920, 1080)
    return E, E.ExportAllDialog(Host(), None, "mp3", "/tmp/ex")


def test_every_format_is_selectable_with_its_own_settings():
    E, d = _dialog()
    keys = [k for k, *_ in E.FORMATS]
    for k in ("wav", "flac", "mp3", "ogg", "opus", "aiff", "caf", "mp4+a", "webm+a", "avi+a",
              "mp4", "webm", "avi", "image", "mcc", "meum"):
        assert k in keys
    for k, lossy in (("wav", 0), ("flac", 0), ("mp3", 1), ("ogg", 1), ("opus", 1), ("aiff", 0), ("caf", 0)):
        d.combo_format.setCurrentIndex(d.combo_format.findData(k))
        assert d.spin_br.isEnabled() == bool(lossy), k
        assert d.spin_parts.isVisibleTo(d) and d.chk_stitch.isVisibleTo(d)
    d.combo_format.setCurrentIndex(d.combo_format.findData("mp4+a"))
    assert d.spin_br.isEnabled() and d.spin_w.value() == 1920
    d.combo_format.setCurrentIndex(d.combo_format.findData("avi"))
    assert not d.spin_br.isEnabled()
    d.combo_format.setCurrentIndex(d.combo_format.findData("mcc"))
    assert d.edit_path.text().endswith(".MCC") and d.grp_project.isVisibleTo(d)


def test_preset_carries_parts_bitrate_and_rates():
    E, d = _dialog()
    d.combo_format.setCurrentIndex(d.combo_format.findData("opus"))
    d.spin_parts.setValue(32); d.spin_br.setValue(128); d.combo_quality.setCurrentIndex(1)
    d.combo_out_sr.setCurrentIndex(d.combo_out_sr.findData(48000))
    p = d.result_preset()
    assert (p["parts"], p["bitrate"], p["render_sr"], p["output_sr"], p["bit_depth"]) == (32, 128, 96000, 48000, 24)


def test_output_rate_above_render_rate_is_rejected():
    E, d = _dialog()
    d.combo_quality.setCurrentIndex(3)
    d.combo_out_sr.setCurrentIndex(d.combo_out_sr.findData(96000))
    d._accept()
    assert d.result() == 0


def test_app_wiring_and_menu():
    assert "def export_all_formats_dialog" in SRC and "def export_project_mcc" in SRC
    assert 'export_menu.addAction("💾 Project (.MCC)…")' in SRC
    assert all(f'"{f}"' in SRC.split("_more_audio")[1][:300] for f in ("ogg", "opus", "aiff", "caf"))
    assert SRC.count('_pre = self.__dict__.pop("_export_preset", None)') == 2
    assert "self._export_preset = None" in SRC            # never leaks a stale preset


def test_previously_undefined_names_are_defined():
    assert "QProgressDialog," in SRC.split("class _NoWheelSliderFilter")[0]
    assert re.search(r"^from pathlib import Path", SRC, re.M)
    assert "QRect, QRectF" in SRC and "SERIES_TAU = 2.0 * _SERIES_PI" in SRC
    assert 'gas.get("apply_enabled", False))' not in SRC.split("_add():")[1][:900]


def test_overlay_matches_root():
    ov = ROOT / "BUILD_ISO" / "app-overlay-v35.22zz" / "groovebox.py"
    assert ov.read_bytes() == (ROOT / "groovebox.py").read_bytes()


def test_mcc_media_formats_listed_and_routed():
    import export_dialog as ed
    keys = {k: (fam, ext) for k, _l, fam, ext, _i in ed.FORMATS}
    assert keys["mcc-audio"] == ("audio", ".MCC")
    assert keys["mcc-video"][0] == "mccvideo"
    src = open("groovebox.py", encoding="utf-8").read()
    assert 'self.export_mixdown_dialog("mcc" if key == "mcc-audio" else key)' in src
    assert "self.export_video_mcc_dialog()" in src
