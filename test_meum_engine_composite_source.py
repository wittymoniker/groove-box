from pathlib import Path
def test_composite_and_legacy_share_worker():
    s=Path("groovebox.py").read_text(encoding="utf-8")
    assert "def _apply_engine_with_shared_context" in s
    assert "def _apply_active_engines_meum_composite" in s
    legacy=s.split("def _apply_engine_deterministically",1)[1].split("def _apply_active_engines_meum_composite",1)[0]
    comp=s.split("def _apply_active_engines_meum_composite",1)[1].split("def _apply_goava_deterministically",1)[0]
    assert "_apply_engine_with_shared_context(engine, seed)" in legacy
    assert "_apply_engine_with_shared_context(engine, seed)" in comp
    assert 'QPushButton("Engines simplified by Meum: ON")' in s
