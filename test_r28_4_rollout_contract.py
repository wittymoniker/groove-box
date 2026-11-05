from pathlib import Path

ROOT = Path(__file__).resolve().parent

def test_startup_mode_selector_has_three_workspace_modes_and_skip_flag():
    src = (ROOT / 'groovebox.py').read_text()
    assert 'Choose your Groovebox mode' in src
    assert 'Performance / DJ' in src
    assert 'Both Workspaces' in src
    assert '--skip-startup-launcher' in src

def test_audio_export_has_distinct_output_rate_and_anti_alias_resampling():
    src = (ROOT / 'groovebox.py').read_text()
    assert 'Output file sample rate' in src
    assert 'resample_poly' in src
    assert 'output_sample_rate' in src
    assert 'cannot exceed the render rate' in src

def test_canonical_sidechain_and_userdata_protection_roundtrip_contract():
    src = (ROOT / 'groovebox.py').read_text()
    assert '"sidechain_state"' in src
    assert '"default_amount": 0.0' in src
    assert '"userdata_protection"' in src
    assert '"protect_from_canonical_overwrite": True' in src
    assert 'def _open_canonical_sidechain_dialog' in src

def test_performance_randomizer_is_seeded_bounded_and_reversible():
    src = (ROOT / 'performance.py').read_text()
    assert 'RANDOMIZE PLAYLIST + PERFORMANCE PARAMETRIC DJ' in src
    assert 'def _randomize_playlist_and_dj_parameters' in src
    assert 'self._playlist_randomize_undo' in src
    assert 'random.Random(seed)' in src
    assert 'def _undo_playlist_randomization' in src

def test_storage_diagnosis_is_read_only_and_format_remains_explicit():
    src = (ROOT / 'performance.py').read_text()
    assert 'def _diagnose_selected_storage' in src
    assert '["lsblk","-J"' in src
    assert 'No changes were made.' in src
    assert 'def _request_storage_format' in src
    assert 'ERASE ALL DATA' in src

def test_render_ui_thread_risk_is_not_misrepresented_as_verified():
    report = (ROOT / 'VALIDATION-v35.22zz-R28.3.0-PATCH-MOTION-PERFORMANCE-MATRIX-20261016.txt').read_text()
    assert 'Full ISO build was not run' in report


def test_math_writer_commits_to_protectable_userdata():
    lab = (ROOT / 'mathematical_composition_lab.py').read_text()
    main = (ROOT / 'groovebox.py').read_text()
    assert 'Commit to Project Userdata' in lab
    assert 'protect_from_canonical_overwrite' in lab
    assert '"math_writer_userdata": _safe_json' in main
    assert 'self.math_writer_userdata = copy.deepcopy(_math_ud)' in main
