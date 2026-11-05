from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent
SOURCE = (ROOT / 'groovebox.py').read_text(encoding='utf-8')
OVERLAY = (ROOT / 'BUILD_ISO' / 'app-overlay-v35.22zz' / 'groovebox.py')


def test_source_parses_and_slot_controls_are_connected():
    ast.parse(SOURCE)
    for token in (
        'self.popup_chord_slot_prev = QPushButton("◀ Slot")',
        'self.popup_chord_slot_next = QPushButton("Slot ▶")',
        'self.popup_chord_slot_index.valueChanged.connect(self._on_chord_slot_selected)',
        'self.popup_chord_interval.valueChanged.connect(self._on_chord_interval_changed)',
        'def _step_chord_slot(self, delta):',
        'def _on_chord_interval_changed(self, value):',
    ):
        assert token in SOURCE


def test_slot_values_are_sequence_local_and_canonicalized():
    assert 'mem["chord_intervals"] = intervals' in SOURCE
    assert 'normalize_chord_intervals(mem.get("chord_intervals", [0, 4, 7]), count, 512)' in SOURCE
    assert 'Preserve the complete authored tail when note count is reduced' in SOURCE
    assert '"chord_intervals": copy.deepcopy(mem.get("chord_intervals", [0, 4, 7]))' in SOURCE
    assert '"chord_note_count": int(mem.get("chord_note_count", 3) or 3)' in SOURCE
    assert 'self._canonical_write_sequence_runtime(name, sid)' in SOURCE


def test_chord_intervals_affect_rendered_pitch_with_vectorized_subdivision():
    assert 'CHORD_SLOT_RENDER_HF24' in SOURCE
    assert 'apply_chord_slot_pitch(pitch_track, s_mask, float(pr), _ci, _cc, self._canonical_chord_note_budget(), fine_cents=_fine)' in SOURCE
    assert 'from spatial_synth_engines import (apply_chord_slot_pitch, normalize_chord_intervals, normalize_chord_slot_features, chord_slot_feature_tracks, canonical_geometric_rhythm_plan, generate_geometric_carrier_audio)' in SOURCE


def test_iso_overlay_matches_active_source():
    assert OVERLAY.read_text(encoding='utf-8') == SOURCE
