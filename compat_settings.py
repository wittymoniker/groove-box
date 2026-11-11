"""GROOVEBOX_COMPAT_SETTINGS_20261102: one saved place for the compatibility / smoothness switches.

Every switch here already existed as an environment variable that had to be set by hand. This module
stores them in a small JSON file, applies them at startup (before NumPy loads) and again when the
Compatibility dialog is applied, and reports what is in effect.

Priority: a variable set in the real environment always wins over the saved setting, so a developer or
a launch script can still override the file. Nothing here changes any DSP maths; it only chooses
buffer sizes, thread counts and which output route is used.

Smooth mode
  on    live (key / trigger) audio uses 1024-frame blocks with 'high' latency, so a busy UI or a slow
        CPU cannot starve the device. Costs about 20 ms more key latency.
  off   live audio keeps the 512-frame 'low' latency blocks.
  auto  (default) on when the machine has 4 or fewer usable logical threads (the Latitude class).
"""
import json
import os

DEFAULTS = {
    "smooth_mode": "auto",          # auto | on | off
    "worker_mode": "adaptive",      # adaptive | balanced | video | memory
    "threads": 0,                   # 0 = automatic (every usable thread plus one spare)
    "audio_blocksize": 0,           # 0 = automatic; otherwise frames per block
    "audio_latency": "auto",        # auto | low | high
    "play_all_outputs": True,       # play on every output device at once (falls back to the selected one)
    "audio_via_video_player": True, # route WAV/audio files through the video player (Latitude-safe)
    "native_voice": True,           # use the compiled voice kernel when available
    "appliance_tuning": True,       # sOS only: performance governor + priority
    "carrier_mix": 0.46,            # imported carrier video: base share of each exported frame (0.05-1.0)
    "video_tile_max": 0.18,         # operator-bound video tiles: largest width as a fraction of the frame (0.05-0.5)
    "autosave": True,               # open project is autosaved in place (main-window Autosave box)
    "auto_copy_to_drive": False,    # also copy each project save to the first connected USB / SD drive
    "export_in_worker": True,       # R32.6: exports always run in worker processes (EXPORT_SCHEDULER_R31); EXPORT_WORKER_20261102: render exports in a separate process (window stays smooth)
    "ui_scale": 100,                # DISPLAY_SCALE_20261102: text + controls, percent (applies at next launch)
    "window_scale": 100,            # DISPLAY_SCALE_20261102: main window as a percent of the usable screen area
    "audio_viz": "full",            # PLAYER_VIZ_20261107: low | full for audio-only files
    "video_makeup": "low",          # PLAYER_MAKEUP_20261107: off | low | high make-up audio for video-only files
    "makeup_generator": "drone",
    "mem_budget_pct": 0,            # R32.8 DYNAMIC_RAM: 0 = auto by tier, else 25-90 % of RAM
    "color_scheme": "normal",       # R32.8 ACCESSIBILITY: normal | high contrast | protan/deutan/tritan-safe | grayscale | warm night | inverted
    "color_scheme_outputs": False,  # also transform generated video (exports + live rig)
    "touch_keyboard": "auto",       # auto (touchscreens only) | on | off
    "no_mouse": False,              # focus outlines + keyboard navigation + Ctrl+K command palette
    "no_keyboard": False,           # on-screen keyboard always available for every field
    "break_reminder_min": 0,        # wellbeing: 0 = off, else minutes of active use
    "save_history_max": 64,         # R32.8: saves / autosaves kept (shrinks with free disk space); 0 = off
    "live_autosave": True,          # R32.8: autosave 20 s after each edit    # R32.8: drone | pulse | bed | chord (makeup_audio.py, deterministic per file)
    "swap_limit": 1.0,              # SWAP_LIMIT_20261107: 0.25 to 4.0 times RAM; default = RAM size
    "audio_rate": "auto",           # HW_RATE_20261107: auto | 44100 | 48000
    "scene_size": "auto",           # HW_SIZE_20261107: auto | 720p | 1080p | native
    "smart_process": True,          # SMART_PROCESS_20261107: unlock the 14 migratory threads
    "pin_enabled": False,           # PIN_LOCK_R31: optional 4-digit lock (salted PBKDF2 hash only)
    "pin_salt": "",
    "pin_hash": "",
    "pin_lock_on_start": True,      # ask for the PIN when the app starts (if a PIN is set)
    "pin_idle_minutes": 0,          # lock after this many idle minutes; 0 = never
    "pin_digits": 4,                # PIN length, 4-8
    "ask_session_name": False,      # SESSION_NAME_R31: ask for a session name at every startup
    "startup_chime": True,          # STARTUP_CHIME_R31: 5 s chime of every note at a random Global Convolve %
}

# Environment variables this module may set. Used to tell "set by us" from "set by the user".
_MANAGED = ("GROOVEBOX_SMOOTH", "GROOVEBOX_THREADS", "GROOVEBOX_AUDIO_BLOCKSIZE", "GROOVEBOX_AUDIO_LATENCY",
            "GROOVEBOX_OUTPUT_SINGLE", "GROOVEBOX_AUDIO_VIA_PLAYER", "GROOVEBOX_NATIVE_VOICE",
            "GROOVEBOX_APPLIANCE_TUNING", "GROOVEBOX_CARRIER_MIX", "GROOVEBOX_VIDEO_TILE_MAX", "QT_SCALE_FACTOR")
try:
    import library_tuning as _library_tuning   # GROOVEBOX_LIBRARY_TUNING_20261102
    _MANAGED = _MANAGED + tuple(_library_tuning.MANAGED)
except Exception:
    _library_tuning = None
_USER_ENV = None   # snapshot of the managed variables the real environment already defined


def settings_path():
    forced = os.environ.get("GROOVEBOX_COMPAT_SETTINGS", "").strip()
    if forced:
        return forced
    try:
        import groovebox_paths
        base = groovebox_paths.base_dir()
    except Exception:
        base = os.path.join(os.path.expanduser("~"), ".groovebox")
    return os.path.join(base, "compat-settings.json")


def _clean(raw):
    out = dict(DEFAULTS)
    if not isinstance(raw, dict):
        return out
    mode = str(raw.get("smooth_mode", out["smooth_mode"])).strip().lower()
    out["smooth_mode"] = mode if mode in ("auto", "on", "off") else "auto"
    lat = str(raw.get("audio_latency", out["audio_latency"])).strip().lower()
    out["audio_latency"] = lat if lat in ("auto", "low", "high") else "auto"
    worker_mode = str(raw.get("worker_mode", out["worker_mode"])).strip().lower()
    out["worker_mode"] = worker_mode if worker_mode in ("adaptive", "balanced", "video", "memory") else "adaptive"
    for key, lo, hi in (("threads", 0, 64), ("audio_blocksize", 0, 16384), ("ui_scale", 50, 300), ("window_scale", 50, 100)):
        try:
            v = raw.get(key, out[key])
            if key == "ui_scale" and (str(v).strip().lower() == "auto" or int(float(v)) == 0):
                out[key] = 0               # UI_SCALE_AUTO_20261102: 0 = pick from the screen size at launch
                continue
            out[key] = max(lo, min(hi, int(float(v))))
        except (TypeError, ValueError):
            pass
    for key, lo, hi in (("carrier_mix", 0.05, 1.0), ("video_tile_max", 0.05, 0.5), ("swap_limit", 0.25, 4.0)):
        try:
            out[key] = round(max(lo, min(hi, float(raw.get(key, out[key])))), 3)
        except (TypeError, ValueError):
            pass
    # COMPAT_KEYS_20261107: keep the new player settings.
    viz = str(raw.get("audio_viz", out.get("audio_viz", "full"))).strip().lower()
    out["audio_viz"] = viz if viz in ("off", "low", "full") else "full"
    gen = str(raw.get("makeup_generator", out.get("makeup_generator", "drone"))).strip().lower()
    out["makeup_generator"] = gen if gen in ("drone", "pulse", "bed", "chord") else "drone"
    rate = str(raw.get("audio_rate", out.get("audio_rate", "auto"))).strip().lower()
    out["audio_rate"] = rate if rate in ("auto", "44100", "48000") else "auto"
    size = str(raw.get("scene_size", out.get("scene_size", "auto"))).strip().lower()
    out["scene_size"] = size if size in ("auto", "720p", "1080p", "native") else "auto"
    mk = str(raw.get("video_makeup", out.get("video_makeup", "low"))).strip().lower()
    out["video_makeup"] = mk if mk in ("off", "low", "high") else "low"
    try:
        _mb = int(raw.get("mem_budget_pct", out.get("mem_budget_pct", 0)) or 0)
        out["mem_budget_pct"] = 0 if _mb <= 0 else max(25, min(90, _mb))
    except Exception:
        out["mem_budget_pct"] = 0
    import accessibility as _a11y
    cs_ = str(raw.get("color_scheme", out.get("color_scheme", "normal")))
    out["color_scheme"] = cs_ if cs_ in _a11y.SCHEMES else "normal"
    tk = str(raw.get("touch_keyboard", out.get("touch_keyboard", "auto"))).lower()
    out["touch_keyboard"] = tk if tk in ("auto", "on", "off") else "auto"
    for _k in ("color_scheme_outputs", "no_mouse", "no_keyboard"):
        if _k in raw:
            out[_k] = bool(raw[_k])
    try:
        out["break_reminder_min"] = max(0, min(240, int(raw.get("break_reminder_min", out.get("break_reminder_min", 0)) or 0)))
    except Exception:
        out["break_reminder_min"] = 0
    # R31: smart_process was missing here, so turning it off never persisted.
    for key in ("autosave", "auto_copy_to_drive", "play_all_outputs", "audio_via_video_player", "native_voice",
                "appliance_tuning", "export_in_worker", "smart_process", "pin_enabled", "pin_lock_on_start",
                "ask_session_name", "startup_chime"):
        if key in raw:
            out[key] = bool(raw[key])
    try:
        out["pin_idle_minutes"] = max(0, min(240, int(raw.get("pin_idle_minutes", 0) or 0)))
        out["pin_digits"] = max(4, min(8, int(raw.get("pin_digits", 4) or 4)))
    except (TypeError, ValueError):
        pass
    for key in ("pin_salt", "pin_hash"):
        v = str(raw.get(key, "") or "")
        out[key] = v if all(c in "0123456789abcdef" for c in v) and len(v) <= 128 else ""
    if not (out["pin_salt"] and out["pin_hash"]):
        out["pin_enabled"] = False
    return out


def boot_overrides(cmdline_path="/proc/cmdline"):
    """Options chosen in the Limine boot menu (kernel command line: sos.ui_scale=125 sos.window_scale=90 …).

    GROOVEBOX_R32_SOS_SETTINGS_20261109: every ``sos.<key>=<value>`` that names a compatibility
    setting is honoured (smooth_mode, threads, audio_rate, scene_size, play_all_outputs,
    startup_chime, worker_mode, audio_latency, native_voice, smart_process, background, update).
    """
    try:
        import sos_system_settings as _sss
        with open(cmdline_path, encoding="utf-8", errors="replace") as _f:
            _ov = _sss.parse_cmdline(_f.read())
        if _ov:
            _bg = _ov.pop("background", None)
            if _bg:
                try:
                    _sss.set_background(_bg)
                except Exception:
                    pass
            _ov.pop("update", None)
            return _ov
    except Exception:
        pass
    out = {}
    try:
        with open(cmdline_path, "r", encoding="utf-8", errors="replace") as f:
            words = f.read().split()
    except OSError:
        return out
    for word in words:
        for opt, key in (("sos.ui_scale=", "ui_scale"), ("sos.window_scale=", "window_scale")):
            if word.startswith(opt):
                try:
                    val = word[len(opt):]
                    out[key] = 0 if (key == "ui_scale" and val.lower() == "auto") else int(float(val))
                except ValueError:
                    pass
    return out


def screen_pixels(drm_root="/sys/class/drm"):
    """(width, height) of the largest connected display from the kernel's DRM mode lists, or None.

    UI_SCALE_AUTO_20261102: read before Qt starts (QT_SCALE_FACTOR must be set before the application exists).
    The first mode of a connector is its preferred (native) mode.
    """
    best = None
    try:
        for name in sorted(os.listdir(drm_root)):
            base = os.path.join(drm_root, name)
            try:
                with open(os.path.join(base, "status"), "r") as f:
                    if f.read().strip() != "connected":
                        continue
                with open(os.path.join(base, "modes"), "r") as f:
                    first = f.readline().strip()
                w, h = (int(x) for x in first.split("x")[:2])
            except (OSError, ValueError):
                continue
            if best is None or w * h > best[0] * best[1]:
                best = (w, h)
    except OSError:
        return None
    return best


def auto_ui_scale(pixels=None):
    """UI scale percent for a screen of this size: small panels stay compact, 4K gets large text."""
    px = pixels if pixels is not None else screen_pixels()
    if not px:
        return 100
    short = min(px)
    for limit, pct in ((2000, 175), (1500, 140), (1200, 115), (700, 100), (560, 90)):
        if short >= limit:
            return pct
    return 80


def load():
    try:
        with open(settings_path(), "r", encoding="utf-8") as f:
            data = _clean(json.load(f))
    except Exception:
        data = dict(DEFAULTS)
    boot = boot_overrides()          # a boot-menu choice wins over the saved value for this session only
    if boot:
        data = _clean({**data, **boot})
    return data


def scaled_rect(x, y, w, h, percent):
    """The usable screen rectangle shrunk to ``percent`` (50-100) of its size and centred in it."""
    pct = max(50, min(100, int(percent))) / 100.0
    nw, nh = max(1, int(round(w * pct))), max(1, int(round(h * pct)))
    return int(x + (w - nw) // 2), int(y + (h - nh) // 2), nw, nh


def save(settings):
    data = _clean(settings)
    path = settings_path()
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.replace(tmp, path)
        return True
    except Exception:
        return False


def usable_cores():
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except Exception:
        return max(1, int(os.cpu_count() or 1))


def smooth_effective(settings, cores=None):
    mode = _clean(settings)["smooth_mode"]
    if mode == "on":
        return True
    if mode == "off":
        return False
    return (usable_cores() if cores is None else int(cores)) <= 4


def effective_ui_scale(settings):
    """The percent that will really be used (resolves Auto)."""
    v = _clean(settings)["ui_scale"]
    return auto_ui_scale() if v == 0 else v


def env_for(settings, cores=None):
    """{variable: value or None}; None means 'leave unset'."""
    s = _clean(settings)
    return {
        "GROOVEBOX_SMOOTH": "1" if smooth_effective(s, cores) else "0",
        "GROOVEBOX_THREADS": str(s["threads"]) if s["threads"] > 0 else None,
        "GROOVEBOX_WORKERS": {"adaptive": None, "balanced": "14", "video": "16", "memory": "8"}[s["worker_mode"]],
        "GROOVEBOX_AUDIO_BLOCKSIZE": str(s["audio_blocksize"]) if s["audio_blocksize"] > 0 else None,
        "GROOVEBOX_AUDIO_LATENCY": s["audio_latency"] if s["audio_latency"] in ("low", "high") else None,
        "GROOVEBOX_OUTPUT_SINGLE": None if s["play_all_outputs"] else "1",
        "GROOVEBOX_AUDIO_VIA_PLAYER": None if s["audio_via_video_player"] else "0",
        "GROOVEBOX_NATIVE_VOICE": None if s["native_voice"] else "off",
        "GROOVEBOX_APPLIANCE_TUNING": None if s["appliance_tuning"] else "0",
        "GROOVEBOX_CARRIER_MIX": None if abs(s["carrier_mix"] - 0.46) < 1e-6 else str(s["carrier_mix"]),
        "GROOVEBOX_VIDEO_TILE_MAX": None if abs(s["video_tile_max"] - 0.18) < 1e-6 else str(s["video_tile_max"]),
        "QT_SCALE_FACTOR": None if effective_ui_scale(s) == 100 else f"{effective_ui_scale(s) / 100.0:g}",
    }


def apply_env(settings=None):
    """Apply the saved (or given) settings to this process's environment. Safe to call repeatedly."""
    global _USER_ENV
    if _USER_ENV is None:
        _USER_ENV = {k: os.environ[k] for k in _MANAGED if k in os.environ}
    wanted = env_for(load() if settings is None else settings)
    for key, value in wanted.items():
        if key in _USER_ENV:
            continue                       # the real environment wins
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    # Low-level libraries (BLAS / OpenMP / encoder) follow the same Smooth level.
    if _library_tuning is not None:
        try:
            _library_tuning.apply(smooth_effective(load() if settings is None else settings), _USER_ENV)
        except Exception:
            pass
    return wanted


def describe(settings=None):
    """Plain-language lines for the dialog / logs: what is in effect right now."""
    s = _clean(load() if settings is None else settings)
    cores = usable_cores()
    lines = [f"Usable logical threads: {cores}"]
    smooth = smooth_effective(s)
    lines.append(f"Smooth mode: {s['smooth_mode']} -> {'ON' if smooth else 'off'} "
                 f"(live audio {'1024-frame, high latency' if smooth else '512-frame, low latency'})")
    try:
        from audio_os_backend import stream_tuning
        for purpose in ("live", "transport", "file"):
            blk, lat = stream_tuning(purpose)
            lines.append(f"  {purpose}: {blk or 'auto'} frames, latency {lat}")
    except Exception as exc:
        lines.append(f"  (stream tuning unavailable: {exc})")
    try:
        import thread_budget
        lines.append(f"Threads: maths {thread_budget.compute_threads()}, helper pools {thread_budget.lane_workers()}")
    except Exception:
        pass
    if _library_tuning is not None:
        try:
            lines.append(_library_tuning.describe(smooth))
        except Exception:
            pass
    lines.append("Startup: the startup screen is always shown")
    lines.append(f"Display: UI scale {'Auto (' + str(effective_ui_scale(s)) + '%)' if s['ui_scale'] == 0 else str(s['ui_scale']) + '%'} (next launch) · window {s['window_scale']}% of the screen"
                 + (" · set by the boot menu" if boot_overrides() else ""))
    lines.append(f"Video: carrier mix {s['carrier_mix']:.2f} of each frame; instrument tiles up to {s['video_tile_max']*100:.0f}% of frame width")
    lines.append("Autosave: " + ("on (open project is saved in place)" if s["autosave"] else "OFF"))
    lines.append("Saves also copied to a connected drive: " + ("yes" if s["auto_copy_to_drive"] else "no"))
    lines.append("Export rendering: " + ("separate process (main window stays smooth)" if s["export_in_worker"] else "inside the main window"))
    lines.append("Output: " + ("every device at once, with fallbacks" if s["play_all_outputs"] else "selected device only"))
    lines.append("Audio files: " + ("through the video player" if s["audio_via_video_player"] else "built-in player"))
    lines.append("Voice kernel: " + ("compiled when available" if s["native_voice"] else "NumPy reference"))
    held = [k for k in _MANAGED if _USER_ENV and k in _USER_ENV]
    if held:
        lines.append("Set in the environment (overrides the saved value): " + ", ".join(held))
    return lines
