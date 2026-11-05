"""Static regression: playback start/stop guards (GROOVEBOX_PLAY_GUARD_20261031)."""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent
src = (ROOT / "groovebox.py").read_text(encoding="utf-8")
ov = (ROOT / "BUILD_ISO/app-overlay-v35.22zz/groovebox.py").read_text(encoding="utf-8")
checks = {
    "overlay identical to root": src == ov,
    "re-entrancy guard": "_play_begin_busy" in src,
    "stop invalidates in-flight render": "self._play_gen = int(getattr(self, \"_play_gen\", 0)) + 1" in src,
    "finish checks generation": "if _gen != getattr(self, \"_play_gen\", _gen):" in src,
    "stream open guarded": "stream open failed safely" in src and "def _abort_play_stream_open" in src,
    "no nested event loop in begin": "QApplication.processEvents()\n        def _work():" not in src,
    "preview override cleared on stop": "self._live_preview_rows_override = None\n        self._sequence_preview_instrument = \"\"" in src,
    "rename: combo keeps keys": "class _InstrumentKeyCombo(QComboBox)" in src,
    "rename: box wired": "self.qe_instrument.editingFinished.connect(self._commit_instrument_display_name)" in src,
    "rename: saved": 'snap["instrument_display_names"]' in src,
    "rename: project save": '"instrument_display_names": copy.deepcopy(' in src,
    "rename: loaded": "_apply_loaded_instrument_display_names(" in src,
    "rename: reset clears": "names.clear()" in src,
    "rename: resize prunes": "_display = self._sanitized_instrument_display_names(" in src,
}


def test_play_guards():
    bad = [k for k, v in checks.items() if not v]
    assert not bad, bad


if __name__ == "__main__":
    for k, v in checks.items():
        print(("PASS: " if v else "FAIL: ") + k)
    sys.exit(1 if any(not v for v in checks.values()) else 0)
