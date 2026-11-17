from pathlib import Path

ROOT = Path(__file__).parent

def test_edit_synth_per_seq_has_explicit_off_and_on_labels():
    src = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    assert "EDIT SYNTH\\nPER SEQ\\nOFF" in src
    assert "EDIT SYNTH\\nPER SEQ\\nON" in src
    assert "MAIN / shared" not in src

def test_provenance_ui_is_read_only_and_explains_sources():
    src = (ROOT / "parameter_provenance_ui.py").read_text(encoding="utf-8")
    assert "WA_TransparentForMouseEvents" in src
    assert "effective" in src
    assert "No explicit source contribution" in src

def test_multidim_legend_explains_all_four_sources():
    src = (ROOT / "multidim_ui.py").read_text(encoding="utf-8")
    for label in ("Seed baseline", "Canonical write", "Explicit user edit", "Step override", "effective net value"):
        assert label in src
