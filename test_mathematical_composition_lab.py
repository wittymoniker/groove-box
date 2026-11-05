from pathlib import Path
import json
from mathematical_composition_lab import generate_pattern, euclidean_pattern, export_pattern

ROOT=Path(__file__).resolve().parent

def test_euclidean_edges_and_rotation_are_bounded():
    assert euclidean_pattern(8,0)==[0]*8
    assert euclidean_pattern(8,8)==[1]*8
    assert sum(euclidean_pattern(16,5))==5
    assert sum(euclidean_pattern(16,5,3))==5

def test_all_pattern_families_are_deterministic_and_bounded():
    for kind in ("Euclidean rhythm","Polyrhythm overlay","Fibonacci contour","Fractal / recursive","Probability / seeded"):
        a=generate_pattern(kind,steps=16,pulses=5,seed=42,bars=3)
        b=generate_pattern(kind,steps=16,pulses=5,seed=42,bars=3)
        assert a==b
        assert a['event_count']==len(a['events'])
        assert all(0 <= e['note'] <= 127 and 1 <= e['velocity'] <= 127 for e in a['events'])
        assert all(0 <= e['beat'] < a['duration_beats'] for e in a['events'])

def test_pattern_export_json_and_csv(tmp_path):
    p=generate_pattern('Euclidean rhythm',steps=8,pulses=3)
    jp=export_pattern(p,tmp_path/'x.json')
    assert json.loads(jp.read_text())['event_count']==p['event_count']
    cp=export_pattern(p,tmp_path/'x.csv')
    assert 'beat,duration_beats,note,velocity,bar,step' in cp.read_text()

def test_ui_integration_is_lazy_and_root_overlay_synced():
    src=(ROOT/'groovebox.py').read_text()
    assert 'self.btn_math_composition_lab.clicked.connect(self._open_math_composition_lab)' in src
    assert 'from mathematical_composition_lab import open_math_composition_lab' in src
    assert src==(ROOT/'BUILD_ISO'/'app-overlay-v35.22zz'/'groovebox.py').read_text()
    assert (ROOT/'mathematical_composition_lab.py').read_bytes()==(ROOT/'BUILD_ISO'/'app-overlay-v35.22zz'/'mathematical_composition_lab.py').read_bytes()


def test_playlist_writer_is_deterministic_and_canonical_compatible():
    from mathematical_composition_lab import generate_playlist_data
    a = generate_playlist_data(rows=24, algorithm="Fibonacci walk", heuristic="Arc / crescendo", seed=19)
    b = generate_playlist_data(rows=24, algorithm="Fibonacci walk", heuristic="Arc / crescendo", seed=19)
    assert a == b
    assert len(a["rows_data"]) == 24
    required = {"position", "time_marker", "script_tag", "domain_tag", "synth_tag", "patch_tag",
                "velocity", "effect_target", "auto_amount", "direction_vector", "multi_seq",
                "coverage", "blend_partner", "live_parametrics", "sequence_ref", "sequence_attack",
                "sequence_release", "pitch_ratio", "provenance"}
    for row in a["rows_data"]:
        assert required.issubset(row)
        assert 1 <= row["velocity"] <= 127
        assert 0 <= row["coverage"] <= 1
        assert row["provenance"]["deterministic"] is True


def test_playlist_writer_algorithms_and_heuristics_change_structure_without_randomness():
    from mathematical_composition_lab import generate_playlist_data
    outputs = [generate_playlist_data(rows=16, algorithm=algo, heuristic="Balanced", seed=3)["rows_data"]
               for algo in ("Balanced progression", "Ascending / descending", "Euclidean cycle", "Fractal / recursive")]
    assert any(outputs[0] != other for other in outputs[1:])
    conservative = generate_playlist_data(rows=16, heuristic="Sparse / conservative", seed=3)["rows_data"]
    dense = generate_playlist_data(rows=16, heuristic="Aggressive / dense", seed=3)["rows_data"]
    assert conservative != dense
