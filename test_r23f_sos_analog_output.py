#!/usr/bin/env python3
"""Host-independent R23f physical fallback and current all-output contracts.

The ISO host must not supply this fixture's sound server, hardware state,
device cache, or mixer configuration. No live audio commands or route workers
are started here. The actual routing and PortAudio selection code is exercised.
"""
# R23F1_HOST_NUMPY_INDEPENDENT_TEST_20261002
# R23F2_ISOLATED_AUDIO_POLICY_FIXTURE_20261105
import os
import sys
import tempfile
import threading
import types
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main():
    # -S intentionally excludes runtime site-packages. Only this dtype token
    # is needed at import time; this fixture does not execute buffer/DSP code.
    try:
        import numpy  # noqa: F401
    except ModuleNotFoundError:
        stub = types.ModuleType("numpy")
        stub.float32 = "float32"
        sys.modules["numpy"] = stub

    import media_output_router as m
    import audio_os_backend as a

    commands = []
    batch_inputs = []
    rows = [
        {"name": "pipewire", "max_output_channels": 2, "max_input_channels": 2,
         "default_samplerate": 48000},
        {"name": "HDA Intel PCH: ALC3204 Analog (hw:0,0)",
         "max_output_channels": 2, "max_input_channels": 2,
         "default_samplerate": 48000},
        {"name": "HDA Intel PCH: HDMI 0 (hw:0,3)",
         "max_output_channels": 2, "max_input_channels": 0,
         "default_samplerate": 48000},
    ]
    ready = threading.Event()
    ready.set()
    route = {"ready": ready, "sink": "", "started": 0.0, "running": False}
    fake_sd = types.SimpleNamespace(default=types.SimpleNamespace(device=(-1, 0)))

    def fake_text(cmd, timeout=2.0):
        if cmd[:2] == ["aplay", "-l"]:
            return (
                "**** List of PLAYBACK Hardware Devices ****\n"
                "card 0: PCH [HDA Intel PCH], device 0: ALC3204 Analog [ALC3204 Analog]\n"
                "card 0: PCH [HDA Intel PCH], device 3: HDMI 0 [HDMI 0]\n"
            )
        if cmd[:2] == ["amixer", "-c"] and cmd[-1] == "scontrols":
            return (
                "Simple mixer control 'Master',0\n"
                "Simple mixer control 'Speaker',0\n"
                "Simple mixer control 'Auto-Mute Mode',0\n"
            )
        if cmd[:4] == ["pactl", "list", "short", "sinks"]:
            return "42\talsa_output.pci-hdmi-stereo\tmodule-alsa-card.c\ts16le\tRUNNING\n"
        return ""

    def fake_run(cmd, **kwargs):
        commands.append(list(cmd))
        batch_inputs.append(str(kwargs.get("input") or ""))
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    with tempfile.TemporaryDirectory(prefix="groovebox-audio-fixture-") as td, ExitStack() as stack:
        # These two state files normally reflect the live/installing machine.
        # Route only those reads to our empty fixture, not the host filesystem.
        def fixture_path(value, *parts):
            path = Path(value, *parts)
            if str(path) in {
                "/run/sos/audio-hardware.state",
                "/var/lib/groovebox/hardware-volume.state",
            }:
                return Path(td) / path.relative_to("/")
            return path

        stack.enter_context(patch.dict(os.environ, {"GROOVEBOX_SOS": "1"}))
        replacements = [
            (m, "Path", fixture_path),
            (m.shutil, "which", lambda name: f"/usr/bin/{name}" if name in
             {"aplay", "amixer", "alsactl", "alsaucm", "pactl"} else None),
            (m, "_run_text", fake_text),
            (m.subprocess, "run", fake_run),
            (m, "_real_alsa_playback_available", lambda: True),
            (m, "_real_pulse_sink_available", lambda: True),
            (m, "_drm_hdmi_connected", lambda: False),
            (m, "_ensure_all_pulse_outputs_sink", lambda: route["sink"]),
            (a, "HAS_SOUNDDEVICE", True),
            (a, "sd", fake_sd),
            (a, "_device_snapshot", lambda force=False: list(rows)),
            (a, "_ALL_ROUTE", route),
            # The route is supplied synchronously above. Do not start a worker
            # which can outlive the mocks and change the host's default sink.
            (a, "warm_all_outputs_route", lambda *args, **kwargs: None),
            (a, "_proven_speaker_pcm", lambda *args, **kwargs: ""),
        ]
        for obj, name, value in replacements:
            stack.enter_context(patch.object(obj, name, value))

        dev = m._preferred_alsa_output_device()
        assert dev == "alsa/plughw:CARD=PCH,DEV=0", dev
        args, env = m.player_routing(
            None, m.AudioTarget("", "System default", kind="default", backend="default"), False
        )
        assert "--ao=alsa" in args, args
        assert "--audio-device=alsa/plughw:CARD=PCH,DEV=0" in args, args
        assert "PULSE_SINK" not in env, env
        assert any(c[:4] == ["amixer", "-c", "0", "sset"] and "Speaker" in c
                   for c in commands), commands
        assert any("Auto-Mute Mode" in c and "Disabled" in c for c in commands), commands
        assert any(c and c[0] == "alsaucm" and "-b" in c for c in commands), commands
        assert any("set _verb HiFi" in text and "set _enadev Speaker" in text
                   for text in batch_inputs), batch_inputs

        # No aggregate route: exercise the real physical-device scoring fallback.
        idx = a.resolve_output_device_index()
        assert idx == 1, ("physical fallback", idx)

        # Current policy: when an aggregate route is ready, use the sound-server
        # row rather than requiring the legacy direct-hardware fallback.
        route["sink"] = "groovebox_all_outputs"
        idx = a.resolve_output_device_index()
        assert idx == 0, ("combined route", idx)
        rows.append({"name": "default", "max_output_channels": 2})
        idx = a.resolve_output_device_index()
        assert idx == 3, ("combined default route", idx)

    print("PASS: R23f sOS player default routes physical PCH analog")
    print("PASS: R23f ALSA/UCM speaker and Auto-Mute preparation")
    print("PASS: R23f PortAudio physical fallback without an aggregate route")
    print("PASS: current aggregate route selects PipeWire/default when available")
    print("PASS: audio fixture has no live sound-server workers or host state reads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
