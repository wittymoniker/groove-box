"""SEED_TOOLS_20261112 / UNIVERSAL_SIGNAL_20261112 / UNIVERSAL_FRAMES_20261112 contract."""
import os
import numpy as np
import pytest

import seed_tools as st
import spectral_canonical as sc
import video_canonical as vc


@pytest.fixture()
def wavs(tmp_path):
    from scipy.io import wavfile
    sr = 48000; t = np.arange(sr) / sr
    a = 0.3 * np.sin(2 * np.pi * 440 * t); b = a.copy(); b[sr // 4: sr // 2] += 0.2 * np.sin(2 * np.pi * 1000 * t[: sr // 4])
    pa, pb, pc = (str(tmp_path / n) for n in ("a.wav", "b.wav", "c.wav"))
    wavfile.write(pa, sr, (a * 32767).astype(np.int16)); wavfile.write(pb, sr, (b * 32767).astype(np.int16))
    wavfile.write(pc, 44100, (128 + 60 * np.sin(2 * np.pi * 440 * np.arange(44100) / 44100)).astype(np.uint8))
    return pa, pb, pc


@pytest.mark.parametrize("value", [None, 3, 2.5, True, 1 + 2j, "text", b"\x00\xff" * 9, {"a": 1}, [], np.zeros(0),
                                   np.full(9, np.nan), np.array([np.inf, -np.inf]), np.arange(10, dtype=np.uint16),
                                   np.random.default_rng(1).normal(size=(3, 2, 50)), np.ones((500, 2)) * 7])
def test_coerce_signal_accepts_anything(value):
    x, sr = sc.coerce_signal(value)
    assert x.ndim == 2 and x.shape[1] >= 1 and np.all(np.isfinite(x)) and np.max(np.abs(x)) <= 1.0
    assert sc.roundtrip_error(x, sr) < 1e-5


def test_uint8_wav_is_centred(wavs):
    x, sr, _ = st.load_signal(wavs[2])
    assert sr == 44100 and abs(float(x.mean())) < 0.02


def test_literal_seed_damage_is_clean_error():
    s = sc.analyse(np.zeros(100), 48000)
    for bad in (s[:20], s[: len(s) // 2], sc.LITERAL_PREFIX + "!!!"):
        with pytest.raises(ValueError):
            sc.synthesize_literal(bad)
    v = vc.analyse(np.zeros((1, 4, 4, 3), np.uint8), 1)
    with pytest.raises(ValueError):
        vc.synthesize_literal(v[:12])


def test_low_rate_generative_is_not_silent():
    x, _ = sc.synthesize_generative("seed", seconds=0.5, sample_rate=8000)
    assert float(np.sqrt(np.mean(x ** 2))) > 1e-3


@pytest.mark.parametrize("value", [np.zeros((4, 4)), np.ones((2, 5, 5), bool), np.random.default_rng(0).random((2, 6, 6)),
                                   np.zeros((1, 6, 6, 4), np.uint16), b"hello", np.full((2, 3, 3, 1), np.nan), np.arange(7)])
def test_coerce_frames_accepts_anything(value):
    f = vc.coerce_frames(value)
    assert f.ndim == 4 and f.shape[3] == 3 and f.dtype == np.uint8 and vc.roundtrip_exact(f)


def test_exact_file_seed_roundtrip(tmp_path, wavs):
    p = tmp_path / "blob.bin"; p.write_bytes(os.urandom(5000))
    for src in (str(p), wavs[0]):
        s = st.file_to_seed(src)
        assert st.seed_kind(s) == "literal-bytes"
        out = st.seed_to_file(s, str(tmp_path / "out"))
        assert open(out, "rb").read() == open(src, "rb").read()
    with pytest.raises(ValueError):
        st.seed_to_bytes(st.file_to_seed(str(p))[:40])


def test_signal_file_seed_is_literal_audio(wavs):
    s = st.file_to_seed(wavs[0], mode="signal")
    x, sr = sc.synthesize_literal(s)
    assert sr == 48000 and x.shape == (1, 48000)


def test_common_seed_is_deterministic_and_finds_shared_partial(wavs):
    c1 = st.find_common([wavs[0], wavs[1], wavs[2]], seconds=1.0)
    c2 = st.find_common([wavs[2], wavs[0], wavs[1]], seconds=1.0)
    assert c1["seed"] == c2["seed"] and sc.is_literal(c1["seed"])
    assert abs(c1["peak_hz"] - 440) < 30 and 0.0 < c1["shared_energy"] <= 1.0 + 1e-9


def test_signal_diff_locates_and_reconstructs(wavs):
    seed, loc = st.diff_to_seed(wavs[0], wavs[1])
    s0, s1 = (float(v) for v in loc.split(" s")[0].split("–"))
    assert 0.2 <= s0 <= 0.26 and 0.49 <= s1 <= 0.53
    xb, _ = st.apply_diff(wavs[0], seed)
    ref, _, _ = st.load_signal(wavs[1])
    assert np.max(np.abs(xb - ref)) < 1e-6
    assert st.diff_to_seed(wavs[0], wavs[0])[1].startswith("identical")


def test_byte_diff_exact(tmp_path):
    a = tmp_path / "a.txt"; b = tmp_path / "b.txt"
    a.write_bytes(b"x" * 1000); b.write_bytes(b"x" * 400 + b"CHANGED" + b"x" * 590)
    seed, loc = st.diff_to_seed(str(a), str(b))
    assert "bytes 400" in loc and st.apply_diff(str(a), seed) == b.read_bytes()
    with pytest.raises(ValueError):
        st.apply_diff(b"y" * 1000, seed)


def test_plan_render_validates():
    j = st.plan_render("abc", 10, "1080p")
    assert (j["width"], j["height"], j["frames"], j["seed_kind"]) == (1920, 1080, 300, "generative")
    assert st.plan_render("abc", 1, "1281x721")["resolution"] == "1280x720"
    for bad in (dict(duration_s=0), dict(resolution="huge"), dict(audio_rate=12345)):
        with pytest.raises(ValueError):
            st.plan_render("abc", **{"duration_s": 1, **bad})


def test_synthesize_any_reaches_every_medium():
    r = st.synthesize_any("hello", seconds=0.5, frames=4, width=32, height=18)
    assert r["audio"][0].shape == (2, 24000) and r["video"][0].shape == (4, 18, 32, 3)
    r = st.synthesize_any(st.bytes_to_seed(b"any bytes at all", "x"))
    assert r["bytes"] == b"any bytes at all" and r["audio"][0].shape[0] == 1
