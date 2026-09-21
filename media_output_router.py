#!/usr/bin/env python3
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


def _run_text(cmd: Sequence[str], timeout: float = 2.0) -> str:
    try:
        p = subprocess.run(list(cmd), capture_output=True, text=True, timeout=timeout, check=False)
        return p.stdout or ""
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
            kind="bluetooth" if ("bluez" in low or "bluetooth" in low) else ("hdmi" if "hdmi" in low else ("usb" if "usb" in low else "audio"))
            out.append(AudioTarget(name,name,state=state,kind=kind,backend="pulse")); seen.add(name)
    # ALSA fallback is essential on a minimal appliance before PipeWire/Pulse
    # compatibility has published sinks. Expose HDMI devices directly to mpv.
    if shutil.which("aplay"):
        txt=_run_text(["aplay","-L"],timeout=4.0); current=None
        for line in txt.splitlines():
            if line and not line[0].isspace():
                current=line.strip(); low=current.lower()
                if ("hdmi" in low or "displayport" in low) and current not in seen:
                    out.append(AudioTarget("alsa/"+current,current,kind="hdmi",backend="alsa")); seen.add(current)
    return out


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
    if audio and audio.name:
        if getattr(audio,"backend","pulse") == "alsa": args.append(f"--audio-device={audio.name}")
        else: env["PULSE_SINK"] = audio.name
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
        p = subprocess.run(cmd, capture_output=True, text=True, check=False)
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
