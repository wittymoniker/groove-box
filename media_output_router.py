# GROOVEBOX_V35_22ZZ_R23R_DISCOVERED_ENDPOINTS_UCM_DMIC_ASPM_20261005
# GROOVEBOX_V35_22ZZ_R23P_BOOT_HARDWARE_INIT_20261004
# GROOVEBOX_V35_22ZZ_R23M_UCM_SPEAKER_PCM_SDMMC_PLATFORM_20261004
# GROOVEBOX_V35_22ZZ_R23K_RUNTIME_AUDIO_MIC_BROWSER_SD_20261003
# GROOVEBOX_V35_22ZZ_R23J_UNIVERSAL_AUDIO_MIC_WATCHDOG_20261003
# GROOVEBOX_V35_22ZZ_R23H_LINKED_HARDWARE_VOLUME_20261002
#!/usr/bin/env python3
# R14_MEDIA_PLAYBACK_RESILIENCE: historical compatibility marker.
# GROOVEBOX_V35_22ZZ_R23F_SOS_ANALOG_OUTPUT_PREP_20261002
# GROOVEBOX_V35_22ZZ_R23D_PHYSICAL_PLAYBACK_CLOCK_20261001
# GROOVEBOX_V35_22ZZ_R23_PLAYBACK_OUTPUT_RECOVERY_20261001
# GROOVEBOX_V35_22ZZ_R19_STREAMING_HARDWARE_PLAYER_20260930
"""Media Hub output routing for local displays/audio and LAN/Wi-Fi TV clients.

The router deliberately keeps hardware-specific work optional:
- X11/Wayland display discovery is advisory; mpv receives a screen index when possible.
- PulseAudio/PipeWire sinks are selected per subprocess with PULSE_SINK, so Groovebox
  does not have to change the machine-wide default output.
- A tiny LAN HTTP server exposes a browser TV player, current media, playlist media,
  and explicitly shared game packages. It never executes received content.
- Optional Chromecast handoff uses the external `catt` command when installed.
"""
from __future__ import annotations
# GROOVEBOX_V35_22ZZ_R23N_HWUCM_CAPTURE_MSI_READER_20261004

import html
import json
import mimetypes
import os
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
import hashlib
import threading
from dataclasses import dataclass, asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from groovebox_media_tools import resolve_local_tool
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, quote, unquote, urlparse


@dataclass
class DisplayTarget:
    name: str
    connected: bool = True
    primary: bool = False
    geometry: str = ""
    index: int = 0
    backend: str = "unknown"


@dataclass
class AudioTarget:
    name: str
    description: str
    state: str = ""
    kind: str = "audio"
    backend: str = "pulse"


def _run_group(args, timeout=2.0, text=True, stdin_data=None):
    """Run a short device command in its own process group; on timeout kill the whole group.

    subprocess.run(timeout=) kills only the direct child, so a wedged helper's own children
    (alsa/pipewire tools) survive and pile up. Returns (returncode, stdout, stderr); rc=None on timeout.
    """
    import signal as _sig
    p = subprocess.Popen(list(args), stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=text, start_new_session=True)
    try:
        out, err = p.communicate(stdin_data, timeout=timeout)
        return p.returncode, out or "", err or ""
    except subprocess.TimeoutExpired:
        try: os.killpg(p.pid, _sig.SIGKILL)
        except Exception:
            try: p.kill()
            except Exception: pass
        try: p.communicate(timeout=1.0)
        except Exception: pass
        return None, "", ""


def _run_text(cmd: Sequence[str], timeout: float = 2.0) -> str:
    try:
        return _run_group(cmd, timeout=timeout)[1]
    except Exception:
        return ""


def detect_displays() -> List[DisplayTarget]:
    out: List[DisplayTarget] = []
    if shutil.which("xrandr"):
        txt = _run_text(["xrandr", "--query"])
        for line in txt.splitlines():
            m = re.match(r"^(\S+)\s+connected(?:\s+(primary))?(?:\s+(\d+x\d+\+[-\d]+\+[-\d]+))?", line)
            if m: out.append(DisplayTarget(m.group(1),True,bool(m.group(2)),m.group(3) or "",len(out),"xrandr"))
    if not out and shutil.which("wlr-randr"):
        txt=_run_text(["wlr-randr"]); current=None
        for line in txt.splitlines():
            if line and not line[0].isspace():
                name=line.split()[0]; current=DisplayTarget(name=name,index=len(out),backend="wlr-randr"); out.append(current)
            elif current and "current" in line.lower(): current.geometry=line.strip()
    # Bare-metal sOS fallback: DRM connector sysfs remains available even when
    # xrandr/wlr-randr is absent. This is the important Latitude 3510 HDMI path.
    if not out:
        drm=Path("/sys/class/drm")
        if drm.is_dir():
            for status in sorted(drm.glob("card*-*/status")):
                try:
                    if status.read_text(errors="ignore").strip() != "connected": continue
                    connector=status.parent.name.split("-",1)[1] if "-" in status.parent.name else status.parent.name
                    modes=status.parent/"modes"; geometry=""
                    if modes.is_file(): geometry=(modes.read_text(errors="ignore").splitlines() or [""])[0]
                    primary=connector.lower().startswith(("edp","lvds"))
                    out.append(DisplayTarget(connector,True,primary,geometry,len(out),"drm-sysfs"))
                except Exception: pass
    if not out: out.append(DisplayTarget("Default display",True,True,"",0,"default"))
    return out


def detect_audio_targets() -> List[AudioTarget]:
    out: List[AudioTarget] = [AudioTarget("", "System default", kind="default", backend="default")]
    seen=set()
    if shutil.which("pactl"):
        txt=_run_text(["pactl","list","short","sinks"])
        for line in txt.splitlines():
            parts=line.split("\t") if "\t" in line else line.split()
            if len(parts)<2: continue
            name=parts[1]; state=parts[-1] if parts else ""; low=name.lower()
            if any(tok in low for tok in ("auto_null","dummy","null")):
                continue
            if str(state).upper() in ("FAILED", "UNAVAILABLE", "INVALID"):
                continue
            kind="bluetooth" if ("bluez" in low or "bluetooth" in low) else ("hdmi" if "hdmi" in low else ("usb" if "usb" in low else "audio"))
            out.append(AudioTarget(name,name,state=state,kind=kind,backend="pulse")); seen.add(name)
    # ALSA fallback is essential on a minimal appliance before PipeWire/Pulse
    # compatibility has published sinks. Expose *real playback* endpoints, not
    # only HDMI.  In particular the Latitude internal speaker can be available
    # through ALSA while pactl still reports only auto_null during session start.
    if shutil.which("aplay"):
        txt=_run_text(["aplay","-L"],timeout=4.0)
        alsa_names=[]
        for line in txt.splitlines():
            if not line or line[0].isspace():
                continue
            name=line.strip(); low=name.lower()
            if not name or any(tok in low for tok in ("null", "lavrate", "samplerate", "speexrate", "jack")):
                continue
            # Avoid flooding the combo with every plugin alias while retaining
            # default/internal/USB/HDMI routes that mpv can open directly.
            if (low == "default" or low.startswith(("sysdefault", "front:", "plughw:", "hw:", "hdmi:", "iec958:"))
                    or any(tok in low for tok in ("sof", "hda", "pch", "usb", "speaker"))):
                alsa_names.append(name)
        # Put ALSA default first when Pulse is not usable.
        alsa_names.sort(key=lambda n: (0 if n.lower()=="default" else 1, n.casefold()))
        for name in alsa_names:
            key="alsa/"+name
            if key in seen or name in seen:
                continue
            low=name.lower(); kind="hdmi" if any(t in low for t in ("hdmi","displayport","iec958")) else ("usb" if "usb" in low else "audio")
            label = name
            if kind == "hdmi":
                label = "HDMI / DisplayPort · " + name
            out.append(AudioTarget(key,label,kind=kind,backend="alsa")); seen.add(key)

        # Some minimal images expose HDMI PCMs in `aplay -l` but omit friendly
        # aliases from `aplay -L`. Add explicit plughw routes so HDMI audio is
        # still selectable in the Player's output menu. Keep this discovery
        # separate from the preferred default: internal speakers remain default.
        hw_txt=_run_text(["aplay","-l"],timeout=1.5)
        rx=re.compile(r"^card\s+(\d+):\s*([^\s\[]+).*?device\s+(\d+):\s*(.*)$",re.I)
        for raw in hw_txt.splitlines():
            m=rx.search(raw.strip())
            if not m:
                continue
            card_num,card_id,dev_num,desc=m.groups()
            low=(card_id+" "+desc).casefold()
            if not any(t in low for t in ("hdmi","displayport","dp audio")):
                continue
            key=f"alsa/plughw:CARD={card_id},DEV={dev_num}"
            if key in seen:
                continue
            label=f"HDMI / DisplayPort · {desc.strip() or card_id} (card {card_num}, device {dev_num})"
            out.append(AudioTarget(key,label,kind="hdmi",backend="alsa")); seen.add(key)
    # Kernel PCM inventory is often more stable than the user-space alias list
    # during HDMI hot-plug/profile changes. Preserve explicit selectable HDMI
    # outputs even if `aplay -L` temporarily omits the alias.
    try:
        pcm_file=Path('/proc/asound/pcm')
        if pcm_file.is_file():
            for raw in pcm_file.read_text(errors='ignore').splitlines():
                m=re.match(r'^\s*(\d+)-(\d+)\s*:\s*(.*?)\s*:\s*playback\s+(\d+)\s*$',raw,re.I)
                if not m: continue
                card_num,dev_num,desc,_channels=m.groups()
                low=desc.casefold()
                if not any(t in low for t in ('hdmi','displayport','dp audio')): continue
                card_id=''
                for id_path in (Path(f'/proc/asound/card{card_num}/id'), Path(f'/sys/class/sound/card{card_num}/id')):
                    try:
                        card_id=id_path.read_text(errors='ignore').strip()
                        if card_id: break
                    except Exception: pass
                card_id=card_id or str(card_num)
                key=f'alsa/plughw:CARD={card_id},DEV={dev_num}'
                if key in seen: continue
                out.append(AudioTarget(key,f'HDMI / DisplayPort · {desc.strip()} (card {card_num}, device {dev_num})',kind='hdmi',backend='alsa'))
                seen.add(key)
    except Exception:
        pass
    # R28.4.9-HW: when a DRM HDMI/DP connector is connected, surface HDMI
    # targets first so the Player default selection is not stuck on silent
    # internal routes while HDMI is the active display.
    if _drm_hdmi_connected() and out:
        hdmi = [t for t in out if getattr(t, "kind", "") == "hdmi"]
        other = [t for t in out if getattr(t, "kind", "") != "hdmi"]
        if hdmi:
            out = hdmi + other
    return out



def _drm_hdmi_connected() -> bool:
    """True when a DRM connector named HDMI/DP reports status=connected."""
    drm = Path("/sys/class/drm")
    if not drm.is_dir():
        return False
    try:
        for conn in drm.iterdir():
            name = conn.name.lower()
            if not any(t in name for t in ("hdmi", "dp-", "displayport")):
                continue
            status = conn / "status"
            if status.is_file() and status.read_text(encoding="utf-8", errors="ignore").strip().lower() == "connected":
                return True
    except Exception:
        return False
    return False


def _running_on_sos() -> bool:
    """True inside the Groovebox/sOS appliance (or its explicit test mode)."""
    return (os.environ.get("GROOVEBOX_SOS", "").strip() == "1"
            or Path("/run/sos").is_dir()
            or Path("/opt/sos").is_dir())


def _alsa_card_for_device(device: str) -> Tuple[str, str]:
    """Return (numeric_card, card_id) for an mpv/ALSA device string."""
    raw=str(device or "")
    if raw.startswith("alsa/"):
        raw=raw[5:]
    m=re.search(r"(?:^|,)CARD=([^,]+)", raw, re.I)
    wanted=(m.group(1) if m else "").strip()
    txt=_run_text(["aplay","-l"], timeout=1.2) if shutil.which("aplay") else ""
    rows=[]
    rx=re.compile(r"^card\s+(\d+):\s*([^\s\[]+)", re.I)
    for line in txt.splitlines():
        mm=rx.search(line.strip())
        if mm:
            rows.append((mm.group(1),mm.group(2)))
    if wanted:
        if wanted.isdigit():
            for num,cid in rows:
                if num==wanted:
                    return num,cid
            return wanted,wanted
        for num,cid in rows:
            if cid.casefold()==wanted.casefold():
                return num,cid
    if rows:
        return rows[0]
    return "", wanted



def _ucm_card_candidates(card_num: str, card_id: str) -> List[str]:
    """Return UCM card selectors, preferring the hardware namespace.

    sof-hda-dsp commonly reports ALSA id ``sofhdadsp`` while UCM's canonical
    profile lives behind the hardware card selector.  ``alsaucm -c sofhdadsp``
    may therefore miss the real conf.d profile even though ``-c hw:0`` works.
    """
    out=[]
    num=str(card_num or '').strip(); cid=str(card_id or '').strip()
    for ident in ((f"hw:{num}" if num else ''), (f"hw:CARD={cid}" if cid else ''), cid, num):
        if ident and ident not in out:
            out.append(ident)
    return out



def _ucm_speaker_pcm(card_num: str, card_id: str) -> str:
    """Return UCM's exact HiFi Speaker PlaybackPCM as an mpv ALSA target."""
    if not shutil.which("alsaucm"):
        return ""
    for ident in _ucm_card_candidates(card_num, card_id):
        try:
            cp=subprocess.run(["alsaucm","-c",ident,"get","PlaybackPCM/Speaker/HiFi"],
                              capture_output=True,text=True,timeout=1.5,check=False)
            if cp.returncode != 0:
                continue
            lines=[x.strip().strip('"\'') for x in (cp.stdout or '').splitlines() if x.strip()]
            for pcm in reversed(lines):
                low=pcm.casefold()
                if low.startswith(("hw:","plughw:","plug:","sysdefault:","front:","default")):
                    return "alsa/"+pcm
        except Exception:
            pass
    return ""


def _activate_ucm_speaker(card_num: str, card_id: str) -> bool:
    """Activate HiFi + Speaker in one UCM process so device context is retained."""
    if not shutil.which("alsaucm"):
        return False
    batch="set _verb HiFi\nset _enadev Speaker\n"
    for ident in _ucm_card_candidates(card_num, card_id):
        try:
            cp=subprocess.run(["alsaucm","-c",ident,"-b","-"], input=batch,
                              text=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                              timeout=2.0,check=False)
            if cp.returncode == 0:
                return True
        except Exception:
            pass
    return False


def _prepare_physical_alsa_output(device: str) -> bool:
    """Prepare an ALSA output without resetting the user's live mixer state.

    R28.4.18: do not let a stale UI/helper mute flag silence playback.

    The boot audio service performs its single alsactl initialization. Re-running
    ``alsactl init`` here on every media/synth preview used to jump the slider back
    to stale levels and could leave the selected speakers silent. A route change
    may activate UCM once, while repeated playback only reapplies the persisted
    desired playback level/unmute state. Capture controls are never changed.
    """
    if not device or not shutil.which("aplay"):
        return False
    card_num, card_id = _alsa_card_for_device(device)
    if not card_num and not card_id:
        return False
    card = card_num or card_id
    device_low = str(device).casefold()
    card_desc = ""
    requested_dev = re.search(r"(?:^|,)DEV=(\d+)", str(device), re.I)
    requested_dev = requested_dev.group(1) if requested_dev else ""
    try:
        for raw in _run_text(["aplay", "-l"], timeout=1.2).splitlines():
            line = raw.strip()
            if not re.search(rf"^card\s+{re.escape(str(card_num))}:", line, re.I):
                continue
            dm = re.search(r"device\s+(\d+):\s*(.*)$", line, re.I)
            if requested_dev and (not dm or dm.group(1) != requested_dev):
                continue
            card_desc = line.casefold()
            if requested_dev or card_desc:
                break
    except Exception:
        pass
    is_digital = any(t in (device_low + " " + card_desc) for t in ("hdmi", "displayport", "dp audio", "iec958", "spdif"))

    def qrun(cmd, timeout=1.2):
        try:
            return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  timeout=timeout, check=False).returncode == 0
        except Exception:
            return False

    # Read intended user-facing volume: the state file is the desired user setting.
    # not proof that a temporarily reset physical mixer already matches it.
    # 72% is only the first-launch fallback; explicit saved 0% is valid.
    pct = 72
    try:
        state = Path("/var/lib/groovebox/hardware-volume.state")
        if state.exists():
            for line in state.read_text(errors="replace").splitlines():
                if line.startswith("volume="):
                    raw_pct = int(float(line.split("=", 1)[1].strip()))
                    if 0 <= raw_pct <= 100:
                        pct = raw_pct
                    break
    except Exception:
        pass

    if shutil.which("amixer"):
        controls = _run_text(["amixer", "-c", str(card), "scontrols"], timeout=1.2)
        names = re.findall(r"Simple mixer control '([^']+)'", controls)
    else:
        names = []

    if is_digital:
        # HDMI/DP is digital; never activate analog speaker UCM on that card.
        # Many IEC958/HDMI controls are SWITCHES (on/off), not volume percentages.
        # Setting "72%" on a switch often fails silently and leaves HDMI muted or
        # at an effectively silent digital default — the "video plays, audio
        # missing/insanely quiet" symptom on Latitude + external displays.
        for name in names:
            low = name.casefold()
            if any(t in low for t in ("capture", "mic", "input")):
                continue
            if not any(t in low for t in ("hdmi", "iec958", "spdif", "pcm", "master", "digital", "playback")):
                continue
            # Switch-style first
            qrun(["amixer", "-c", str(card), "sset", name, "on"], 1.0)
            qrun(["amixer", "-c", str(card), "sset", name, "unmute"], 1.0)
            # Volume-style (ignore failure when control is a pure switch)
            qrun(["amixer", "-c", str(card), "sset", name, f"{pct}%"], 1.0)
            qrun(["amixer", "-c", str(card), "sset", name, "100%"], 1.0)
        # Also raise the matching PipeWire/Pulse sink so desktop stacks are not quiet.
        try:
            if shutil.which("pactl"):
                sinks = _run_text(["pactl", "list", "short", "sinks"], timeout=1.2)
                for line in sinks.splitlines():
                    cols = line.split("	")
                    if len(cols) < 2:
                        continue
                    sink = cols[1]
                    slow = sink.casefold()
                    if any(t in slow for t in ("hdmi", "displayport", "dp", "iec958")):
                        subprocess.run(
                            [shutil.which("pactl") or "pactl", "set-sink-mute", sink, "0"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=1.0, check=False,
                        )
                        subprocess.run(
                            [shutil.which("pactl") or "pactl", "set-sink-volume", sink, f"{max(pct, 90)}%"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=1.0, check=False,
                        )
                        # Prefer this sink as default while HDMI is the selected route
                        subprocess.run(
                            [shutil.which("pactl") or "pactl", "set-default-sink", sink],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=1.0, check=False,
                        )
        except Exception:
            pass
        return True

    # Only activate UCM on a route different from the audio boot selector. This
    # is NOT alsactl init: it does not replay the global mixer defaults.
    route_matches = False
    try:
        state = Path("/run/sos/audio-hardware.state")
        if state.exists():
            saved = {}
            for line in state.read_text(errors="replace").splitlines():
                if "=" in line:
                    k, v = line.split("=", 1); saved[k.strip()] = v.strip()
            active_card = str(saved.get("card", ""))
            active_id = str(saved.get("card_id", saved.get("id", "")))
            route_matches = active_card == str(card_num) or (active_id and active_id.casefold() == str(card_id).casefold())
    except Exception:
        pass
    if not route_matches:
        _activate_ucm_speaker(card_num, card_id)
        qrun(["amixer", "-c", str(card), "cset", "name='Speaker Playback Switch'", "on"], 1.0)
        for name in names:
            if "auto-mute" in name.casefold():
                qrun(["amixer", "-c", str(card), "sset", name, "Disabled"], 1.0)

    # Reassert desired output level and unmute playback-only controls every time.
    for name in names:
        low = name.casefold()
        if any(tok in low for tok in ("capture", "mic", "input")):
            continue
        if "auto-mute" in low:
            qrun(["amixer", "-c", str(card), "sset", name, "Disabled"], 1.0)
            continue
        if any(tok in low for tok in ("master", "speaker", "pcm", "dac", "front", "headphone", "playback")) \
                and not any(tok in low for tok in ("capture", "mic", "input")):
            qrun(["amixer", "-c", str(card), "sset", name, f"{pct}%"], 1.0)
            qrun(["amixer", "-c", str(card), "sset", name, "unmute"], 1.0)
    return True


def _real_pulse_sink_available() -> bool:
    if not shutil.which("pactl"):
        return False
    txt=_run_text(["pactl","list","short","sinks"],timeout=0.7)
    for line in txt.splitlines():
        low=line.lower()
        if line.strip() and not any(tok in low for tok in ("auto_null","dummy")):
            return True
    return False

def _real_alsa_playback_available() -> bool:
    """True when ALSA exposes at least one physical playback PCM."""
    if not shutil.which("aplay"):
        return False
    txt=_run_text(["aplay","-l"],timeout=1.2)
    low=txt.lower()
    return ("card " in low and "device " in low and "no soundcards found" not in low)

def _physical_alsa_playback_devices() -> List[str]:
    """Return ranked direct ALSA PCMs, with the hardware-volume card first.

    R23k keeps playback and the Dell hardware-volume helper on the same card.
    This matters when HDMI and the ALC3204/PCH codec coexist: a perfectly valid
    HDMI PCM can advance a playback clock while the laptop speakers remain silent.
    """
    boot_pcm=""
    try:
        bs=Path("/run/sos/audio-hardware.state")
        if bs.is_file():
            for line in bs.read_text(errors="replace").splitlines():
                if line.startswith("speaker_pcm="):
                    boot_pcm=line.split("=",1)[1].strip(); break
    except Exception:
        boot_pcm=""
    if not _real_alsa_playback_available():
        return (["alsa/"+boot_pcm] if boot_pcm and not boot_pcm.startswith("alsa/") else ([boot_pcm] if boot_pcm else []))
    txt=_run_text(["aplay","-l"],timeout=1.5)
    persisted_card=""
    try:
        state=Path("/var/lib/groovebox/hardware-volume.state")
        if state.is_file():
            for line in state.read_text(errors="replace").splitlines():
                if line.startswith("card="):
                    persisted_card=line.split("=",1)[1].strip()
                    break
    except Exception:
        persisted_card=""
    candidates=[]
    rx=re.compile(r"^card\s+(\d+):\s*([^\s\[]+).*?device\s+(\d+):\s*(.*)$", re.I)
    for raw in txt.splitlines():
        m=rx.search(raw.strip())
        if not m:
            continue
        card_i, card_id, dev_i, desc=m.groups()
        low=(card_id+" "+desc).casefold()
        score=0
        if persisted_card and (persisted_card == card_i or persisted_card.casefold() == card_id.casefold()):
            score += 1000
        if any(t in low for t in ("analog","speaker","pch","sof","hda","alc","realtek")):
            score += 220
        if any(t in low for t in ("hdmi","displayport","spdif","iec958")):
            # If an external display is connected, its HDMI/DP PCM must be the
            # default route for all media sources (including files on microSD).
            # Otherwise preserve the historical internal-speaker-first policy.
            score += 700 if _drm_hdmi_connected() else -500
        if "usb" in low:
            score += 30
        try:
            score -= int(card_i)*2 + int(dev_i)
        except Exception:
            pass
        candidates.append((score, card_i, card_id, dev_i))
    candidates.sort(reverse=True)
    # Do not pin the route to a boot-time PCM before inspecting current hardware.
    # Boot state can be stale (e.g. HDMI DEV=3 recorded at boot while the laptop
    # speakers are the usable endpoint now). Ranked live ALSA enumeration wins.
    out=[]
    seen_cards=set()
    for _score, card_i, card_id, dev_i in candidates:
        card_key=(card_i,card_id)
        if card_key not in seen_cards:
            seen_cards.add(card_key)
            ucm_pcm=_ucm_speaker_pcm(card_i,card_id)
            if ucm_pcm and ucm_pcm not in out:
                out.append(ucm_pcm)
        # Generic direct aliases remain fallbacks after UCM's exact Speaker PCM.
        for dev in (f"alsa/plughw:CARD={card_id},DEV={dev_i}",
                    f"alsa/plughw:CARD={card_i},DEV={dev_i}"):
            if dev not in out:
                out.append(dev)
    # Keep the boot-detected PCM only as a fallback if live discovery could not
    # produce any physical route. Never let a stale boot entry outrank live data.
    if boot_pcm:
        b=boot_pcm if boot_pcm.startswith("alsa/") else "alsa/"+boot_pcm
        if b not in out: out.append(b)
    return out

def _physical_alsa_playback_device() -> str:
    devices=_physical_alsa_playback_devices()
    return devices[0] if devices else ""

def _preferred_alsa_output_device() -> str:
    """Return a real ALSA output, preferring connected HDMI/DP when present.

    A connected external display changes the intended listening endpoint. The
    ranked physical list then puts its digital PCM ahead of internal analog, so
    audio-only files, video audio, and media loaded from microSD share the route.
    """
    direct=_physical_alsa_playback_device()
    if direct:
        return direct
    if not _real_alsa_playback_available():
        return ""
    txt=_run_text(["aplay","-L"],timeout=2.0)
    names=[line.strip() for line in txt.splitlines() if line and not line[0].isspace()]
    clean=[n for n in names if not any(t in n.casefold() for t in ("null","lavrate","samplerate","speexrate","jack"))]
    # plughw first: it is direct ALSA with conversion. sysdefault is only a later
    # compatibility fallback because some distributions wire it back to Pulse.
    for prefixes in (("plughw:",), ("front:",), ("hw:",), ("sysdefault:",), ("default",)):
        for name in clean:
            low=name.casefold()
            if any(low == pre or low.startswith(pre) for pre in prefixes):
                return "alsa/"+name
    return "alsa/default"

# GROOVEBOX_R23R_ALL_OUTPUTS_SINK_20261103: the combine sink only spans sinks that can
# actually play (a sink whose active port is "not available" — e.g. HDMI with no display —
# stalled the whole combine: silent playback + a clock that never advanced on the Latitude
# 3510). The result is cached and refreshed on a worker, so pressing Play never waits on
# pactl from the GUI thread.
_ALL_SINK_CACHE = {"name": "", "at": 0.0}
_ALL_SINK_LOCK = threading.Lock()
_ALL_SINK_TTL = 20.0


def _unavailable_pulse_sinks() -> set:
    """Sink names whose active port reports 'not available' (pactl list sinks)."""
    bad = set()
    try:
        raw = _run_text(["pactl", "list", "sinks"], timeout=2.0)
    except Exception:
        return bad
    name, active, ports = "", "", {}
    in_ports = False

    def flush():
        if name and active and "not available" in ports.get(active, ""):
            bad.add(name)
    for line in raw.splitlines():
        st = line.strip()
        if line.startswith("Sink #"):
            flush(); name, active, ports, in_ports = "", "", {}, False
        elif st.startswith("Name:"):
            name = st.split(":", 1)[1].strip()
        elif st.startswith("Ports:"):
            in_ports = True
        elif st.startswith("Active Port:"):
            active = st.split(":", 1)[1].strip(); in_ports = False
        elif in_ports and ":" in st:
            key = st.split(":", 1)[0].strip()
            ports[key] = st
    flush()
    return bad


def all_outputs_sink_cached(refresh: bool = False) -> str:
    """The combined sink name, without blocking: the cached value unless it is stale and
    no other thread is refreshing it (then refresh here — call from a worker)."""
    import time as _t
    now = _t.monotonic()
    if not refresh and _ALL_SINK_CACHE["name"] and now - _ALL_SINK_CACHE["at"] < _ALL_SINK_TTL:
        return _ALL_SINK_CACHE["name"]
    if not _ALL_SINK_LOCK.acquire(blocking=not _ALL_SINK_CACHE["name"]):
        return _ALL_SINK_CACHE["name"]
    try:
        name = _ensure_all_pulse_outputs_sink_uncached()
        _ALL_SINK_CACHE.update(name=name, at=_t.monotonic())
        return name
    finally:
        _ALL_SINK_LOCK.release()


def prewarm_all_outputs() -> str:
    """Build / refresh the All-outputs route ahead of Play (device-scan worker): the combine
    sink, and the internal analog output unmuted / at volume (Latitude speakers ship muted)."""
    name = all_outputs_sink_cached(refresh=True)
    try:
        dev = _preferred_alsa_output_device()
        if dev:
            _prepare_physical_alsa_output(dev)
    except Exception:
        pass
    return name


def _ensure_all_pulse_outputs_sink() -> str:
    return all_outputs_sink_cached()


def _ensure_all_pulse_outputs_sink_uncached() -> str:
    """Create/reuse a Pulse/PipeWire combine sink spanning every real sink.

    This keeps the appliance default audible on internal speakers and HDMI/USB/
    Bluetooth simultaneously when those outputs are published by PulseAudio or
    PipeWire. Returns an empty string when the server cannot create a combined sink.
    """
    if not shutil.which("pactl"):
        return ""
    try:
        raw=_run_text(["pactl","list","short","sinks"],timeout=2.0)
        names=[]
        _bad=_unavailable_pulse_sinks()
        for line in raw.splitlines():
            parts=line.split("\t") if "\t" in line else line.split()
            if len(parts)<2: continue
            name=parts[1]
            if name in _bad:
                continue          # port not available (unplugged HDMI / DP): would stall the combine
            try:   # GROOVEBOX_R23R_DEVICE_PROFILES_20261103: switched off in Hardware & Master → Devices
                import audio_device_profiles as _adp
                if not _adp.enabled("pulse:" + name):
                    continue
            except Exception:
                pass
            if not any(t in name.casefold() for t in ("auto_null","dummy","null","groovebox_all_outputs")):
                if name not in names: names.append(name)
        if not names:
            return ""
        combined="groovebox_all_outputs"
        existing_line=next((line for line in raw.splitlines() if (line.split("\t") if "\t" in line else line.split())[1:2]==[combined]),"")
        if existing_line:
            modules=_run_text(["pactl","list","modules","short"],timeout=1.5)
            current_args=next((line for line in modules.splitlines() if "module-combine-sink" in line and combined in line),"")
            desired=",".join(names)
            if current_args and ("slaves="+desired) in current_args:
                return combined
            # HDMI/USB hot-plugging changes the desired slave set. Reload only
            # the combine module so newly detected outputs join the default route.
            try:
                module_id=(current_args.split("\t") if "\t" in current_args else current_args.split())[0] if current_args else ""
                if module_id.isdigit(): subprocess.run([shutil.which("pactl") or "pactl","unload-module",module_id],capture_output=True,timeout=2,check=False)
            except Exception: pass
        # A single sink is already the whole available output set.
        if len(names)==1:
            return names[0]
        module=shutil.which("pactl")
        cp=subprocess.run([module,"load-module","module-combine-sink",f"sink_name={combined}","sink_properties=device.description=Groovebox_All_Detected_Outputs","slaves="+",".join(names)],capture_output=True,text=True,timeout=4,check=False)
        if cp.returncode==0 and (cp.stdout or "").strip().isdigit():
            return combined
        # A stale combine sink may exist but be absent from the initial list due
        # to a short server transition. Never change the machine default here.
        return names[0] if names else ""
    except Exception:
        return ""


def player_routing(display: Optional[DisplayTarget], audio: Optional[AudioTarget], want_video: bool = True) -> Tuple[List[str], Dict[str, str]]:
    """Return mpv-compatible extra args and a subprocess environment overlay."""
    args: List[str] = []
    env: Dict[str, str] = {}
    if want_video and display and display.backend in {"xrandr", "wlr-randr"}:
        # Bind by connector/output name instead of enumeration order. This stays
        # deterministic when HDMI is hot-plugged and output indices reshuffle.
        args.extend(["--fullscreen", f"--fs-screen-name={display.name}"])
    elif want_video and display and display.backend == "drm-sysfs" and display.name:
        # Bare-metal mpv path for Intel i915/DRM connectors such as HDMI-A-1.
        args.extend(["--fullscreen","--vo=gpu-next","--gpu-context=drm",f"--drm-connector={display.name}"])
    # HF28.2 / R23F:
    # - Explicit "__all_detected__" always uses the aggregate All-outputs route.
    # - On sOS, None/empty/"System default" must still force physical ALSA (PCH
    #   analog) even when PipeWire/HDMI sinks look healthy — otherwise the
    #   playback clock advances while speakers stay silent (R23F contract).
    # - Off sOS, None/empty prefer the All combine sink when Pulse is available.
    audio_name = getattr(audio, "name", "") if audio is not None else ""
    explicit_all = audio_name == "__all_detected__"
    unset_or_default = (audio is None) or (audio_name in ("", "default", "system"))
    if explicit_all or (unset_or_default and not _running_on_sos()):
        combined=_ensure_all_pulse_outputs_sink()
        if combined:
            env["PULSE_SINK"]=combined
            # mpv's PipeWire AO ignores PULSE_SINK: name the sink on the Pulse AO explicitly.
            args.extend(["--ao=pulse,pipewire,alsa", f"--audio-device=pulse/{combined}"])
            # (No set-default-sink / amixer here: that ran on the GUI thread on every Play and
            # changed the machine default; the device scan worker prepares the route.)
        elif _real_alsa_playback_available():
            alsa_device=_preferred_alsa_output_device() or "alsa/default"
            _prepare_physical_alsa_output(alsa_device)
            args.extend(["--ao=alsa",f"--audio-device={alsa_device}"])
            args.extend(["--volume=100", "--audio-fallback-to-null=no"])
    elif audio and audio_name and not unset_or_default:
        if getattr(audio,"backend","pulse") == "alsa":
            # HDMI/DisplayPort has a distinct digital PCM/profile. Still run the
            # digital-safe unmute/volume path inside _prepare_physical_alsa_output
            # (is_digital branch never activates analog UCM). Skipping prepare
            # left HDMI silent on some Dell Latitude 3510 + external display setups.
            _prepare_physical_alsa_output(audio.name)
            args.extend(["--ao=alsa", f"--audio-device={audio.name}"])
            # HF27: keep digital routes audible; some builds default softvol low.
            route_hint=(str(getattr(audio,"kind","") or "")+" "+str(audio.name)+" "+str(getattr(audio,"description","") or "")).casefold()
            if any(token in route_hint for token in ("hdmi","displayport","dp audio","iec958","spdif")):
                args.extend(["--volume=100", "--softvol-max=200", "--audio-fallback-to-null=no"])
        else:
            env["PULSE_SINK"] = audio.name
    elif _real_alsa_playback_available() and (_running_on_sos() or not _real_pulse_sink_available()):
        # On the appliance, "system default" must mean the internal physical
        # speaker when one exists. A healthy HDMI/PipeWire sink can advance the
        # playback clock while remaining acoustically silent, so clock-based
        # recovery alone cannot detect the wrong default route.
        alsa_device=_preferred_alsa_output_device() or "alsa/default"
        _prepare_physical_alsa_output(alsa_device)
        args.extend(["--ao=alsa", f"--audio-device={alsa_device}"])

    # R23: physical player output is intentionally conservative. Source media may
    # be 96/128/192 kHz; mpv resamples only the playback stream to 48 kHz stereo.
    # Never start with --ao=null.  The Player watchdog may detach audio *after* a
    # verified clock stall, but initial playback always attempts real hardware.
    args.extend(["--audio-samplerate=48000", "--audio-channels=stereo", "--audio-buffer=0.12"])
    if want_video:
        args.extend(["--audio-fallback-to-null=no", "--autosync=30"])
    # GROOVEBOX_R23R_DEVICE_PROFILES_20261103: an ALSA route plays at the rate / bit depth chosen for
    # that card in Hardware & Master → Devices (matched by its hw:X,Y).
    try:
        import re as _re, audio_device_profiles as _adp
        dev = next((a.split("=", 1)[1] for a in args if str(a).startswith("--audio-device=alsa")), "")
        m = _re.search(r"hw:(\d+),(\d+)", dev)
        if m:
            tag = f"hw:{m.group(1)},{m.group(2)}"
            for pname, prof in _adp.load().items():
                if tag in pname:
                    if int(prof.get("rate", 0) or 0) > 0:
                        args.append(f"--audio-samplerate={int(prof['rate'])}")
                    fmt = {16: "s16", 24: "s24", 32: "s32"}.get(int(prof.get("bits", 0) or 0))
                    if fmt:
                        args.append(f"--audio-format={fmt}")
                    break
    except Exception:
        pass
    return args, env


def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class MediaShareServer:
    """Small local-network server for TV playback and game-package distribution."""

    def __init__(self, port: int = 8780):
        self.port = int(port)
        self.token = secrets.token_urlsafe(12)
        self.server: Optional[ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.playlist: List[Dict[str, Any]] = []
        self.current_media: Optional[str] = None
        self.shared_games: Dict[str, str] = {}
        self.title = "Groovebox Media Hub"
        self.compat_cache_dir = os.path.join(tempfile.gettempdir(), "groovebox_tv_compat")
        os.makedirs(self.compat_cache_dir, exist_ok=True)

    def set_playlist(self, items: Iterable[Dict[str, Any]]) -> None:
        clean = []
        for it in items:
            p = os.path.abspath(str(it.get("path", "")))
            if os.path.isfile(p):
                clean.append({
                    "path": p,
                    "name": os.path.basename(p),
                    "volume": int(it.get("volume", 100) or 100),
                    "rate": float(it.get("rate", 1.0) or 1.0),
                    "pitch_semitones": float(it.get("pitch_semitones", 0.0) or 0.0),
                    "duration_s": float(it.get("duration_s", 5.0) or 5.0),
                    "media_kind": ("audio" if Path(p).suffix.lower() in {".mp3",".wav",".ogg",".flac",".opus",".m4a",".aac",".aiff",".aif",".caf"} else "video"),
                })
        self.playlist = clean

    def set_current(self, path: Optional[str]) -> None:
        self.current_media = os.path.abspath(path) if path and os.path.isfile(path) else None

    def share_game(self, path: str) -> str:
        p = os.path.abspath(path)
        if not (os.path.isfile(p) and p.lower().endswith(".zip")):
            raise ValueError("Game package must be an existing .zip file")
        key = secrets.token_urlsafe(8)
        self.shared_games[key] = p
        return key

    def base_url(self) -> str:
        return f"http://{lan_ip()}:{self.port}"

    def tv_url(self) -> str:
        return f"{self.base_url()}/tv?token={quote(self.token)}"

    def game_url(self, key: str) -> str:
        return f"{self.base_url()}/game/{quote(key)}?token={quote(self.token)}"

    def compatible_media(self, path: str, duration_s: float = 5.0) -> str:
        """Return a TV/browser-friendly file, transcoding once on demand when needed."""
        path = os.path.abspath(path)
        ext = Path(path).suffix.lower()
        if ext in {".mp4", ".webm", ".mp3", ".wav", ".ogg"}:
            return path
        ffmpeg = resolve_local_tool("ffmpeg", required=False)
        if not ffmpeg:
            return path
        st = os.stat(path)
        key = hashlib.sha256(f"{path}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()[:20]
        is_audio = ext in {".flac", ".opus", ".aiff", ".aif", ".caf", ".m4a", ".aac"}
        is_image = ext in {".png",".jpg",".jpeg",".webp",".bmp",".gif",".tif",".tiff"}
        if is_image: key = hashlib.sha256(f"{key}|duration={max(.25,float(duration_s)):.3f}".encode()).hexdigest()[:20]
        out = os.path.join(self.compat_cache_dir, key + (".mp3" if is_audio else ".mp4"))
        if os.path.isfile(out) and os.path.getsize(out) > 0:
            return out
        if is_audio:
            cmd=[ffmpeg,"-y","-v","error","-i",path,"-vn","-c:a","libmp3lame","-b:a","192k",out]
        elif is_image:
            cmd=[ffmpeg,"-y","-v","error","-loop","1","-framerate","30","-i",path,"-t",f"{max(.25,float(duration_s)):.3f}","-c:v","libx264","-preset","veryfast","-crf","22","-pix_fmt","yuv420p","-an",out]
        else:
            cmd=[ffmpeg,"-y","-v","error","-i",path,"-c:v","libx264","-preset","veryfast","-crf","22","-c:a","aac","-b:a","160k","-pix_fmt","yuv420p",out]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=900)
        except subprocess.TimeoutExpired:
            try: os.unlink(out)
            except OSError: pass
            raise RuntimeError("TV compatibility transcode timed out")
        if p.returncode != 0:
            try: os.unlink(out)
            except OSError: pass
            raise RuntimeError((p.stderr or "TV compatibility transcode failed")[-1200:])
        return out

    def start(self) -> None:
        if self.server is not None:
            return
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def _send(self, code: int, ctype: str, data: bytes, extra: Optional[Dict[str, str]] = None):
                self.send_response(code); self.send_header("Content-Type",ctype); self.send_header("Content-Length",str(len(data))); self.send_header("Cache-Control","no-store")
                if extra:
                    for k,v in extra.items(): self.send_header(k,v)
                self.end_headers()
                if self.command != "HEAD": self.wfile.write(data)

            def _authorized(self, parsed) -> bool:
                return parse_qs(parsed.query).get("token", [""])[0] == owner.token

            def _serve_file(self, path: str):
                try:
                    size=os.path.getsize(path); ctype=mimetypes.guess_type(path)[0] or "application/octet-stream"; start=0; end=max(0,size-1); code=200
                    range_h=self.headers.get("Range","")
                    if range_h.startswith("bytes=") and size>0:
                        spec=range_h[6:].split(",",1)[0].strip(); m=re.match(r"^(\d*)-(\d*)$",spec)
                        if m:
                            a,b=m.groups()
                            if not a and b:
                                length=max(1,min(size,int(b))); start=size-length; end=size-1
                            else:
                                start=int(a or 0); end=int(b) if b else size-1; start=max(0,min(start,size-1)); end=max(start,min(end,size-1))
                            code=206
                    length=0 if size==0 else end-start+1
                    self.send_response(code); self.send_header("Content-Type",ctype); self.send_header("Content-Length",str(length)); self.send_header("Cache-Control","no-store"); self.send_header("Accept-Ranges","bytes")
                    if code==206:self.send_header("Content-Range",f"bytes {start}-{end}/{size}")
                    self.end_headers()
                    if self.command=="HEAD" or length<=0:return
                    with open(path,"rb") as f:
                        f.seek(start); remaining=length
                        while remaining>0:
                            chunk=f.read(min(1024*1024,remaining))
                            if not chunk:break
                            self.wfile.write(chunk); remaining-=len(chunk)
                except (BrokenPipeError,ConnectionResetError):
                    return
                except Exception as e:
                    self._send(500,"application/json",json.dumps({"error":str(e)}).encode())

            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path == "/health":
                    self._send(200, "application/json", b'{"ok":true}')
                    return
                if not self._authorized(parsed):
                    self._send(403, "application/json", b'{"error":"bad token"}')
                    return
                if parsed.path == "/manifest.json":
                    payload = {
                        "title": owner.title,
                        "items": [dict(it, url=f"/compat/{i}?token={quote(owner.token)}") for i, it in enumerate(owner.playlist)],
                        "current": f"/current?token={quote(owner.token)}" if owner.current_media else None,
                    }
                    self._send(200, "application/json", json.dumps(payload).encode())
                    return
                if parsed.path == "/tv":
                    data = owner._tv_html().encode("utf-8")
                    self._send(200, "text/html; charset=utf-8", data)
                    return
                if parsed.path == "/current" and owner.current_media:
                    self._serve_file(owner.current_media); return
                m = re.match(r"^/compat/(\d+)$", parsed.path)
                if m:
                    i = int(m.group(1))
                    if 0 <= i < len(owner.playlist):
                        try:
                            self._serve_file(owner.compatible_media(owner.playlist[i]["path"], owner.playlist[i].get("duration_s",5.0)))
                        except Exception as e:
                            self._send(500, "application/json", json.dumps({"error":str(e)}).encode())
                        return
                m = re.match(r"^/media/(\d+)$", parsed.path)
                if m:
                    i = int(m.group(1))
                    if 0 <= i < len(owner.playlist): self._serve_file(owner.playlist[i]["path"]); return
                m = re.match(r"^/game/([A-Za-z0-9_-]+)$", parsed.path)
                if m and m.group(1) in owner.shared_games:
                    self._serve_file(owner.shared_games[m.group(1)]); return
                self._send(404, "application/json", b'{"error":"not found"}')

            def do_HEAD(self):
                # Same authorization/routing as GET, but _send/_serve_file omit bodies.
                return self.do_GET()

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        srv, self.server = self.server, None
        if srv:
            try: srv.shutdown(); srv.server_close()
            except Exception: pass
        self.thread = None

    def _tv_html(self) -> str:
        token = json.dumps(self.token)
        return f"""<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>
<title>{html.escape(self.title)}</title>
<style>body{{margin:0;background:#05070a;color:#ddd;font:16px sans-serif}}#wrap{{height:100vh;display:grid;grid-template-rows:1fr auto}}video,audio{{width:100%;height:100%;object-fit:contain;background:#000}}#bar{{padding:8px 12px;background:#111}}button{{font-size:18px;margin-right:8px}}</style>
<div id=wrap><div id=stage></div><div id=bar><button onclick='prev()'>◀</button><button onclick='next()'>▶</button><span id=label>Groovebox</span></div></div>
<script>
const token={token}; let items=[],i=0,el=null;
async function boot(){{let m=await (await fetch('/manifest.json?token='+encodeURIComponent(token))).json();items=m.items||[]; if(items.length) play(0);}}
function play(n){{if(!items.length)return;i=(n+items.length)%items.length;let it=items[i];let tag=(it.media_kind==='audio')?'audio':'video';document.getElementById('stage').innerHTML='<'+tag+' id=p controls autoplay playsinline></'+tag+'>';el=document.getElementById('p');el.src=it.url;el.volume=Math.max(0,Math.min(1,(it.volume||100)/100));try{{el.playbackRate=Math.max(.25,Math.min(4,it.rate||1));}}catch(e){{}}el.onended=()=>next();document.getElementById('label').textContent=(i+1)+'/'+items.length+' '+it.name+' · '+(it.rate||1).toFixed(2)+'×';el.play().catch(()=>{{}});}}
function next(){{play(i+1)}} function prev(){{play(i-1)}} boot();
</script>"""


def cast_with_catt(url: str, device: Optional[str] = None) -> Tuple[bool, str]:
    catt = shutil.which("catt")
    if not catt:
        return False, "catt is not installed"
    cmd = [catt]
    if device: cmd += ["-d", device]
    cmd += ["cast", url]
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, f"cast started (pid {p.pid})"
    except Exception as e:
        return False, str(e)
