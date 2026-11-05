"""Hardware format choices labelled by device AND interpretation.

GROOVEBOX_R23R_HARDWARE_FORMATS_20261101

Instead of an often-empty list of device names, each option is a concrete,
validated format the hardware will actually accept, labelled with both the
device and how Groovebox will use it, e.g.

    48 kHz · 24-bit · stereo — HDA Intel PCH: ALC3204 (ALSA) · PCM playback
    1280×720 @ 30 fps · MJPEG — Integrated Webcam · camera capture

When the software is not sure, the first option is always the safe
"All devices / system default" choice (Groovebox resamples the hardware copy),
so multi-mode / multi-device setups can be compared by experiment.

Everything here may block on audio servers or camera drivers: call it from a
worker thread. sounddevice and Qt Multimedia are optional.
"""
from __future__ import annotations

RATES = (44100, 48000, 88200, 96000, 192000)
DTYPES = (("int16", "16-bit"), ("int24", "24-bit"), ("float32", "32-bit float"))
CHANNELS = ((1, "mono"), (2, "stereo"))
MAX_DEVICES = 24


def _default_option(kind: str) -> dict:
    return {"kind": kind, "device": None, "samplerate": 48000, "dtype": "float32", "channels": 2,
            "label": f"48 kHz · 32-bit float · stereo — All devices (system default) · "
                     f"{'PCM playback' if kind == 'output' else 'PCM capture'}, Groovebox resamples the hardware copy",
            "interpretation": "system default"}


def audio_options(kind: str = "output", max_per_device: int = 10) -> list:
    """Validated (device, rate, depth, channels) choices for audio output or input."""
    out = [_default_option(kind)]
    try:
        from audio_os_backend import sd  # build policy: PortAudio only via audio_os_backend
    except Exception:
        return out
    if sd is None:
        return out
    try:
        devices = list(sd.query_devices())
        apis = [a.get("name", "") for a in sd.query_hostapis()]
    except Exception:
        return out
    check = sd.check_output_settings if kind == "output" else sd.check_input_settings
    key = "max_output_channels" if kind == "output" else "max_input_channels"
    role = "PCM playback" if kind == "output" else "PCM capture"
    for idx, dev in enumerate(devices[:MAX_DEVICES]):
        maxch = int(dev.get(key, 0) or 0)
        if maxch <= 0:
            continue
        api = apis[dev.get("hostapi", 0)] if 0 <= int(dev.get("hostapi", 0)) < len(apis) else ""
        name = f"{dev.get('name', 'device')}" + (f" ({api})" if api else "")
        default_sr = int(round(float(dev.get("default_samplerate", 48000) or 48000)))
        n = 0
        rates = sorted(set(RATES) | {default_sr}, key=lambda r: (r != default_sr, r))
        for sr in rates:
            for ch, chname in CHANNELS:
                if ch > maxch:
                    continue
                for dt, dtname in DTYPES:
                    if n >= max_per_device:
                        break
                    try:
                        check(device=idx, samplerate=sr, channels=ch, dtype=dt)
                    except Exception:
                        continue
                    native = " · device default rate" if sr == default_sr else ""
                    out.append({"kind": kind, "device": idx, "device_name": dev.get("name", ""), "hostapi": api,
                                "samplerate": sr, "dtype": dt, "channels": ch,
                                "label": f"{sr / 1000:g} kHz · {dtname} · {chname} — {name} · {role}{native}",
                                "interpretation": role})
                    n += 1
    return out


def camera_options(max_per_camera: int = 12) -> list:
    """(camera, resolution, frame rate, pixel format) choices from Qt Multimedia."""
    out = [{"kind": "camera", "device": None, "label": "Default camera · its preferred format · camera capture"}]
    try:
        from PyQt6.QtMultimedia import QMediaDevices
    except Exception:
        return out
    try:
        cams = list(QMediaDevices.videoInputs())
    except Exception:
        return out
    for cam in cams:
        seen = set()
        fmts = sorted(cam.videoFormats(), key=lambda f: (-(f.resolution().width() * f.resolution().height()), -f.maxFrameRate()))
        for f in fmts:
            res = f.resolution()
            try:
                pix = f.pixelFormat().name.replace("Format_", "")
            except Exception:
                pix = "?"
            key = (res.width(), res.height(), round(f.maxFrameRate()), pix)
            if key in seen:
                continue
            seen.add(key)
            out.append({"kind": "camera", "device": bytes(cam.id()).decode("utf-8", "replace"),
                        "device_name": cam.description(), "width": res.width(), "height": res.height(),
                        "fps": float(f.maxFrameRate()), "pixel_format": pix,
                        "label": f"{res.width()}×{res.height()} @ {f.maxFrameRate():g} fps · {pix} — {cam.description()} · camera capture"})
            if len(seen) >= max_per_camera:
                break
    return out
