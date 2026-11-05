import numpy as np
import wavespace as ws


def _peak_hz(freq, sr=44100, dur=0.5):
    t = np.arange(int(sr * dur), dtype=np.float64) / sr
    phase = 2.0 * np.pi * freq * t                       # the same phase the panel synth voice uses
    a = np.zeros(16); b = np.zeros(16); a[0] = 1.0; a[2] = 0.3
    out = ws.geometric_voice(phase, t, dur, 0, (a, b), sample_rate=sr, harmonic_cap=16,
                             vector=(0.3, -0.2, 0.1), ball=None, density=None,
                             depths={"vector": 0.8, "ball": 0.0, "cellular": 0.0})
    spec = np.abs(np.fft.rfft(out * np.hanning(out.size)))
    return np.fft.rfftfreq(out.size, 1.0 / sr)[int(np.argmax(spec))]


def test_geometric_voice_fundamental_follows_the_note_phase():
    for f in (110.0, 261.63, 432.0, 880.0):
        assert abs(_peak_hz(f) - f) < 3.0


def test_render_feeds_geometric_and_panel_voice_the_same_phase():
    src = open("groovebox.py", encoding="utf-8").read()
    i = src.index("_ws_v = _ws_geometric_voice(")
    assert src[i:i + 120].split("(")[1].strip().startswith("phase,")
    j = src.index("voice_raw = (1.0 - entropy) * harm + entropy * inh")
    assert "phase" in src[j - 900:j]
