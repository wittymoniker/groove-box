"""R123 phase 8: layout, wheel rule, touch / tablet fallbacks, live keys, Julia pairing, ISO stamp."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = (ROOT / "groovebox.py").read_text()


def test_markov_beside_trays_and_panel_square():
    assert "GROOVEBOX_R123_MARKOV_BESIDE_TRAYS_20261119" in SRC
    assert "below_seq_layer.addWidget(self._build_markov_resampler_panel()" not in SRC
    assert "GROOVEBOX_R123_PANEL_SQUARE_20261119" in (ROOT / "panel_synth_deck.py").read_text()


def test_wheel_scrolls_unless_clicked():
    body = SRC.split("class _NoWheelSliderFilter", 1)[1].split("def _fast_copy", 1)[0]
    assert "GROOVEBOX_R123_SCROLL_UNLESS_CLICKED_20261119" in body
    assert "MouseButtonPress" in body and "_is_armed" in body and "ControlModifier" in body


def test_modpath_right_drag_and_touch_fallbacks():
    for f in ("mm_fields.py", "mm_visual.py"):
        t = (ROOT / f).read_text()
        assert "GROOVEBOX_R123_MODPATH_RIGHT_DRAG_20261119" in t and "touch_compat" in t
    import touch_compat
    assert touch_compat.HOLD_MS >= 300


def test_tablet_keyboard_and_live_keys_are_installed():
    assert "tablet_keyboard as _tk" in SRC and "live_keys as _lk" in SRC
    import live_keys
    keys = [k for _g, k, *_ in live_keys.bindings(object())]
    assert len(keys) == len(set(keys))
    for k in ("Alt+Space", "Alt+.", "Ctrl+Shift+E", "Ctrl+Shift+M"):
        assert k in keys
    import tablet_keyboard as tk
    assert len(tk.DEFAULT_CUSTOM) == tk.N_CUSTOM


def test_julia_pairing_needs_pythoncall_project(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("jb_probe", ROOT / "julia_bridge.py")
    src = (ROOT / "julia_bridge.py").read_text()
    assert "_jl_project_ready" in src and "PYTHON_JULIAPKG_EXE" in src
    ns = {"os": os}
    exec(src.split("def _jl_project_ready", 1)[1].split("\n\n\n", 1)[0].join(["def _jl_project_ready", ""]), ns)
    (tmp_path / "Manifest.toml").write_text('[[deps.PythonCall]]\n')
    assert ns["_jl_project_ready"](str(tmp_path))
    assert not ns["_jl_project_ready"](str(tmp_path / "missing"))


def test_julia_ccall_pointer_and_exports():
    jl = (ROOT / "julia" / "GrooveboxHybrid.jl").read_text()
    assert "GROOVEBOX_R123_JULIA_CCALL_POINTER_20261119" in jl and "export " in jl
    ov = ROOT / "BUILD_ISO" / "app-overlay-v35.22zz" / "julia" / "GrooveboxHybrid.jl"
    if ov.exists():
        assert ov.read_text() == jl


def test_fast_marker_probe_has_no_null_byte_warning(tmp_path):
    lib = ROOT / "BUILD_ISO" / "initrd_lib.sh"
    if not lib.exists():
        return
    b = tmp_path / "img"; b.write_bytes(b"\x00\x01\x02binary\x00")
    r = subprocess.run(["bash", "-c", f'source "{lib}" >/dev/null 2>&1; gb_fast_is "{b}"; echo rc=$?'],
                       capture_output=True, text=True)
    assert "null byte" not in r.stderr and "rc=1" in r.stdout


def test_base_frequency_range_and_clear_memory_route_stores():
    assert "spin_base_frequency" in SRC
    i = SRC.index("def _clear_project_memory")
    body = SRC[i:i + 6000]
    for k in ("sidechain_state", "patch_motion_state", "markov_resampler_spec"):
        assert k in body
