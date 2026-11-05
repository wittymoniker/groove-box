from pathlib import Path


def test_video_visual_fractal_contract_is_present():
    source = Path(__file__).with_name("groovebox.py").read_text(encoding="utf-8")
    assert "UNIVERSAL_FRACTAL_MOTION_20261024" in source
    assert "for octave in range(5)" in source
    assert "frequency = PHI ** octave" in source
    assert "alpha = max(0.06, min(1.0, alpha))" in source
    assert "alpha = max(0.08, min(1.0, alpha))" in source


def test_instrument_center_marker_removed():
    source = Path(__file__).with_name("groovebox.py").read_text(encoding="utf-8")
    assert "self.engine._dot(img,cx,cy,core,0.9*alpha,r=2)" not in source
    assert "self.engine._dot(img,cx,cy,core,0.65*alpha,r=2)" not in source
    assert "self.engine._dot(img,cx,cy,core,0.8*alpha,r=2)" not in source
