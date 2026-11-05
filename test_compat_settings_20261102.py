import json, os, importlib
import compat_settings as cs


def _fresh(tmp_path, monkeypatch, raw=None):
    p = tmp_path / "c.json"
    monkeypatch.setenv("GROOVEBOX_COMPAT_SETTINGS", str(p))
    for k in cs._MANAGED:
        monkeypatch.delenv(k, raising=False)
    cs._USER_ENV = None
    if raw is not None:
        p.write_text(json.dumps(raw))
    return p


def test_defaults_and_sanitising(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch, {"smooth_mode": "bogus", "threads": 999, "audio_latency": "x"})
    s = cs.load()
    assert s["smooth_mode"] == "auto" and s["threads"] == 64 and s["audio_latency"] == "auto"


def test_smooth_auto_by_core_count():
    assert cs.smooth_effective({"smooth_mode": "auto"}, cores=4)
    assert not cs.smooth_effective({"smooth_mode": "auto"}, cores=8)
    assert cs.smooth_effective({"smooth_mode": "on"}, cores=32)
    assert not cs.smooth_effective({"smooth_mode": "off"}, cores=1)


def test_roundtrip_and_env(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    assert cs.save({"smooth_mode": "on", "threads": 6, "play_all_outputs": False, "native_voice": False})
    cs.apply_env()
    assert os.environ["GROOVEBOX_SMOOTH"] == "1" and os.environ["GROOVEBOX_THREADS"] == "6"
    assert os.environ["GROOVEBOX_OUTPUT_SINGLE"] == "1" and os.environ["GROOVEBOX_NATIVE_VOICE"] == "off"
    assert "GROOVEBOX_AUDIO_BLOCKSIZE" not in os.environ
    cs.save(dict(cs.DEFAULTS, smooth_mode="off")); cs.apply_env()
    assert os.environ["GROOVEBOX_SMOOTH"] == "0" and "GROOVEBOX_OUTPUT_SINGLE" not in os.environ


def test_real_environment_wins(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    monkeypatch.setenv("GROOVEBOX_THREADS", "3"); cs._USER_ENV = None
    cs.save({"threads": 9}); cs.apply_env()
    assert os.environ["GROOVEBOX_THREADS"] == "3"


def test_stream_tuning_smooth(monkeypatch):
    import audio_os_backend as ab
    monkeypatch.delenv("GROOVEBOX_AUDIO_LATENCY", raising=False); monkeypatch.delenv("GROOVEBOX_AUDIO_BLOCKSIZE", raising=False)
    monkeypatch.setenv("GROOVEBOX_SMOOTH", "0"); assert ab.stream_tuning("live") == (512, "low")
    monkeypatch.setenv("GROOVEBOX_SMOOTH", "1"); assert ab.stream_tuning("live") == (1024, "high")
    monkeypatch.setenv("GROOVEBOX_AUDIO_BLOCKSIZE", "256"); assert ab.stream_tuning("live")[0] == 256


def test_describe_runs(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    assert any("Smooth mode" in l for l in cs.describe())


def test_wiring_markers():
    src = open("groovebox.py", encoding="utf-8").read()
    assert "_show_compat_dialog" in src and "btn_compat" in src and "_compat_start" not in src
    assert "compat_settings" in open("run_groovebox.py").read()


def test_startup_screen_and_quit_wiring():
    src = open("groovebox.py", encoding="utf-8").read()
    assert "force_chooser=True" in src and "force_chooser=False" in src
    assert "compat_btn" in src and "modal=True" in src and "_remember" not in src
    assert "Back to startup screen" in src and "Back to startup chooser" in src


def test_startup_cannot_be_skipped():
    src = open("groovebox.py", encoding="utf-8").read()
    assert 'GROOVEBOX_ALLOW_STARTUP_SKIP' in src and "Skip this screen" not in src


def test_video_settings_env_and_geometry(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    cs.save({"carrier_mix": 0.8, "video_tile_max": 0.4}); cs.apply_env()
    assert os.environ["GROOVEBOX_CARRIER_MIX"] == "0.8" and os.environ["GROOVEBOX_VIDEO_TILE_MAX"] == "0.4"
    cs.save({"carrier_mix": 9, "video_tile_max": 0.18}); cs.apply_env()
    assert cs.load()["carrier_mix"] == 1.0 and "GROOVEBOX_VIDEO_TILE_MAX" not in os.environ
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    import groovebox as g
    f = g.MathematiciansGrooveboxApp._instrument_video_tile_geometry
    monkeypatch.delenv("GROOVEBOX_VIDEO_TILE_MAX", raising=False)
    tw0, _ = f(1920, 1080, 1)
    monkeypatch.setenv("GROOVEBOX_VIDEO_TILE_MAX", "0.4")
    tw1, _ = f(1920, 1080, 1)
    assert tw0 <= int(1920 * 0.18) + 1 and tw1 > tw0 * 2 - 5


def test_ui_scale_auto_resolves_from_screen_size():
    import compat_settings as cs
    assert cs._clean({"ui_scale": "auto"})["ui_scale"] == 0 and cs._clean({"ui_scale": 0})["ui_scale"] == 0
    assert cs._clean({"ui_scale": 20})["ui_scale"] == 50           # explicit values still clamp
    assert [cs.auto_ui_scale(p) for p in ((1366, 768), (1920, 1080), (2560, 1440), (3840, 2160), (1024, 600), (800, 480))] \
        == [100, 100, 115, 175, 90, 80]
    assert cs.auto_ui_scale(None) in (80, 90, 100, 115, 140, 175)
    assert cs.env_for({"ui_scale": 0})["QT_SCALE_FACTOR"] in (None, "0.8", "0.9", "1.15", "1.4", "1.75")


def test_boot_menu_can_request_auto(tmp_path):
    import compat_settings as cs
    f = tmp_path / "cmdline"; f.write_text("quiet sos.ui_scale=auto sos.window_scale=90")
    assert cs.boot_overrides(str(f)) == {"ui_scale": 0, "window_scale": 90}
