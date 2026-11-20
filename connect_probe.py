"""GROOVEBOX_R124_CONNECT: one probe for every external connection (MIDI, OSC, audio servers, files, network).

``probe()`` returns [{"name", "kind", "ok", "detail", "fix"}]. Missing pieces are reported with the
one-line fix and never raise, so the Connect panel can grey them out instead of failing.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import socket
import sys
import tempfile


def _mod(name):
    return importlib.util.find_spec(name) is not None


def _pip(pkg):
    return f"{sys.executable} -m pip install {pkg}"


def probe(timeout=0.4):
    rows = []

    def add(name, kind, ok, detail, fix=""):
        rows.append({"name": name, "kind": kind, "ok": bool(ok), "detail": detail, "fix": "" if ok else fix})

    # MIDI
    if _mod("mido"):
        try:
            import mido
            ins, outs = mido.get_input_names(), mido.get_output_names()
            add("MIDI", "midi", True, f"{len(ins)} in · {len(outs)} out")
        except Exception as exc:
            add("MIDI", "midi", False, f"mido present, no backend ({exc.__class__.__name__})", _pip("python-rtmidi"))
    else:
        add("MIDI", "midi", False, "mido not installed", _pip("mido python-rtmidi"))
    # OSC (UDP socket bind on loopback)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        add("OSC (UDP)", "osc", True, f"loopback UDP available (test port {port})")
    except Exception as exc:
        add("OSC (UDP)", "osc", False, str(exc), "check firewall / network permissions")
    # Audio devices
    if _mod("sounddevice"):
        try:
            import sounddevice as sd
            devs = sd.query_devices(); n_out = sum(1 for d in devs if d.get("max_output_channels", 0) > 0)
            add("Audio devices", "audio", n_out > 0, f"{n_out} output device(s)", "connect an output device or start PipeWire")
        except Exception as exc:
            add("Audio devices", "audio", False, f"PortAudio: {exc.__class__.__name__}", "install libportaudio2 / start PipeWire")
    else:
        add("Audio devices", "audio", False, "sounddevice not installed", _pip("sounddevice"))
    # Audio servers
    pw = bool(shutil.which("pw-cli") or shutil.which("pipewire"))
    add("PipeWire", "server", pw, "pw-cli found" if pw else "not found", "install pipewire pipewire-pulse wireplumber")
    jk = bool(shutil.which("jack_lsp") or shutil.which("pw-jack"))
    add("JACK", "server", jk, "jack tools found" if jk else "not found", "install pipewire-jack (or jackd2)")
    # Files
    try:
        with tempfile.NamedTemporaryFile(prefix="gb-connect-", delete=True) as fh:
            fh.write(b"ok")
        add("Files (temp)", "files", True, tempfile.gettempdir())
    except Exception as exc:
        add("Files (temp)", "files", False, str(exc), "free disk space / fix TMPDIR permissions")
    home = os.path.expanduser("~")
    add("Files (home)", "files", os.access(home, os.W_OK), home, "home directory is read-only")
    ff = shutil.which("ffmpeg")
    add("ffmpeg (video/stream)", "files", bool(ff), ff or "not found", "install ffmpeg")
    # Network
    try:
        socket.getaddrinfo("localhost", 80)
        add("Network (local)", "network", True, "resolver OK")
    except Exception as exc:
        add("Network (local)", "network", False, str(exc), "check /etc/hosts")
    try:
        c = socket.create_connection(("1.1.1.1", 443), timeout=timeout); c.close()
        add("Network (internet)", "network", True, "reachable")
    except Exception:
        add("Network (internet)", "network", False, "offline", "connect Wi-Fi/Ethernet (Settings ▸ Network)")
    # Language runtimes used by external app support
    for name, exe, fix in (("Julia", "julia", "ISO ships /opt/sos/julia; on desktop install juliaup"),
                           ("Go", "go", "install golang"), ("C compiler", "cc", "install build-essential / gcc")):
        p = shutil.which(exe)
        add(name, "runtime", bool(p), p or "not found", fix)
    add("Lua (lupa)", "runtime", _mod("lupa"), "lupa" if _mod("lupa") else "not installed", _pip("lupa"))
    return rows


def text(rows=None):
    rows = rows if rows is not None else probe()
    return "\n".join(f"{'✓' if r['ok'] else '✗'} {r['name']:<22} {r['detail']}" + (f"   → {r['fix']}" if r["fix"] else "")
                     for r in rows)
