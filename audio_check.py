"""🩺 Audio check — one-press audio diagnosis for sOS / desktop.

GROOVEBOX_R23R_AUDIO_CHECK_20261101

Collects the facts needed to explain "no sound" (cards, mixer levels and mute
states, PipeWire/Pulse sinks, hardware-volume state, PortAudio devices, the
device Groovebox resolves, recent audio errors) and plays a short, labelled
test tone through every playback path in turn so the user can say which ones
were audible. The report is written to <Groovebox data>/logs/.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path


def _q(cmd, t=4.0):
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=t)
        return ((cp.stdout or "") + (cp.stderr or "")).strip()
    except Exception as e:
        return f"<{e}>"


def _tone(sr=48000, secs=0.8, hz=660.0):
    import numpy as np
    t = np.arange(int(sr * secs)) / sr
    env = np.minimum(1.0, t / 0.02) * np.minimum(1.0, (secs - t) / 0.05)
    return (0.35 * np.sin(2 * np.pi * hz * t) * env).astype("float32")


def logs_dir() -> Path:
    try:
        import groovebox_paths
        d = Path(groovebox_paths.base_dir()) / "logs"
    except Exception:
        d = Path.home() / ".groovebox" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def system_report(host=None) -> str:
    out = []
    add = lambda title, body: out.append(f"\n===== {title} =====\n{body}")
    add("time", time.strftime("%Y-%m-%d %H:%M:%S"))
    if os.path.exists("/proc/asound/cards"):
        add("/proc/asound/cards", open("/proc/asound/cards").read())
    for tool, args in (("aplay", ["-l"]), ("aplay", ["-L"]), ("arecord", ["-l"])):
        if shutil.which(tool):
            add(f"{tool} {' '.join(args)}", _q([tool] + args))
    if shutil.which("amixer") and os.path.exists("/proc/asound/cards"):
        import re
        for c in re.findall(r"^\s*(\d+)\s+\[", open("/proc/asound/cards").read(), re.M):
            add(f"amixer -c {c} scontents", _q(["amixer", "-c", c, "scontents"]))
    for tool, args in (("pactl", ["info"]), ("pactl", ["list", "short", "sinks"]), ("pactl", ["list", "short", "sources"]),
                       ("wpctl", ["status"])):
        if shutil.which(tool):
            add(f"{tool} {' '.join(args)}", _q([tool] + args))
    for p in ("/var/lib/groovebox/hardware-volume.state", "/run/sos/audio-hardware.state", "/run/sos/memory.state"):
        if os.path.exists(p):
            add(p, open(p, errors="replace").read())
    helper = os.environ.get("GROOVEBOX_HARDWARE_VOLUME_HELPER", "/usr/bin/sos-hardware-volume")
    if os.path.exists(helper):
        add("sos-hardware-volume status", _q([helper, "status"]))
    try:
        from audio_os_backend import sd, HAS_SOUNDDEVICE, resolve_output_device_index
        if HAS_SOUNDDEVICE:
            add("PortAudio devices", str(sd.query_devices()))
            add("PortAudio default", repr(sd.default.device))
            pref = str(getattr(host, "_preferred_audio_output_name", "") or "") if host is not None else ""
            _ix = resolve_output_device_index(pref)
            try:
                _nm = sd.query_devices(_ix)["name"] if _ix is not None else None
            except Exception:
                _nm = None
            try:
                from audio_os_backend import _proven_speaker_pcm
                _pp = _proven_speaker_pcm(force=True)
            except Exception as _e:
                _pp = f"<{_e}>"
            add("Groovebox output choice",
                f"preferred_name={pref!r} → device index {_ix!r} ({_nm!r})\nproven physical speaker PCM (video path) = {_pp!r}")
        else:
            add("PortAudio", "sounddevice unavailable")
    except Exception as e:
        add("PortAudio", f"<{e}>")
    if host is not None:
        st = {k: repr(getattr(host, k, None)) for k in ("_audio_owner", "is_playing", "is_paused", "_audio_only_mode",
                                                         "master_volume", "audio_stream", "_pkp_poly_stream")}
        add("Groovebox transport state", "\n".join(f"{k} = {v}" for k, v in st.items()))
    try:
        el = logs_dir() / "errors.log"
        if el.is_file():
            add("errors.log (tail)", el.read_text(errors="replace")[-6000:])
    except Exception:
        pass
    return "\n".join(out)


def playback_tests(host=None, announce=lambda s: None):
    """Play a labelled tone through each path. Returns [(label, result)]."""
    import numpy as np
    results = []
    tone = _tone()

    def run(label, fn):
        announce(f"🔊 Now playing: {label}")
        try:
            fn(); results.append((label, "played without error"))
        except Exception as e:
            results.append((label, f"FAILED: {e}"))
        time.sleep(0.4)

    def via_groovebox(channels=1, block=1024, latency="high"):
        from audio_os_backend import sd, open_output_stream, prepare_output_buffer
        pref = str(getattr(host, "_preferred_audio_output_name", "") or "") if host is not None else ""
        buf, rate, _i = prepare_output_buffer(tone, 48000, preferred_name=pref)
        pos = [0]

        def cb(outdata, frames, _t, _s):
            n = min(frames, len(buf) - pos[0]); outdata.fill(0)
            if n > 0:
                for c in range(outdata.shape[1]):
                    outdata[:n, c] = buf[pos[0]:pos[0] + n]
                pos[0] += n
        st = open_output_stream(samplerate=int(rate), channels=int(channels), dtype="float32", callback=cb,
                                blocksize=int(block), latency=latency, preferred_name=pref, silent_fallback=False)
        st.start(); time.sleep(len(buf) / float(rate) + 0.3); st.stop(); st.close()

    def via_main_window_engine():
        """The exact voice engine the key notes / Trigger use inside the running main window."""
        if host is None or not hasattr(host, "_pkp_poly_submit"):
            raise RuntimeError("main window engine not available")
        sr = 48000
        host._pkp_poly_submit(tone.astype("float32"), sr)
        time.sleep(len(tone) / float(sr) + 0.4)
        st = getattr(host, "_pkp_poly_stream", None)
        if st is None or not bool(getattr(st, "active", False)):
            raise RuntimeError(f"audition stream not active after the note: {st!r}")

    def via_default():
        from audio_os_backend import sd
        sd.play(np.repeat(tone[:, None], 2, axis=1), 48000, blocking=True)

    run("1 · Groovebox device path (same as Trigger / Play)", via_groovebox)
    # GROOVEBOX_STREAM_PROFILES_20261102: the audio-file player, the key/trigger notes and
    # the arrangement open the device with different settings. Playing a tone with each
    # profile shows which setting a given machine cannot make audible.
    run("1b · File-player settings (stereo, 2048 frames, high latency)",
        lambda: via_groovebox(2, 2048, "high"))
    run("1c · Key/Trigger settings (mono, 512 frames, low latency)",
        lambda: via_groovebox(1, 512, "low"))
    run("1d · Main-window note engine (the stream key notes and Trigger use)", via_main_window_engine)
    run("2 · PortAudio system default device", via_default)
    aplay = shutil.which("aplay")
    if aplay:
        import re, tempfile, wave
        tmp = os.path.join(tempfile.gettempdir(), "groovebox_audio_check.wav")
        with wave.open(tmp, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000)
            w.writeframes(np.repeat((tone * 32767).astype("<i2")[:, None], 2, axis=1).tobytes())
        _rows = re.findall(r"^card (\d+): .*?, device (\d+): (.*)$", _q([aplay, "-l"]), re.M)
        cards = [(c, d) for c, d, _n in _rows]
        _names = {(c, d): n.strip() for c, d, n in _rows}
        for c, d in cards[:6]:
            dev = f"plughw:{c},{d}"
            _nm = _names.get((c, d), "")
            _kind = " [HDMI/DP - silent if no display is attached]" if any(t in _nm.casefold() for t in ("hdmi", "displayport", "dp ")) else ""
            def go(dev=dev):
                r = subprocess.run([aplay, "-q", "-D", dev, tmp], capture_output=True, text=True, timeout=10)
                if r.returncode != 0:
                    raise RuntimeError((r.stderr or "").strip()[:200] or f"rc={r.returncode}")
            run(f"3 · direct ALSA {dev} · {_nm}{_kind}", go)
    if shutil.which("paplay"):
        run("4 · PipeWire/Pulse default sink (paplay)",
            lambda: subprocess.run(["paplay", tmp], timeout=10, check=True) if aplay else None)
    return results


def run_check(host=None, announce=lambda s: None) -> str:
    """Full check; returns the report path."""
    report = system_report(host)
    tests = playback_tests(host, announce)
    body = report + "\n\n===== playback tests (which did you HEAR?) =====\n" + "\n".join(f"{l}: {r}" for l, r in tests)
    path = logs_dir() / f"audio-check-{time.strftime('%Y%m%d-%H%M%S')}.txt"
    path.write_text(body, encoding="utf-8")
    return str(path)
