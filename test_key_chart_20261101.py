"""GROOVEBOX_KEY_CHART_20261101: letter + top-row number keys play the selected instrument on a linear scale."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = (ROOT / "groovebox.py").read_text(encoding="utf-8")


def _consts():
    rows = re.search(r'KEYCHART_ROWS = (\([^)]*\))', SRC).group(1)
    return eval(rows)


def test_chart_has_36_unique_letter_and_digit_keys_low_to_high():
    rows = _consts()
    order = "".join(rows)
    assert len(order) == 36 and len(set(order)) == 36
    assert rows[0].startswith("Z") and rows[-1] == "1234567890"        # bottom row lowest, number row highest
    assert set(order) == set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")   # every letter and digit, nothing else


def test_linear_scale_is_equal_hz_steps():
    assert "return 1.0 + float(degree) / float(steps)" in SRC


def test_filter_only_acts_for_the_active_main_window_and_never_steals_typing():
    body = SRC.split("def _keychart_handle_key")[1].split("def _keychart_trigger")[0]
    for guard in ("ControlModifier", "AltModifier", "MetaModifier", "KeypadModifier", "isAutoRepeat",
                  "_win not in _ok_windows", "isActiveWindow", "activePopupWidget", "activeModalWidget",
                  "_keychart_text_entry_focused(obj)"):
        assert guard in body, guard
    entry = SRC.split("def _keychart_text_entry_focused")[1].split("def _keychart_handle_key")[0]
    for kind in ("QLineEdit", "QTextEdit", "QPlainTextEdit", "QAbstractSpinBox", "isEditable", "EditingState"):
        assert kind in entry, kind


def test_hit_voice_has_direct_pitch_path_that_bypasses_boost():
    assert "pitch_ratio=None, hit_seconds=None" in SRC
    assert 'if getattr(self, "pkp_boost_active", False) and not _direct_pitch:' in SRC
    assert "min(base_freq * _pr, 20000.0)" in SRC


def test_installed_at_startup_with_button():
    assert "self._install_keychart()" in SRC and "btn_key_chart" in SRC and "_show_key_chart_dialog" in SRC


def test_overlay_matches_root():
    ov = ROOT / "BUILD_ISO" / "app-overlay-v35.22zz" / "groovebox.py"
    assert ov.read_bytes() == (ROOT / "groovebox.py").read_bytes()


def test_no_limiter_added_to_key_note_path():
    src = open("groovebox.py", encoding="utf-8").read()
    assert "GROOVEBOX_KEY_NOTE_DECLICK" not in src
    i = src.index("def _pkp_poly_callback"); j = src.index("def _pkp_poly_submit")
    assert "tanh" not in src[i:j]
    ac = open("audio_check.py", encoding="utf-8").read()
    assert "1b · File-player settings" in ac and "1c · Key/Trigger settings" in ac and "1d · Main-window note engine" in ac


def test_no_soft_saturation_or_audition_peak_scaling():
    src = open("groovebox.py", encoding="utf-8").read()
    assert "np.tanh(gain * arr)" not in src
    i = src.index("def _pkp_poly_submit"); j = src.index("def _pkp_fire_step_hit")
    assert "0.98" not in src[i:j]


def test_audio_check_answers_window_is_nonmodal():
    src = open("groovebox.py", encoding="utf-8").read()
    i = src.index("def _run_audio_check"); j = src.index("def _on_seed_ws_override_toggled")
    body = src[i:j]
    assert "dlg.exec()" not in body
    assert "NonModal" in body and "WindowStaysOnTopHint" in body
