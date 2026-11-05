from pathlib import Path

ROOT = Path(__file__).resolve().parent
GROOVEBOX = (ROOT / "groovebox.py").read_text(encoding="utf-8")
COEDIT = (ROOT / "coedit.py").read_text(encoding="utf-8")
LIVE_EDIT = (ROOT / "live_edit_ui.py").read_text(encoding="utf-8")


def test_main_status_history_is_editable_and_bounded():
    assert 'setObjectName("GrooveboxStatusHistory")' in GROOVEBOX
    assert 'setEditable(True)' in GROOVEBOX
    assert 'setMaxCount(100)' in GROOVEBOX
    assert 'def _set_status_message(self, message' in GROOVEBOX


def test_swap_notifications_use_status_history_not_modal_popups():
    body = GROOVEBOX[GROOVEBOX.index('    def _memory_note_parked'):GROOVEBOX.index('    # ------------------------------------------------------------------\n    # GROOVEBOX_R23R_HARDWARE_FOLLOW')]
    assert 'self._set_status_message(msg)' in body
    assert 'QMessageBox' not in body
    assert '60.0' in body


def test_playlist_button_is_prominent_again():
    body = GROOVEBOX[GROOVEBOX.index('self.btn_view_playlist = _make_global_operator_button'):GROOVEBOX.index('self.btn_local_randomize = _make_global_operator_button')]
    assert 'setMinimumHeight(68)' in body
    assert 'setMinimumWidth(210)' in body


def test_parametric_math_background_is_not_hidden_by_opaque_central_widget():
    assert 'central_widget.setAutoFillBackground(False)' in GROOVEBOX
    assert 'QWidget#GrooveboxCentral {\n                background: transparent;' in GROOVEBOX
    assert 'class ParametricMathBackground(QWidget):' in GROOVEBOX
    assert 'self.parametric_background = _ensure_single_math_background(' in GROOVEBOX
    assert 'show=not self._math_background_deferred' in GROOVEBOX


def test_edit_together_syncs_project_snapshot_sections_over_coedit_transport():
    assert 'self.host._project_snapshot()' in LIVE_EDIT
    assert 's.local_tick()' in LIVE_EDIT
    assert '"/api/v1/coedit"' in COEDIT
    assert 'def _apply_sections(self, sections: Dict)' in COEDIT
    # Project document contains canonical, sequence, playlist, synth and engine state.
    for key in ('"engines"', '"canonical_engines"', '"instrument_param_state"',
                '"master_playlist_data"', '"instrument_sequencer_memory"',
                '"patch_motion_state"', '"master_vector_state"', '"ball_synth_params"',
                '"cellular_synth_params"'):
        assert key in GROOVEBOX
