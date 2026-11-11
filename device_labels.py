"""device_labels.py — GROOVEBOX_R32_DEVICE_LABELS_20261110

Readable audio-device listings: every selector shows what a device *is* and how it behaves,
not just its driver name.  label(row, "out"|"in") -> (text, tooltip).

  HDMI / DisplayPort   "TV / monitor speakers · follows the screen (sleeps with it)"
  USB                  "USB interface · own clock (best for recording)"
  Bluetooth            "Bluetooth · 150–250 ms delay (fine for playback, not for live keys)"
  PipeWire / Pulse     "shared mixer · several apps at once"
  direct ALSA hw:      "direct hardware · lowest latency · exclusive"
  plughw / dmix        "ALSA converted / shared"
  Groovebox Both       "HDMI + speakers together"
  monitor              "records what you hear (loopback)"
  digital mic (DMIC)   "built-in microphone array"
  headset / headphone, speaker, line / analog, S/PDIF / optical, virtual / null
"""
from __future__ import annotations

import re

_RULES = (
    (("groovebox both", "groovebox_both"), "HDMI + speakers together (Groovebox combined output)"),
    (("bluetooth", "bluez", "a2dp", "hfp", "airpods"), "Bluetooth · 150–250 ms delay (fine for playback, not for live keys)"),
    (("hdmi", "displayport", " dp ", "dp-", "display audio"), "TV / monitor speakers · follows the screen (sleeps with it)"),
    (("monitor of", ".monitor", "loopback", "stereo mix", "what u hear"), "records what you hear (loopback)"),
    (("dmic", "digital mic", "mic array", "microphone array"), "built-in microphone array"),
    (("headset",), "headset (mic + earphones)"),
    (("headphone", "earphone"), "headphones"),
    (("usb",), "USB interface · own clock (best for recording)"),
    (("spdif", "s/pdif", "iec958", "optical", "toslink"), "digital S/PDIF / optical"),
    (("speaker",), "built-in speakers"),
    (("line in", "line-in", "line out", "line-out", "analog", "analogue"), "analog jack"),
    (("webcam", "camera", "c920", "brio"), "camera microphone"),
    (("null", "dummy", "virtual", "auto_null"), "virtual / silent (no hardware)"),
)
_BACKEND = (
    (("pipewire",), "PipeWire shared mixer · several apps at once"),
    (("pulse",), "PulseAudio shared mixer · several apps at once"),
    (("dmix", "dsnoop"), "ALSA shared (dmix)"),
    (("plughw",), "ALSA with rate/format conversion"),
    (("hw:", "(hw"), "direct hardware · lowest latency · exclusive (other apps wait)"),
    (("wasapi",), "Windows WASAPI"), (("asio",), "ASIO · lowest latency (Windows)"),
    (("core audio", "coreaudio"), "macOS Core Audio"), (("mme",), "Windows MME (compatible, higher latency)"),
    (("directsound",), "Windows DirectSound"),
)


def _text(row):
    if isinstance(row, dict):
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        return " ".join(str(x) for x in (row.get("name"), row.get("description"), row.get("backend"),
                                          meta.get("hostapi_name"), meta.get("name")) if x)
    return str(row)


def hints(row):
    low = " " + _text(row).casefold() + " "
    out = []
    for keys, txt in _RULES:
        if any(k in low for k in keys):
            out.append(txt); break
    for keys, txt in _BACKEND:
        if any(k in low for k in keys):
            out.append(txt); break
    if isinstance(row, dict) and str(row.get("backend", "")).lower() == "alsa" and not any("ALSA" in h or "hardware" in h for h in out):
        out.append("direct ALSA")
    return out


def _caps(row, kind):
    if not isinstance(row, dict):
        return ""
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else row
    try:
        ch = int(meta.get("max_output_channels" if kind == "out" else "max_input_channels") or 0)
    except Exception:
        ch = 0
    try:
        sr = float(meta.get("default_samplerate") or 0)
    except Exception:
        sr = 0
    bits = []
    if ch:
        bits.append({1: "mono", 2: "stereo"}.get(ch, "%d ch" % ch))
    if sr:
        bits.append("%g kHz" % (sr / 1000.0))
    return " · ".join(bits)


def label(row, kind="out", base=None):
    base = str(base or (row.get("description") or row.get("name") if isinstance(row, dict) else row) or "Audio device")
    base = re.sub(r"\s+", " ", base).strip()
    h = hints(row)
    caps = _caps(row, kind)
    short = h[0] if h else ""
    text = base + ("  —  " + short if short and short.split(" ·")[0].casefold() not in base.casefold() else "")
    if caps:
        text += "  [" + caps + "]"
    if isinstance(row, dict) and row.get("default"):
        text = "★ " + text
    tip = "\n".join([base] + h + ([caps] if caps else []) +
                    (["not verified by PortAudio yet (it may still work)"] if isinstance(row, dict) and row.get("verified") is False else []))
    return text, tip
