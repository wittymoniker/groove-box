"""R31 regression tests: settings, PIN, reset safety, multidim net-mod cap, export pathway, live tools."""
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _src(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_smart_process_and_pin_settings_persist(tmp_path, monkeypatch):
    monkeypatch.setenv("GROOVEBOX_COMPAT_SETTINGS", str(tmp_path / "compat-settings.json"))
    import compat_settings as cs
    st = cs.load()
    st.update(smart_process=False, ask_session_name=True, startup_chime=False, pin_digits=6, pin_idle_minutes=5)
    assert cs.save(st)
    back = cs.load()
    assert back["smart_process"] is False and back["ask_session_name"] is True and back["startup_chime"] is False
    assert back["pin_digits"] == 6 and back["pin_idle_minutes"] == 5
    # a PIN flag without a hash is never treated as enabled
    st["pin_enabled"] = True; st["pin_hash"] = ""; cs.save(st)
    assert cs.load()["pin_enabled"] is False


def test_pin_hash_check_and_length():
    import pin_lock as pl
    salt, h = pl.hash_pin("482913")
    st = {"pin_enabled": True, "pin_salt": salt, "pin_hash": h, "pin_digits": 6}
    assert pl.check_pin("482913", st)
    assert not pl.check_pin("4829", st) and not pl.check_pin("482914", st) and not pl.check_pin("48291a", st)
    assert pl.digits({"pin_digits": 99}) == 8 and pl.digits({"pin_digits": 1}) == 4
    assert "482913" not in str(st)


def test_reset_targets_refuse_unsafe_roots(tmp_path, monkeypatch):
    import pin_lock as pl
    monkeypatch.setenv("GROOVEBOX_DATA_DIR", str(tmp_path / "MathematiciansGroovebox"))
    monkeypatch.setenv("GROOVEBOX_COMPAT_SETTINGS", str(tmp_path / "MathematiciansGroovebox" / "compat-settings.json"))
    assert pl.reset_targets() == [os.path.realpath(str(tmp_path / "MathematiciansGroovebox"))]
    monkeypatch.setenv("GROOVEBOX_DATA_DIR", str(tmp_path / "somewhere_else"))
    assert all("somewhere_else" not in t for t in pl.reset_targets())
    assert pl.RESET_SECONDS == 75 * 60


def test_multidim_net_mod_cap():
    import multidim_synth as md
    routes = [{"source": "s", "target": "pitch", "amount": 0.8}, {"source": "s", "target": "pitch", "amount": 0.7}]
    src = {"s": np.ones(8)}
    assert float(md._xmod_target_delta(routes, "pitch", src, 8)[0]) == 1.0
    assert float(md._xmod_target_delta(routes, "pitch", src, 8, cap=0.5)[0]) == 0.5
    assert float(md._xmod_target_delta(routes, "pitch", src, 8, cap=0.0)[0]) == 0.0
    s = _src("multidim_synth.py")
    assert s.count("cap=_net_cap)") >= 8 and md.MD_NET_MOD_DEFAULT == 0.5
    g = _src("groovebox.py")
    assert 'p["xmod_net_max"] = float(getattr(self, "md_net_mod_max", 0.5))' in g
    assert 'data.get("md_net_mod_max", 1.0)' in g        # pre-R31 projects keep their old ceiling


def test_audio_export_masters_once_and_never_renders_in_window():
    g = _src("groovebox.py")
    body = g[g.index("    def export_mixdown_dialog("):g.index("    def _resolve_ffmpeg_binary(")]
    assert "_master_hardclip(" not in body and "_bake_dj_write(" not in body
    assert "_export_scheduler().submit_audio(" in body
    assert "An audio export is already running" not in body
    w = _src("export_worker.py")
    assert w.count("_bake_dj_write(") == 2 and '"audio_file"' in w     # once for batch "final", once for audio_file
    assert 'raise RuntimeError("synchronous worker render retired' in g


def test_scheduler_never_blocks_ui_thread():
    s = _src("export_scheduler.py")
    s = s.split('"""', 2)[2]                     # skip the module docstring (it names what is NOT done)
    for bad in ("processEvents(", ".exec()", ".result(", "waitForFinished(", "time.sleep("):
        assert bad not in s, bad
    import export_scheduler as es
    assert 1 <= es.default_parallel() <= 3


def test_live_player_teardown_is_off_ui():
    s = _src("live_player.py")
    stop = s[s.index("    def stop(self):\n        \"\"\"LIVE_TEARDOWN_R31"):s.index("    def _teardown_off_ui(")]
    assert ".join(" not in stop.replace("lambda w=w: w.join", "") and "eng.close()" not in stop
    assert "_teardown_busy()" in s


def test_new_modules_ship_in_iso_and_exe_inventory():
    from runtime_payload import runtime_module_names
    names = set(runtime_module_names(ROOT))
    for m in ("export_scheduler", "pin_lock", "sequence_perform_row", "clip_studio_performance"):
        assert m in names
        assert (ROOT / "BUILD_ISO" / "app-overlay-v35.22zz" / (m + ".py")).read_bytes() == (ROOT / (m + ".py")).read_bytes()


def test_tap_tempo_and_state_slots_logic():
    from PyQt6.QtWidgets import QApplication, QDoubleSpinBox
    global _QAPP
    _QAPP = QApplication.instance() or QApplication([])          # keep a reference: Qt must outlive the widgets
    import sequence_perform_row as sp

    class Host:
        pass
    h = Host(); h.spin_bpm = QDoubleSpinBox(); h.spin_bpm.setRange(1, 999)
    h._project_snapshot = lambda: {"bpm": h.spin_bpm.value()}
    applied = []
    h._apply_project_snapshot = lambda d: applied.append(d)
    h.reload_active_instrument_sequencer_ui = lambda: None
    h._push_undo = lambda *_: None
    row = sp.SequencePerformRow(h)
    import time as _t
    base = _t.monotonic()
    row._taps = [base - 1.0, base - 0.5]
    orig = sp.time.monotonic
    sp.time.monotonic = lambda: base
    try:
        row.tap()
    finally:
        sp.time.monotonic = orig
    assert abs(h.spin_bpm.value() - 120.0) < 0.2
    row.slot_store("A"); row.slot_recall("A")
    assert applied and applied[0]["bpm"] == h.spin_bpm.value()
