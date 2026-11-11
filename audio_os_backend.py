# GROOVEBOX_V35_22ZZ_R23F_SOS_PHYSICAL_OUTPUT_PRIORITY_20261002
# GROOVEBOX_V35_22ZZ_R19_CAPTURE_THREAD_STREAMING_PLAYER_20260930
# GROOVEBOX_V35_22ZZ_R18_ADAPTIVE_HARDWARE_SAMPLE_RATE_20260930
"""OS/standalone audio compatibility layer for Mathematician's Groovebox.

Goals:
- zero SciPy dependency for PCM WAV I/O;
- one lazy/optional sounddevice import for realtime PortAudio access;
- keep NumPy as the buffer/interchange layer while native C++ handles hot DSP.
"""
from __future__ import annotations
import os
import sys

import wave
import time
import threading
from pathlib import Path
import numpy as np

try:
    import sounddevice as sd  # optional realtime backend, bundled in standalone builds
    HAS_SOUNDDEVICE = True
except Exception:
    sd = None
    HAS_SOUNDDEVICE = False


def read_wav(path):
    """Read PCM WAV into a NumPy array, scipy.io.wavfile-compatible ordering.

    Supports unsigned 8-bit and signed 16/24/32-bit PCM. 24-bit is expanded to
    int32 with sign extension. Multi-channel data is returned shape (frames, ch).
    """
    path = str(Path(path))
    with wave.open(path, "rb") as wf:
        channels = int(wf.getnchannels())
        sr = int(wf.getframerate())
        width = int(wf.getsampwidth())
        frames = int(wf.getnframes())
        raw = wf.readframes(frames)
    if width == 1:
        arr = np.frombuffer(raw, dtype=np.uint8).copy()
    elif width == 2:
        arr = np.frombuffer(raw, dtype="<i2").copy()
    elif width == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        vals = (b[:, 0].astype(np.int32)
                | (b[:, 1].astype(np.int32) << 8)
                | (b[:, 2].astype(np.int32) << 16))
        vals = (vals ^ 0x800000) - 0x800000
        arr = vals
    elif width == 4:
        arr = np.frombuffer(raw, dtype="<i4").copy()
    else:
        raise RuntimeError(f"Unsupported PCM WAV sample width: {width} bytes")
    if channels > 1:
        arr = arr.reshape(-1, channels)
    return sr, arr


def write_wav(path, sample_rate, data):
    """Write integer or float PCM WAV without SciPy.

    Float arrays are clipped to [-1,1] and encoded as rounded signed 24-bit PCM
    (GROOVEBOX_R23R_AUDIO_DEPTH_RATE_20261101; was truncated 16-bit).
    Integer arrays preserve 8/16/32-bit width; int64 is safely narrowed to 32-bit.
    """
    arr = np.asarray(data)
    if arr.ndim == 1:
        channels = 1
    elif arr.ndim == 2:
        channels = int(arr.shape[1])
    else:
        raise ValueError("WAV data must be 1-D mono or 2-D frames×channels")

    if np.issubdtype(arr.dtype, np.floating):
        v = np.rint(np.clip(np.nan_to_num(arr, nan=0.0), -1.0, 1.0) * 8388607.0).astype(np.int32)
        u = (v.reshape(-1).astype(np.int64) & 0xFFFFFF).astype(np.uint32)
        packed = np.empty((u.size, 3), dtype=np.uint8)
        packed[:, 0] = u & 0xFF; packed[:, 1] = (u >> 8) & 0xFF; packed[:, 2] = (u >> 16) & 0xFF
        out = packed
        width = 3
    elif arr.dtype == np.uint8:
        out = np.ascontiguousarray(arr)
        width = 1
    elif arr.dtype.itemsize <= 2:
        out = np.ascontiguousarray(arr.astype("<i2", copy=False))
        width = 2
    else:
        out = np.ascontiguousarray(np.clip(arr, -2147483648, 2147483647).astype("<i4"))
        width = 4

    with wave.open(str(Path(path)), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(width)
        wf.setframerate(int(sample_rate))
        wf.writeframes(out.tobytes(order="C"))


class _WavfileCompat:
    read = staticmethod(read_wav)
    write = staticmethod(write_wav)


wavfile = _WavfileCompat()


# GROOVEBOX_V35_22ZZ_R14_AUDIO_ROUTE_CACHE_20260930
_DEVICE_CACHE_LOCK = threading.Lock()
_DEVICE_CACHE_AT = 0.0
_DEVICE_CACHE = []
_DEVICE_CACHE_ERROR = None
_DEVICE_CACHE_TTL = 4.0
_BAD_OUTPUT_TOKENS = ("dummy", "null", "monitor of", "auto_null", "groovebox_all_outputs")
_BAD_INPUT_TOKENS = ("dummy", "null", "auto_null", "monitor", "loopback", "dmix", "groovebox_all_outputs")

# Last successful capture device (name, index). Prefer it on the next open.
_LAST_GOOD_INPUT = None
_LAST_OPEN_ERROR = ''

def note_successful_input(name, index):
    global _LAST_GOOD_INPUT
    _LAST_GOOD_INPUT = (str(name or ''), index)

def last_good_input():
    return _LAST_GOOD_INPUT

def last_open_error():
    return _LAST_OPEN_ERROR

# GROOVEBOX_R23R_OPEN_COOLDOWN_LOCK_20261031: these were referenced but never
# defined, so every adaptive input/output open raised NameError before it
# reached PortAudio.
_OPEN_FAIL_LOCK = threading.Lock()
_OPEN_FAIL_UNTIL = 0.0

def _set_open_error(msg):
    global _LAST_OPEN_ERROR
    _LAST_OPEN_ERROR = str(msg or '')[:240]

def _note_open_failure():
    global _OPEN_FAIL_UNTIL
    with _OPEN_FAIL_LOCK:
        _OPEN_FAIL_UNTIL = time.monotonic() + 1.5

def _open_allowed() -> bool:
    with _OPEN_FAIL_LOCK:
        return time.monotonic() >= _OPEN_FAIL_UNTIL


_DEVICE_QUERY_LOCK = threading.Lock()   # GROOVEBOX_NO_GUI_STALL_20261030: serialises sd.query_devices only


def _device_snapshot(force=False):
    """Cache PortAudio enumeration briefly so UI/device callbacks cannot thrash ALSA/PipeWire.

    The slow sd.query_devices() call runs OUTSIDE the cache lock.  A caller that
    already has older rows never waits for a query another thread is running (that
    wait froze the GUI whenever a background refresh hit a stalled PipeWire/ALSA).
    """
    global _DEVICE_CACHE_AT, _DEVICE_CACHE, _DEVICE_CACHE_ERROR
    if not HAS_SOUNDDEVICE:
        _DEVICE_CACHE_ERROR = "sounddevice import failed; PortAudio backend unavailable"
        return []
    now=time.monotonic()
    with _DEVICE_CACHE_LOCK:
        if (not force) and (now-_DEVICE_CACHE_AT)<_DEVICE_CACHE_TTL:
            return list(_DEVICE_CACHE)
        stale=list(_DEVICE_CACHE)
    got=_DEVICE_QUERY_LOCK.acquire(blocking=not stale)
    if not got:
        return stale            # a refresh is already in flight; serve the last known rows
    try:
        with _DEVICE_CACHE_LOCK:
            # Another thread may have refreshed while we waited for the query lock.
            if (not force) and (time.monotonic()-_DEVICE_CACHE_AT)<_DEVICE_CACHE_TTL:
                return list(_DEVICE_CACHE)
        try:
            # Query host APIs as well as devices: this preserves a useful error
            # on Linux when PortAudio is installed but ALSA/PipeWire is not ready.
            rows=[dict(d) for d in sd.query_devices()]
            err = None if rows else "PortAudio returned zero devices"
        except Exception as exc:
            rows=[]
            err = f"{type(exc).__name__}: {exc}"
        with _DEVICE_CACHE_LOCK:
            _DEVICE_CACHE_ERROR = err
            _DEVICE_CACHE=rows; _DEVICE_CACHE_AT=time.monotonic()
        return list(rows)
    finally:
        _DEVICE_QUERY_LOCK.release()


def audio_device_diagnostics(force=True):
    """Return backend/device state and the exact last enumeration error."""
    rows=_device_snapshot(force=force)
    hostapis=[]; default=None; error=_DEVICE_CACHE_ERROR
    if HAS_SOUNDDEVICE:
        try: hostapis=[dict(x) for x in sd.query_hostapis()]
        except Exception as exc: error = error or f"host API query: {type(exc).__name__}: {exc}"
        try: default=sd.default.device
        except Exception as exc: error = error or f"default device query: {type(exc).__name__}: {exc}"
    return {"sounddevice_available":HAS_SOUNDDEVICE,"devices":rows,"host_apis":hostapis,
            "default_device":default,"enumeration_error":error}



# GROOVEBOX_V35_22ZZ_R17_SHARED_AUDIO_ROUTING_20260930
def invalidate_device_cache():
    """Invalidate PortAudio enumeration after a real hardware refresh/hot-plug."""
    global _DEVICE_CACHE_AT, _DEVICE_CACHE, _DEVICE_CACHE_ERROR
    with _DEVICE_CACHE_LOCK:
        _DEVICE_CACHE_AT = 0.0
        _DEVICE_CACHE = []
        _DEVICE_CACHE_ERROR = None


def _first_audio_use(reason: str):
    try:
        from hardware_runtime import ensure_audio_ready
        ensure_audio_ready(reason)
    except Exception:
        pass


def list_input_devices(force=False):
    """Return physical/capture-capable PortAudio inputs; exclude dmix/monitors."""
    rows=_device_snapshot(force=force); out=[]
    for i,d in enumerate(rows):
        name=str(d.get('name','')).strip(); low=name.casefold()
        if not name or int(d.get('max_input_channels',0) or 0)<=0: continue
        if any(t in low for t in _BAD_INPUT_TOKENS): continue
        out.append((i,name,dict(d)))
    return out


def resolve_input_device_index(preferred_name=None, force=False):
    """Return a real capture device index; dmix is output-only and is never selected."""
    rows=_device_snapshot(force=force)
    if not rows: return None
    pref=str(preferred_name or '').strip().casefold()
    def ok(i):
        if not (0 <= int(i) < len(rows)): return False
        d=rows[int(i)]; name=str(d.get('name','')).casefold()
        return int(d.get('max_input_channels',0) or 0)>0 and not any(t in name for t in _BAD_INPUT_TOKENS)
    if pref:
        exact=[]; partial=[]
        for i,d in enumerate(rows):
            if not ok(i): continue
            name=str(d.get('name','')).casefold()
            if name==pref: exact.append(i)
            elif pref in name or name in pref: partial.append(i)
        if exact: return exact[0]
        if partial: return partial[0]
    try:
        default=sd.default.device
        in_idx=int(default[0] if isinstance(default,(tuple,list)) else default)
        if ok(in_idx): return in_idx
    except Exception: pass
    scored=[]
    for i,d in enumerate(rows):
        if not ok(i): continue
        name=str(d.get('name','')).casefold(); score=0
        for token,pts in (("pipewire",100),("pulse",90),("default",80),("mic",65),("microphone",65),("sof",55),("analog",45),("hda",35),("pch",30),("usb",25)):
            if token in name: score+=pts
        scored.append((score,-i,i))
    return max(scored)[2] if scored else None


_CAPTURE_RATE_LADDER = (48000, 44100, 96000, 192000)

def _input_rate_candidates(requested, device_index=None):
    requested=max(8000,int(round(float(requested or 48000))))
    rates=[requested]
    try:
        rows=_device_snapshot()
        if device_index is not None and 0 <= int(device_index) < len(rows):
            default=int(round(float(rows[int(device_index)].get('default_samplerate',0) or 0)))
            if default > 0 and default not in rates:
                rates.append(default)
    except Exception:
        pass
    for rate in _CAPTURE_RATE_LADDER:
        if rate not in rates:
            rates.append(rate)
    return rates

def negotiate_input_samplerate(samplerate=48000, *, channels=1, dtype='float32', preferred_name=None, device=None, force=False):
    """Return (supported_rate, device_index) for physical capture only.

    Interactive capture callers normally request <=48 kHz so camera/mic UI work
    cannot inherit a 96/192 kHz project/export rate. Canonical render/export state
    is never changed by this function.
    """
    if not HAS_SOUNDDEVICE:
        return int(samplerate), None
    idx=int(device) if device is not None else resolve_input_device_index(preferred_name, force=force)
    last=None
    for rate in _input_rate_candidates(samplerate, idx):
        try:
            sd.check_input_settings(device=idx, samplerate=int(rate), channels=int(channels), dtype=dtype)
            return int(rate), idx
        except Exception as exc:
            last=exc
    if not force:
        invalidate_device_cache()
        return negotiate_input_samplerate(samplerate, channels=channels, dtype=dtype, preferred_name=preferred_name, device=device, force=True)
    if last is not None:
        raise last
    raise RuntimeError('No usable physical input sample rate')

def open_input_stream_adaptive(*, samplerate=48000, channels=1, dtype='float32', callback=None,
                               blocksize=0, latency='low', preferred_name=None, device=None, **kwargs):
    """Open capture at a supported hardware rate and return (stream, rate, index).

    Fails fast if a recent open already failed, so the UI thread is not blocked
    by repeated ALSA/PortAudio attempts when the selected mic has no signal.
    """
    if not HAS_SOUNDDEVICE: raise RuntimeError('sounddevice is unavailable')
    if not _open_allowed():
        raise RuntimeError('microphone open on cooldown after recent failure')
    name = str(preferred_name or '').casefold()
    if name and any(t in name for t in _BAD_INPUT_TOKENS):
        raise RuntimeError('selected device is not a usable capture endpoint')
    # Prefer the last device that actually opened when the caller did not pin one.
    if device is None and not preferred_name:
        last = last_good_input()
        if last and last[0]:
            preferred_name = last[0]
    _first_audio_use('audio-record-adaptive')
    try:
        rate,idx=negotiate_input_samplerate(samplerate,channels=channels,dtype=dtype,preferred_name=preferred_name,device=device)
        params=dict(samplerate=int(rate),channels=channels,dtype=dtype,callback=callback,
                    blocksize=blocksize,latency=latency,**kwargs)
        if idx is not None: params['device']=idx
        stream = sd.InputStream(**params)
        note_successful_input(preferred_name or '', idx)
        _set_open_error('')
        return stream, int(rate), idx
    except Exception as exc:
        _set_open_error(exc)
        _note_open_failure()
        invalidate_device_cache()
        try:
            rate,idx=negotiate_input_samplerate(samplerate,channels=channels,dtype=dtype,preferred_name=preferred_name,device=device,force=True)
            params['samplerate']=int(rate)
            if idx is not None: params['device']=idx
            stream = sd.InputStream(**params)
            note_successful_input(preferred_name or '', idx)
            _set_open_error('')
            return stream, int(rate), idx
        except Exception as exc2:
            _set_open_error(exc2)
            _note_open_failure()
            raise

_CAPTURE_PREP_AT = [0.0]


def prepare_capture_level(min_pct=40, target_pct=70):
    """GROOVEBOX_R23R_CAPTURE_LEVEL_20261101: raise a muted / near-zero microphone when a
    recording starts (sOS only).

    The playback helper never touches capture controls, so a fresh boot often left
    the Dell's mic muted or at ~0% and recordings came out almost silent. This only
    acts on controls that are OFF or below ``min_pct`` (user choices above that are
    kept): capture switch on, capture/mic volume → ``target_pct``, a zero mic boost →
    one step, PipeWire/Pulse default source unmuted and raised if below ``min_pct``.
    Runs in the background, at most every 30 s.
    """
    now = time.monotonic()
    if now - _CAPTURE_PREP_AT[0] < 30.0:
        return
    _CAPTURE_PREP_AT[0] = now
    try:
        from media_output_router import _running_on_sos
        if not _running_on_sos():
            return
    except Exception:
        return

    def _run():
        import re as _re, shutil as _sh, subprocess as _sp
        def q(cmd, t=1.5):
            try:
                return _sp.run(cmd, capture_output=True, text=True, timeout=t).stdout or ""
            except Exception:
                return ""
        amixer = _sh.which("amixer")
        if amixer:
            cards = _re.findall(r"^\s*(\d+)\s+\[", open("/proc/asound/cards").read(), _re.M) if os.path.exists("/proc/asound/cards") else []
            for c in cards:
                for name in _re.findall(r"Simple mixer control '([^']+)'", q([amixer, "-c", c, "scontrols"])):
                    low = name.casefold()
                    if not any(k in low for k in ("capture", "mic", "dmic", "input")) or "playback" in low:
                        continue
                    info = q([amixer, "-c", c, "sget", name])
                    pcts = [int(x) for x in _re.findall(r"\[(\d+)%\]", info)]
                    if "[off]" in info and "Capture" in info:
                        q([amixer, "-c", c, "sset", name, "cap"])
                    if "boost" in low:
                        steps = _re.findall(r"Capture (\d+) \[|: (\d+) \[", info)
                        if pcts and max(pcts) == 0:
                            q([amixer, "-c", c, "sset", name, "1"])
                        continue
                    if pcts and max(pcts) < int(min_pct):
                        q([amixer, "-c", c, "sset", name, f"{int(target_pct)}%"])
        pactl = _sh.which("pactl"); wpctl = _sh.which("wpctl")
        if pactl:
            q([pactl, "set-source-mute", "@DEFAULT_SOURCE@", "0"])
            vols = [int(x) for x in _re.findall(r"(\d+)%", q([pactl, "get-source-volume", "@DEFAULT_SOURCE@"]))]
            if vols and max(vols) < int(min_pct):
                q([pactl, "set-source-volume", "@DEFAULT_SOURCE@", "100%"])
        elif wpctl:
            q([wpctl, "set-mute", "@DEFAULT_AUDIO_SOURCE@", "0"])
            m = _re.search(r"Volume:\s*([\d.]+)", q([wpctl, "get-volume", "@DEFAULT_AUDIO_SOURCE@"]))
            if m and float(m.group(1)) < int(min_pct) / 100.0:
                q([wpctl, "set-volume", "@DEFAULT_AUDIO_SOURCE@", "1.0"])
    threading.Thread(target=_run, daemon=True, name="GrooveboxCapturePrep").start()


def open_input_stream(*, samplerate=48000, channels=1, dtype='float32', callback=None,
                      blocksize=0, latency='low', preferred_name=None, device=None, **kwargs):
    """Compatibility opener retaining the caller-requested rate."""
    if not HAS_SOUNDDEVICE: raise RuntimeError('sounddevice is unavailable')
    if not _open_allowed():
        raise RuntimeError('microphone open on cooldown after recent failure')
    name = str(preferred_name or '').casefold()
    if name and any(t in name for t in _BAD_INPUT_TOKENS):
        raise RuntimeError('selected device is not a usable capture endpoint')
    _first_audio_use('audio-record')
    prepare_capture_level()
    idx=int(device) if device is not None else resolve_input_device_index(preferred_name)
    params=dict(samplerate=samplerate,channels=channels,dtype=dtype,callback=callback,
                blocksize=blocksize,latency=latency,**kwargs)
    if idx is not None: params['device']=idx
    try:
        return sd.InputStream(**params)
    except Exception:
        _note_open_failure()
        invalidate_device_cache()
        idx=int(device) if device is not None else resolve_input_device_index(preferred_name,force=True)
        if idx is not None: params['device']=idx
        try:
            return sd.InputStream(**params)
        except Exception:
            _note_open_failure()
            raise

_PROVEN_PCM_CACHE = {"t": 0.0, "v": ""}
_PROVEN_PCM_LOCK = threading.Lock()

def _proven_speaker_pcm(force=False, ttl=15.0):
    """Cached name of the proven physical ALSA output (spawns aplay, so never per-call)."""
    now=time.monotonic()
    with _PROVEN_PCM_LOCK:
        if not force and _PROVEN_PCM_CACHE["v"] and now-_PROVEN_PCM_CACHE["t"] < ttl:
            return _PROVEN_PCM_CACHE["v"]
    try:
        from media_output_router import _preferred_alsa_output_device
        v=str(_preferred_alsa_output_device() or "")
    except Exception:
        v=""
    with _PROVEN_PCM_LOCK:
        _PROVEN_PCM_CACHE["t"]=now
        if v: _PROVEN_PCM_CACHE["v"]=v
        return _PROVEN_PCM_CACHE["v"]


_ALL_ROUTE = {"ready": threading.Event(), "sink": "", "started": 0.0, "running": False}
_ALL_ROUTE_LOCK = threading.Lock()


def _build_all_outputs_route():
    """Worker: one PipeWire/Pulse sink spanning every real output + physical speaker prepared.

    GROOVEBOX_ALL_OUTPUTS_ALWAYS_20261102: the Performance media player already plays on
    "All detected outputs" (speaker, HDMI/DP, 3.5 mm, USB, Bluetooth at once), which is why
    video was audible on the Dell Latitude while PortAudio streams (main window, audio files,
    key notes) opened a single device. Every PortAudio output now takes the same route.
    """
    sink = ""
    try:
        from media_output_router import _ensure_all_pulse_outputs_sink, _preferred_alsa_output_device, _prepare_physical_alsa_output
        sink = str(_ensure_all_pulse_outputs_sink() or "")
        if sink:
            os.environ["PULSE_SINK"] = sink          # the ALSA 'pulse' plugin honours this
            try:
                import shutil as _sh, subprocess as _sp
                if _sh.which("pactl"):
                    _sp.run([_sh.which("pactl"), "set-default-sink", sink], capture_output=True, timeout=1.5, check=False)
            except Exception:
                pass
        try:
            pcm = _preferred_alsa_output_device()
            if pcm:
                _prepare_physical_alsa_output(pcm)   # UCM Speaker path + unmute, same as video
        except Exception:
            pass
    except Exception:
        sink = ""
    with _ALL_ROUTE_LOCK:
        _ALL_ROUTE["sink"] = sink
        _ALL_ROUTE["running"] = False
        _ALL_ROUTE["started"] = time.monotonic()
    _ALL_ROUTE["ready"].set()


def warm_all_outputs_route(force=False, ttl=15.0):
    """Start (never block on) the all-outputs route preparation; re-run at most every ttl s."""
    if os.environ.get("GROOVEBOX_OUTPUT_SINGLE", "").strip() in ("1", "true", "yes"):
        _ALL_ROUTE["ready"].set()
        return
    with _ALL_ROUTE_LOCK:
        if _ALL_ROUTE["running"]:
            return
        if not force and _ALL_ROUTE["started"] and time.monotonic() - _ALL_ROUTE["started"] < ttl:
            return
        _ALL_ROUTE["running"] = True
    threading.Thread(target=_build_all_outputs_route, daemon=True, name="GrooveboxAllOutputsRoute").start()


def _all_outputs_portaudio_index(rows, ok):
    """PortAudio row that reaches the combined sink (pipewire / pulse), or None."""
    warm_all_outputs_route()
    _ALL_ROUTE["ready"].wait(2.5)            # bounded; first call only, normally already ready
    sink = _ALL_ROUTE["sink"]
    if not sink:
        return None
    # "default" first: it is what the System-default choice resolves to, which is audible on
    # the Dell Latitude's main window; the combined sink is its default sink once the route
    # is built, so it still reaches every output.
    for token_match in (lambda n: n == "default",
                        lambda n: n in ("pipewire", "pulse"),
                        lambda n: "pipewire" in n or n.startswith("pulse")):
        for i, d in enumerate(rows):
            if ok(i) and token_match(str(d.get("name", "")).casefold()):
                return i
    return None


def resolve_output_device_index(preferred_name=None, force=False):
    """Return a usable physical/default PortAudio output index, never Dummy/Null when avoidable."""
    rows=_device_snapshot(force=force)
    if not rows:
        return None
    pref=str(preferred_name or '').strip().casefold()
    def ok(i):
        if not (0 <= int(i) < len(rows)): return False
        d=rows[int(i)]; name=str(d.get('name','')).casefold()
        return int(d.get('max_output_channels',0) or 0)>0 and not any(t in name for t in _BAD_OUTPUT_TOKENS)
    # Always play on every detected output at once when a sound server can combine them.
    try:
        _all_idx=_all_outputs_portaudio_index(rows, ok)
        if _all_idx is not None:
            return _all_idx
    except Exception:
        pass
    if pref:
        exact=[]; partial=[]
        for i,d in enumerate(rows):
            if not ok(i): continue
            name=str(d.get('name','')).casefold()
            if name==pref: exact.append(i)
            elif pref in name or name in pref: partial.append(i)
        if exact: return exact[0]
        if partial: return partial[0]
    try:
        from media_output_router import _running_on_sos
        sos = bool(_running_on_sos())
    except Exception:
        sos = False
    try:
        default=sd.default.device
        out_idx=int(default[1] if isinstance(default,(tuple,list)) else default)
        # A normal desktop's policy-selected default remains authoritative. On
        # sOS, however, the default can be a valid PipeWire/HDMI endpoint while
        # the laptop speakers live on a separate physical analog PCM. Let the
        # appliance scoring below choose the physical endpoint instead.
        if ok(out_idx) and not sos:
            return out_idx
    except Exception:
        pass
    if sos:
        # GROOVEBOX_SYSTEM_DEFAULT_FIRST_20261102: on the Latitude the PortAudio "default"
        # device (what a "System default" selection resolves to via the partial-name match
        # below) is audible in the main window, while a direct hw PCM picked by scoring is
        # not. With no explicit choice, use that same device before any direct PCM.
        for i,d in enumerate(rows):
            if ok(i) and str(d.get('name','')).casefold()=="default":
                return i
        # GROOVEBOX_PROVEN_SPEAKER_20261102: video plays because mpv is pinned to the
        # proven physical speaker PCM (boot state / UCM). PortAudio used to guess by
        # name and could open a different, silent PCM, so audio files, the main
        # window and keyboard notes were silent while video was audible. Resolve the
        # PortAudio row for that same card,device first.
        try:
            import re as _re
            m=_re.search(r"hw:(\d+),(\d+)", _proven_speaker_pcm(force=force))
            if m:
                tag=f"(hw:{m.group(1)},{m.group(2)})"
                for i,d in enumerate(rows):
                    if ok(i) and tag in str(d.get('name','')).casefold():
                        return i
        except Exception:
            pass
    scored=[]
    for i,d in enumerate(rows):
        if not ok(i): continue
        name=str(d.get('name','')).casefold(); score=0
        if sos:
            # sOS has no desktop policy daemon we can trust to choose the
            # internal speaker. Prefer a physical analog/SOF/HDA PortAudio PCM;
            # PipeWire/Pulse stays available but cannot outrank it by default.
            for token,pts in (("speaker",220),("analog",210),("sof",180),("hda",170),("pch",160),
                              ("hw:",150),("pipewire",55),("pulse",45),("default",35)):
                if token in name: score+=pts
            if "hdmi" in name or "displayport" in name: score -= 40
            if "headphone" in name: score-=40
        else:
            for token,pts in (("pipewire",90),("pulse",80),("default",70),("speaker",60),("sof",45),("analog",40),("hda",35),("pch",30)):
                if token in name: score+=pts
            if "hdmi" in name or "displayport" in name: score -= 5
            if "headphone" in name: score-=10
        scored.append((score,-i,i))
    return max(scored)[2] if scored else None




# Physical playback is allowed to run below the composition/export rate.
# This boundary never mutates the canonical render or export sample rate.
_HARDWARE_RATE_LADDER = (192000, 96000, 48000, 44100)

def _output_rate_candidates(requested, device_index=None):
    requested=max(1,int(round(float(requested))))
    rates=[requested]
    # For high-rate projects, descend rather than failing PortAudio -9997.
    for rate in _HARDWARE_RATE_LADDER:
        if rate < requested and rate not in rates:
            rates.append(rate)
    # The selected device decides the fallback. 48 kHz is used only when that
    # device's own default is 48 kHz, or when the device reports nothing.
    device_rate = 0
    try:
        rows=_device_snapshot()
        if device_index is not None and 0 <= int(device_index) < len(rows):
            device_rate=int(round(float(rows[int(device_index)].get('default_samplerate',0) or 0)))
    except Exception:
        device_rate = 0
    if device_rate > 0 and device_rate not in rates:
        rates.append(device_rate)
    elif device_rate <= 0:
        for rate in (48000, 44100):
            if rate not in rates:
                rates.append(rate)
    return rates

def negotiate_output_samplerate(samplerate, *, channels=1, dtype='float32', preferred_name=None, device=None, force=False):
    """Return (supported_rate, device_index) for physical playback.

    The requested render rate is tried first. Unsupported high rates descend
    192k -> 96k -> 48k -> 44.1k -> device default. The composition/render
    buffer itself is not changed here.
    """
    if not HAS_SOUNDDEVICE:
        return int(samplerate), None
    idx=int(device) if device is not None else resolve_output_device_index(preferred_name, force=force)
    last=None
    _cands=list(_output_rate_candidates(samplerate, idx))
    try:   # GROOVEBOX_R23R_DEVICE_PROFILES_20261103: the rate chosen for this device in Hardware & Master
        import audio_device_profiles as _adp
        _rows=_device_snapshot()
        if idx is not None and 0 <= int(idx) < len(_rows):
            _pr=_adp.rate(str(_rows[int(idx)].get('name','')))
            if _pr > 0:
                _cands=[_pr]+[r for r in _cands if r != _pr]
    except Exception:
        pass
    for rate in _cands:
        try:
            sd.check_output_settings(device=idx, samplerate=int(rate), channels=int(channels), dtype=dtype)
            return int(rate), idx
        except Exception as exc:
            last=exc
    if not force:
        invalidate_device_cache()
        return negotiate_output_samplerate(samplerate, channels=channels, dtype=dtype, preferred_name=preferred_name, device=device, force=True)
    if last is not None:
        raise last
    raise RuntimeError('No usable physical output sample rate')

def _resample_for_hardware(data, src_rate, dst_rate):
    arr=np.asarray(data,dtype=np.float32)
    src=int(src_rate); dst=int(dst_rate)
    if src <= 0 or dst <= 0 or src == dst or arr.size == 0:
        return np.ascontiguousarray(arr)
    # SciPy is bundled in the full runtime; use its anti-aliased polyphase path
    # when available. The NumPy path is a deterministic compatibility fallback.
    try:
        import math as _math
        _rp = __import__("scipy.signal", fromlist=["resample_poly"]).resample_poly
        g=_math.gcd(src,dst)
        out=_rp(arr, dst//g, src//g, axis=0)
        return np.ascontiguousarray(out,dtype=np.float32)
    except Exception:
        n_in=int(arr.shape[0]) if arr.ndim else int(arr.size)
        n_out=max(1,int(round(n_in*float(dst)/float(src))))
        old=np.linspace(0.0,1.0,n_in,endpoint=False,dtype=np.float64)
        new=np.linspace(0.0,1.0,n_out,endpoint=False,dtype=np.float64)
        if arr.ndim <= 1:
            out=np.interp(new,old,arr.reshape(-1)).astype(np.float32)
        else:
            out=np.empty((n_out,arr.shape[1]),dtype=np.float32)
            for ch in range(arr.shape[1]):
                out[:,ch]=np.interp(new,old,arr[:,ch]).astype(np.float32)
        return np.ascontiguousarray(out)

_OUTPUT_ROUTE_PREP_LOCK = threading.Lock()
_OUTPUT_ROUTE_PREP_AT = 0.0

def _prepare_sos_output_route(force=False):
    """Bounded mixer/UCM preparation shared by synth preview and media output."""
    global _OUTPUT_ROUTE_PREP_AT
    try:
        from media_output_router import _running_on_sos, _preferred_alsa_output_device, _prepare_physical_alsa_output
        if not _running_on_sos():
            return ""
    except Exception:
        return ""
    now=time.monotonic()
    with _OUTPUT_ROUTE_PREP_LOCK:
        if not force and _OUTPUT_ROUTE_PREP_AT and now-_OUTPUT_ROUTE_PREP_AT < 8.0:
            try: return _preferred_alsa_output_device() or ""
            except Exception: return ""
        try:
            dev=_preferred_alsa_output_device() or ""
            if dev:
                _prepare_physical_alsa_output(dev)
            _OUTPUT_ROUTE_PREP_AT=now
            return dev
        except Exception:
            return ""


def prepare_output_buffer(data, samplerate, *, preferred_name=None, device=None, dtype='float32'):
    """Adapt a playback-only buffer to the highest supported hardware rate.

    Returns (buffer, physical_rate, device_index). Export/render state remains at
    the original sample rate; only this physical I/O copy is resampled.
    """
    arr=np.asarray(data,dtype=np.float32)
    channels=1 if arr.ndim <= 1 else max(1,int(arr.shape[1]))
    rate,idx=negotiate_output_samplerate(samplerate,channels=channels,dtype=dtype,preferred_name=preferred_name,device=device)
    return _resample_for_hardware(arr,int(samplerate),rate), int(rate), idx

_threading = threading      # R32.8 sweep: the render stream referenced an unbound alias (NameError on start)


def _query_physical_rate(device_index, samplerate, channels):
    """R32.8 sweep: (rate, channels) the device really opens; the requested rate when it is accepted."""
    rate, _idx = negotiate_output_samplerate(samplerate, channels=channels, device=device_index)
    return int(rate), int(channels)


def stream_tuning(purpose: str = "transport"):
    """(blocksize, latency) per stream purpose (GROOVEBOX_R23R_SMOOTH_STREAMS_20261101).

    transport  - pre-rendered composition/file playback: robust 'high' latency so UI
                 work on a laptop can never starve the device (start delay ~50 ms).
    live       - Trigger / keyboard audition: 512-frame blocks, 'low' latency.
    Override with GROOVEBOX_AUDIO_LATENCY=low|high|<seconds> and
    GROOVEBOX_AUDIO_BLOCKSIZE=<frames> (0 = let PortAudio choose).
    """
    defaults = {
        "transport":      (1024, "high"),
        "file":           (2048, "high"),
        # file_decoded: entire buffer already in RAM — low latency is safe, no starve risk.
        "file_decoded":   (512,  "low"),
        "live":           (512,  "low"),
    }
    block, lat = defaults.get(str(purpose), (1024, "high"))
    if str(purpose) == "live" and os.environ.get("GROOVEBOX_SMOOTH", "").strip() == "1":
        block, lat = 1024, "high"   # GROOVEBOX_COMPAT_SETTINGS_20261102: smooth mode
    env_lat = os.environ.get("GROOVEBOX_AUDIO_LATENCY", "").strip().lower()
    if env_lat in ("low", "high"):
        lat = env_lat
    elif env_lat:
        try:
            lat = max(0.001, float(env_lat))
        except ValueError:
            pass
    env_blk = os.environ.get("GROOVEBOX_AUDIO_BLOCKSIZE", "").strip()
    if env_blk.isdigit():
        block = int(env_blk)
    return block, lat


def _log_audio_failure(where, exc):
    """GROOVEBOX_R23R_AUDIO_CHECK_20261101: device-open failures go to logs/errors.log."""
    try:
        import traceback as _tb
        try:
            import groovebox_paths as _gp
            d = os.path.join(_gp.base_dir(), "logs")
        except Exception:
            d = os.path.join(os.path.expanduser("~"), ".groovebox", "logs")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "errors.log"), "a", encoding="utf-8") as f:
            f.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} · audio {where} =====\n{exc!r}\n")
    except Exception:
        pass


_HWVOL_POST_OPEN_AT = [0.0]


def _hardware_volume_post_open_sync():
    """GROOVEBOX_R23R_HWVOL_POST_OPEN_20261101: re-assert the desired hardware volume
    + unmute shortly AFTER a stream opens. Opening the first stream makes PipeWire /
    WirePlumber activate the speaker route and restore its saved (often muted or
    zero) state, which undid the startup sync — the Dell symptom "no sound until a
    volume slider is moved". sOS only (the helper exists there); at most every 20 s."""
    helper = os.environ.get("GROOVEBOX_HARDWARE_VOLUME_HELPER", "/usr/bin/sos-hardware-volume")
    if not (os.path.isfile(helper) and os.access(helper, os.X_OK)):
        return
    now = time.monotonic()
    if now - _HWVOL_POST_OPEN_AT[0] < 20.0:
        return
    _HWVOL_POST_OPEN_AT[0] = now

    def _sync():
        try:
            import subprocess as _sp
            _sp.Popen([helper, "sync"], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, start_new_session=True)
        except Exception:
            pass
    for delay in (0.5, 2.5):
        t = threading.Timer(delay, _sync)
        t.daemon = True
        t.start()


def _try_fanout_stream(*, samplerate, channels, dtype, callback, blocksize, latency, kwargs):
    """Multi-device stream when >=2 physical outputs accept the format and no sound server
    can combine them (that case is already covered by the combined sink). None = use the
    ordinary single-device path (which keeps its own fallbacks)."""
    try:
        if os.environ.get("GROOVEBOX_OUTPUT_SINGLE", "").strip() in ("1", "true", "yes"):
            return None
        if not sys.platform.startswith("linux") or not HAS_SOUNDDEVICE:
            return None
        warm_all_outputs_route()
        _ALL_ROUTE["ready"].wait(2.5)
        if _ALL_ROUTE["sink"]:
            return None                       # PipeWire/Pulse combined sink already feeds every output
        rows=_device_snapshot()
        try:
            import audio_device_profiles as _adp
        except Exception:
            _adp = None
        def ok(i):
            if not (0 <= int(i) < len(rows)): return False
            d=rows[int(i)]; name=str(d.get('name','')).casefold()
            if _adp is not None and not _adp.enabled(str(d.get('name',''))):
                return False                   # switched off in Hardware & Master → Devices
            return int(d.get('max_output_channels',0) or 0)>0 and not any(t in name for t in _BAD_OUTPUT_TOKENS)
        from multi_output import physical_targets, FanOutStream
        targets=physical_targets(rows, ok)
        if len(targets) < 2:
            return None
        try:                                   # the proven speaker leads (it drives the callback)
            import re as _re
            m=_re.search(r"hw:(\d+),(\d+)", _proven_speaker_pcm())
            if m:
                tag=f"(hw:{m.group(1)},{m.group(2)})"
                targets.sort(key=lambda i: 0 if tag in str(rows[i].get('name','')).casefold() else 1)
        except Exception:
            pass
        fo=FanOutStream(sd, callback, device_ids=targets, samplerate=int(samplerate), channels=int(channels),
                        dtype=dtype, blocksize=blocksize, latency=latency, extra=dict(kwargs),
                        rescan=lambda: [i for i in physical_targets(_device_snapshot(), ok)],
                        on_join=_hardware_volume_post_open_sync)
        if len(fo.devices) < 2:
            fo.close()                         # one physical device is no better than the normal path
            return None
        _log_audio_failure("fan-out opened", f"devices={[rows[i].get('name') for i in fo.devices]} skipped={fo.skipped}")
        return fo
    except Exception as exc:
        _log_audio_failure("fan-out unavailable (single device used)", exc)
        return None


# GROOVEBOX_SILENT_OUTPUT_FALLBACK_20261104 -----------------------------------
# The app sets SILENT_FALLBACK = True so it boots and runs with no audio device:
# streams that cannot open become SilentOutputStream, which keeps the callback
# clocked (transport, scopes, sequencers advance), discards the samples, and
# moves onto a real device as soon as one accepts a stream.
SILENT_FALLBACK = False
_SILENT_PROBE_S = 3.0
_SILENT_LIVE = set()
_SILENT_LIVE_LOCK = threading.Lock()
_CB_STOP = tuple(e for e in (getattr(sd, "CallbackStop", None), getattr(sd, "CallbackAbort", None)) if e)


class _SilentTime:
    __slots__ = ("currentTime", "outputBufferDacTime", "inputBufferAdcTime")

    def __init__(self, t):
        self.currentTime = self.outputBufferDacTime = self.inputBufferAdcTime = t


class _SilentStatus:
    input_underflow = input_overflow = output_underflow = output_overflow = priming_output = False

    def __bool__(self):
        return False


def _stop_all_silent_streams():
    # Before interpreter teardown: a still-running silent clock would call into Qt objects
    # that are being destroyed (native crash at exit).
    with _SILENT_LIVE_LOCK:
        live = list(_SILENT_LIVE)
    for s in live:
        try:
            s.close()
        except Exception:
            pass


import atexit as _atexit
_atexit.register(_stop_all_silent_streams)


def silent_output_active() -> bool:
    """True while at least one output is running silent, waiting for a device."""
    with _SILENT_LIVE_LOCK:
        return any(s._real is None and s._running for s in _SILENT_LIVE)


def _usable_output_rows():
    rows = _device_snapshot(force=True)
    if not rows and HAS_SOUNDDEVICE:
        # PortAudio only enumerates at init; with zero devices no stream can be open, so a
        # re-init is safe and is the only way to see a sound server or card that appeared later.
        with _DEVICE_QUERY_LOCK:
            try:
                sd._terminate(); sd._initialize()
            except Exception:
                pass
        invalidate_device_cache()
        rows = _device_snapshot(force=True)
    return [d for d in rows if int(d.get('max_output_channels', 0) or 0) > 0
            and not any(t in str(d.get('name', '')).casefold() for t in _BAD_OUTPUT_TOKENS)]


class SilentOutputStream:
    silent = True

    def __init__(self, open_real, *, samplerate, channels=1, dtype='float32', callback=None, blocksize=0):
        self._open_real = open_real
        self.samplerate = float(samplerate or 48000)
        self.channels = int(channels or 1)
        self.dtype = dtype
        self.blocksize = int(blocksize or 0) or 512
        self.latency = 0.0
        self.device = None
        self._cb = callback
        self._lock = threading.Lock()
        self._stop_evt = threading.Event()
        self._thread = None
        self._real = None
        self._running = False
        self._closed = False
        with _SILENT_LIVE_LOCK:
            _SILENT_LIVE.add(self)

    @property
    def active(self):
        real = self._real
        if real is not None:
            try:
                return bool(real.active)
            except Exception:
                return False
        return self._running

    @property
    def stopped(self):
        return not self.active

    @property
    def closed(self):
        return self._closed

    @property
    def cpu_load(self):
        return 0.0

    def start(self):
        with self._lock:
            if self._closed:
                return
            real = self._real
            if real is None:
                if self._running:
                    return
                self._running = True
                self._stop_evt.clear()
                self._thread = threading.Thread(target=self._run, name="groovebox-silent-audio", daemon=True)
                self._thread.start()
                return
        real.start()

    def stop(self, ignore_errors=True):
        with self._lock:
            self._running = False
            self._stop_evt.set()
            th, real = self._thread, self._real
        if th is not None and th is not threading.current_thread():
            th.join(timeout=1.0)
        if real is not None:
            try:
                real.stop()
            except Exception:
                if not ignore_errors:
                    raise

    abort = stop

    def close(self, ignore_errors=True):
        self.stop()
        with self._lock:
            self._closed = True
            real, self._real = self._real, None
        with _SILENT_LIVE_LOCK:
            _SILENT_LIVE.discard(self)
        if real is not None:
            try:
                real.close()
            except Exception:
                if not ignore_errors:
                    raise

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_exc):
        self.close()

    def _run(self):
        frames = self.blocksize
        period = frames / self.samplerate
        try:
            buf = np.zeros((frames, self.channels), dtype=np.dtype(self.dtype))
        except Exception:
            buf = np.zeros((frames, self.channels), dtype=np.float32)
        status = _SilentStatus()
        t0 = time.monotonic()
        next_t = t0
        next_probe = t0 + _SILENT_PROBE_S
        while not self._stop_evt.is_set() and not sys.is_finalizing():
            now = time.monotonic()
            if self._cb is not None:
                buf.fill(0)
                try:
                    self._cb(buf, frames, _SilentTime(now - t0), status)
                except _CB_STOP:
                    with self._lock:
                        self._running = False
                    return
                except Exception:
                    pass
            if now >= next_probe:
                next_probe = now + _SILENT_PROBE_S
                if self._promote():
                    return
            next_t += period
            delay = next_t - time.monotonic()
            if delay > 0:
                self._stop_evt.wait(delay)
            elif delay < -0.5:
                next_t = time.monotonic()

    def _promote(self):
        try:
            if not _usable_output_rows():
                return False
            real = self._open_real()
        except Exception:
            return False
        with self._lock:
            if self._stop_evt.is_set() or self._closed:
                keep = False
            else:
                self._real = real
                self.device = getattr(real, "device", None)
                self.latency = getattr(real, "latency", 0.0)
                keep = True
        if not keep:
            try:
                real.close()
            except Exception:
                pass
            return False
        try:
            real.start()
        except Exception:
            with self._lock:
                self._real = None
            try:
                real.close()
            except Exception:
                pass
            return False
        print("[Audio] output device available — audio resumed", file=sys.stderr, flush=True)
        return True


def open_output_stream(*, samplerate, channels=1, dtype='float32', callback=None,
                       blocksize=0, latency='low', preferred_name=None, silent_fallback=None, **kwargs):
    """Open a routed output stream; with no usable device, return a SilentOutputStream when enabled."""
    if silent_fallback is None:
        silent_fallback = SILENT_FALLBACK
    args = dict(samplerate=samplerate, channels=channels, dtype=dtype, callback=callback,
                blocksize=blocksize, latency=latency, preferred_name=preferred_name, **kwargs)
    if not silent_fallback or callback is None:
        return _open_output_stream_strict(**args)
    try:
        return _open_output_stream_strict(**args)
    except Exception as exc:
        print(f"[Audio] no usable output device ({type(exc).__name__}); running silent until one appears",
              file=sys.stderr, flush=True)
        return SilentOutputStream(lambda: _open_output_stream_strict(**args), samplerate=samplerate,
                                  channels=channels, dtype=dtype, callback=callback, blocksize=blocksize)


def _open_output_stream_strict(*, samplerate, channels=1, dtype='float32', callback=None,
                               blocksize=0, latency='low', preferred_name=None, **kwargs):
    """Open one routed sounddevice stream using the same resolver as sample preview."""
    if not HAS_SOUNDDEVICE:
        raise RuntimeError('sounddevice is unavailable')
    name = str(preferred_name or '').casefold()
    if name and any(t in name for t in _BAD_OUTPUT_TOKENS):
        # e.g. the "groovebox_all_outputs" combine sink, which Performance stores as the
        # preferred name. That used to raise here on every open ("not a usable playback
        # endpoint"); it simply means "all outputs / no specific device".
        preferred_name = None
    _first_audio_use('audio-playback')
    _prepare_sos_output_route()
    # All devices at once, regardless of the selected device (GROOVEBOX_FANOUT_20261102).
    if callback is not None:
        _fo=_try_fanout_stream(samplerate=samplerate, channels=channels, dtype=dtype, callback=callback,
                               blocksize=blocksize, latency=latency, kwargs=kwargs)
        if _fo is not None:
            _hardware_volume_post_open_sync()
            return _fo
    idx=resolve_output_device_index(preferred_name)
    params=dict(samplerate=samplerate,channels=channels,dtype=dtype,callback=callback,
                blocksize=blocksize,latency=latency,**kwargs)
    # GROOVEBOX_FANOUT_20261102: never fail on the first refusal. Try the resolved device, then
    # the system default / sound-server devices, the proven speaker, and every other real
    # output, and only report failure when all of them have refused.
    cands=[]
    def _add(i):
        if i is not None and int(i) not in cands:
            cands.append(int(i))
    _add(idx)
    last=None
    for _round in (0, 1):
        rows=_device_snapshot(force=bool(_round))
        def _ok(i, rows=rows):
            d=rows[i]; n=str(d.get('name','')).casefold()
            return int(d.get('max_output_channels',0) or 0)>0 and not any(t in n for t in _BAD_OUTPUT_TOKENS)
        if _round:
            _add(resolve_output_device_index(preferred_name, force=True))
        for want in (lambda n: n=="default", lambda n: n in ("pipewire","pulse"),
                     lambda n: "hw:" in n, lambda n: True):
            for i,d in enumerate(rows):
                if _ok(i) and want(str(d.get('name','')).casefold()):
                    _add(i)
        for dev in list(cands)[:8]:
            p2=dict(params); p2['device']=dev
            try:   # GROOVEBOX_R23R_DEVICE_PROFILES_20261103: the device's own bit depth
                import audio_device_profiles as _adp
                p2=_adp.wrap_params(p2, str(rows[dev].get('name','')) if 0 <= dev < len(rows) else '')
            except Exception:
                pass
            try:
                st = sd.OutputStream(**p2)
                _hardware_volume_post_open_sync()
                return st
            except Exception as _exc:
                last=_exc
        cands=[]
    if idx is None:
        try:                                   # nothing enumerated: let PortAudio pick its default
            st = sd.OutputStream(**params)
            _hardware_volume_post_open_sync()
            return st
        except Exception as _exc:
            last=_exc
    _note_open_failure()
    _log_audio_failure(f"output open (preferred={preferred_name!r}, index={idx!r}, rate={samplerate})", last)
    raise last if last is not None else RuntimeError('no usable output device')


# GROOVEBOX_R23R_HW_CLOCK_RING_20261103 ----------------------------------------

import concurrent.futures as _cf


class _ClockAlignedRingBuffer:
    """Lock-free ring buffer that decouples render threads from the PortAudio callback.

    Render threads write ahead; the PortAudio callback reads without touching the
    GIL-heavy Python path.  Buffer depth = 4 blocks by default (keeps ~170 ms of
    headroom at 1024-sample / 48 kHz = ~21 ms per block).
    """

    def __init__(self, block_frames: int = 1024, channels: int = 2,
                 depth: int = 4, dtype=np.float32):
        self._block = int(block_frames)
        self._ch    = int(channels)
        self._depth = int(depth)
        self._buf   = np.zeros((depth, block_frames, channels), dtype=dtype)
        self._write = 0   # next slot to fill
        self._read  = 0   # next slot to consume
        self._lock  = threading.Lock()

    def write(self, frames: np.ndarray) -> bool:
        """Write one block; returns False if the ring is full (drop / xrun)."""
        with self._lock:
            used = (self._write - self._read) % self._depth
            if used >= self._depth - 1:
                return False
            sl = self._write % self._depth
        tgt = self._buf[sl]
        n = min(frames.shape[0], self._block)
        tgt[:n] = frames[:n, :self._ch] if frames.ndim == 2 else frames[:n, np.newaxis]
        if n < self._block:
            tgt[n:] = 0
        with self._lock:
            self._write = (self._write + 1) % (self._depth * 2)
        return True

    def read(self, out: np.ndarray) -> bool:
        """Fill *out* from the ring; returns False on underrun (silence inserted)."""
        with self._lock:
            if self._write == self._read:
                out[:] = 0
                return False
            sl = self._read % self._depth
        out[:] = self._buf[sl, :out.shape[0], :out.shape[1]] if out.ndim == 2 else self._buf[sl, :out.shape[0], 0]
        with self._lock:
            self._read = (self._read + 1) % (self._depth * 2)
        return True

    @property
    def fill(self) -> int:
        return (self._write - self._read) % (self._depth * 2)


class _HardwareClockMonitor:
    """Tracks hardware-vs-CPU clock drift in parts-per-million.

    Every time the PortAudio callback fires, call tick(hw_frames) with the
    hardware frame counter.  After a short settling period, drift_ppm() returns
    a stable estimate.
    """

    def __init__(self, nominal_rate: int = 48000):
        self._rate  = int(nominal_rate)
        self._t0    = time.monotonic()
        self._hw0   = 0
        self._hw    = 0
        self._ticks = 0
        self._ppm   = 0.0

    def tick(self, hw_frames: int) -> None:
        self._hw = int(hw_frames)
        self._ticks += 1
        if self._ticks == 32:          # discard first 32 callbacks (device warm-up)
            self._hw0 = self._hw
            self._t0  = time.monotonic()
        elif self._ticks > 32:
            elapsed   = time.monotonic() - self._t0
            expected  = (self._hw - self._hw0) / float(self._rate)
            if elapsed > 0.5:
                self._ppm = 1e6 * (expected - elapsed) / elapsed

    def drift_ppm(self) -> float:
        return self._ppm

    def hw_ticks(self) -> int:
        return self._hw


def _detect_host_api() -> str:
    """Return the name of the active PortAudio host API (JACK/CoreAudio/WASAPI/ALSA/…)."""
    if not HAS_SOUNDDEVICE:
        return "none"
    try:
        apis = sd.query_hostapis()
        for api in apis:
            if api.get("devices"):
                return str(api.get("name", "unknown"))
        return str(apis[0].get("name", "unknown")) if apis else "unknown"
    except Exception:
        return "unknown"


def warm_hardware_parallel(preferred_name: str | None = None) -> None:
    """Pre-warm all hardware prep tasks in parallel to reduce first-note latency."""
    tasks = [
        ("route",    lambda: warm_all_outputs_route(force=False)),
        ("snapshot", lambda: _device_snapshot(force=True)),
        ("resolve",  lambda: resolve_output_device_index(preferred_name, force=False)),
        ("host_api", _detect_host_api),
    ]
    try:
        import thread_budget as _tb
        lane = _tb.make_lane("hardware-warmup", max_workers=len(tasks), max_pending=len(tasks), kind="bulk")
    except Exception as _pool_exc:
        # Only a missing/broken scheduler takes this compatibility path.
        print(f"[hw-warm] shared scheduler unavailable; using one-shot fallback: {_pool_exc}")
        with _cf.ThreadPoolExecutor(max_workers=min(len(tasks), 2), thread_name_prefix="gb-hw-warm-fallback") as ex:
            futs = {ex.submit(fn): name for name, fn in tasks}
            for fut in _cf.as_completed(futs):
                try:
                    fut.result()
                except Exception as exc:
                    print(f"[hw-warm] {futs[fut]}: {exc}")
    else:
        futs = {lane.submit(fn): name for name, fn in tasks}
        for fut in _cf.as_completed(futs):
            try:
                fut.result()
            except Exception as exc:
                print(f"[hw-warm] {futs[fut]}: {exc}")



class RenderStreamBridge:
    """Stream rendered blocks to the audio device as they arrive — no full-render wait.

    Usage:
        bridge = RenderStreamBridge(samplerate=48000, preferred_name="...")
        bridge.start()
        for block in my_renderer():       # block: float32 ndarray (frames, 2)
            bridge.push(block)
            if bridge.stopped: break
        bridge.finish()

    The bridge opens the PortAudio stream immediately (pre-roll = one silent block)
    so the first real block arrives with minimal latency.  Internally it uses
    _ClockAlignedRingBuffer to decouple the render thread from the PortAudio
    callback, absorbing up to ~85 ms of jitter at 48 kHz / 1024-frame blocks.
    """

    _BLOCK = 1024
    _DEPTH = 8    # ~170 ms headroom at 48 kHz — enough to absorb a GC pause

    def __init__(self, samplerate: int = 48000, channels: int = 2,
                 preferred_name: "str | None" = None, volume: float = 1.0):
        import numpy as _np
        self._sr       = int(samplerate)
        self._ch       = int(channels)
        self._pref     = preferred_name
        self._vol      = float(volume)
        self._ring     = _ClockAlignedRingBuffer(block_frames=self._BLOCK,
                                                 channels=self._ch, depth=self._DEPTH)
        self._stream   = None
        self._stopped  = False
        self._lock     = _threading.Lock()
        self._np       = _np

    # --- PortAudio callback (audio thread) ------------------------------------
    def _callback(self, outdata, frames, _t, _status):
        outdata.fill(0)
        if self._ring.read(outdata):
            if self._vol != 1.0:
                self._np.multiply(outdata, self._vol, out=outdata)
        # underrun → silence (ring.read returned False)

    # --- public API (render thread) ------------------------------------------
    def start(self):
        """Open the stream immediately so pre-roll latency is hidden from the caller."""
        if not HAS_SOUNDDEVICE:
            raise RuntimeError("sounddevice unavailable")
        _first_audio_use("render-stream")
        _prepare_sos_output_route()
        idx = resolve_output_device_index(self._pref, force=False)
        try:
            phys_rate, _n_ch = _query_physical_rate(idx, self._sr, self._ch)
        except Exception:
            phys_rate = self._sr
        self._phys_rate = int(phys_rate)
        try:
            st = open_output_stream(
                samplerate=self._phys_rate, channels=self._ch,
                dtype="float32", callback=self._callback,
                blocksize=self._BLOCK, latency="low",
                preferred_name=self._pref)
            st.start()
            self._stream = st
        except Exception as exc:
            raise RuntimeError(f"RenderStreamBridge: could not open stream: {exc}") from exc

    def push(self, block: "np.ndarray") -> bool:
        """Push one rendered block into the ring buffer.  Returns False if the ring
        is full (caller should yield/sleep briefly).  Resamples from render rate
        to hardware rate when they differ."""
        if self._stopped:
            return False
        import numpy as _np
        blk = _np.asarray(block, dtype=_np.float32)
        if blk.ndim == 1:
            blk = _np.stack([blk, blk], axis=1)
        elif blk.shape[1] != self._ch:
            blk = _np.ascontiguousarray(blk[:, :self._ch])
        # Resample if render rate ≠ hardware rate
        if self._phys_rate != self._sr and blk.shape[0] > 0:
            try:
                from audio_resampling import resample_block
                blk = resample_block(blk, self._sr, self._phys_rate)
            except Exception:
                # Cheap linear interpolation fallback
                n_out = max(1, int(round(blk.shape[0] * self._phys_rate / self._sr)))
                xs = _np.linspace(0, blk.shape[0] - 1, n_out)
                ix = xs.astype(_np.int32).clip(0, blk.shape[0] - 1)
                blk = blk[ix]
        # Chop into BLOCK-sized chunks and write each
        pos = 0
        while pos < blk.shape[0]:
            chunk = blk[pos:pos + self._BLOCK]
            if chunk.shape[0] < self._BLOCK:
                # Pad last chunk to full block size
                pad = _np.zeros((self._BLOCK - chunk.shape[0], self._ch), dtype=_np.float32)
                chunk = _np.concatenate([chunk, pad], axis=0)
            self._ring.write(chunk)
            pos += self._BLOCK
        return True

    def finish(self):
        """Signal end-of-stream; drains remaining ring content then closes."""
        import numpy as _np
        # Push silence to drain (ring reads until it empties)
        silence = _np.zeros((self._BLOCK, self._ch), dtype=_np.float32)
        for _ in range(self._DEPTH + 2):
            self._ring.write(silence)
        self._stopped = True

    def stop(self):
        """Hard stop — close stream immediately without draining."""
        self._stopped = True
        with self._lock:
            st, self._stream = self._stream, None
        if st is not None:
            try:
                st.stop(); st.close()
            except Exception:
                pass

    @property
    def stopped(self) -> bool:
        return self._stopped

    @property
    def position_s(self) -> float:
        """Approximate playback position in seconds (hardware frames consumed)."""
        try:
            return float(self._stream.time) if self._stream else 0.0
        except Exception:
            return 0.0


def play_buffer(data, samplerate, preferred_name=None, blocking=False):
    """Play through the highest supported physical rate, resampling only this I/O copy."""
    if not HAS_SOUNDDEVICE:
        raise RuntimeError('sounddevice is unavailable')
    _first_audio_use('audio-preview')
    _prepare_sos_output_route()
    arr, physical_rate, idx = prepare_output_buffer(data, samplerate, preferred_name=preferred_name)
    _hardware_volume_post_open_sync()
    sd.play(arr,int(physical_rate),device=idx,blocking=bool(blocking)) if idx is not None else sd.play(arr,int(physical_rate),blocking=bool(blocking))
    return idx
