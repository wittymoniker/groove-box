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
import threading

try:
    from groovebox_runtime.default_migrations import migrate_untouched_defaults
except Exception:   # R99: a missing / stale runtime package must never take Settings and Compatibility down
    def migrate_untouched_defaults(settings, policies, *, touched=(), canonical_owned=()):
        result = dict(settings); touched, canonical_owned = set(touched or ()), set(canonical_owned or ())
        changed = []
        for key, policy in dict(policies or {}).items():
            if key in touched or key in canonical_owned or key not in result or not isinstance(policy, dict):
                continue
            if "from" in policy and "to" in policy and result[key] == policy["from"] and policy["from"] != policy["to"]:
                result[key] = policy["to"]; changed.append({"key": str(key), "from": policy["from"], "to": policy["to"]})
        return result, {"changed": changed, "count": len(changed), "sha256": ""}

_SAVE_LOCK = threading.RLock()     # SETTINGS_REPAIR_20261112: one writer at a time (GUI, workers, timers)

DEFAULTS = {
    "external_app_share": 0.19758,      # R99: external apps / user programs stay strictly under this share of CPU and RAM
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
    "equation_audio_save": False,   # R120: opt-in lossless float32 .eqaudio sidecar on explicit project saves (25 MiB cap)
    "auto_copy_to_drive": False,    # also copy each project save to the first connected USB / SD drive
    "export_in_worker": True,       # R32.6: exports always run in worker processes (EXPORT_SCHEDULER_R31); EXPORT_WORKER_20261102: render exports in a separate process (window stays smooth)
    "ui_scale": 0,                  # R97: Auto resolves from connected display dimensions; explicit percent still supported
    "window_scale": 100,            # DISPLAY_SCALE_20261102: main window as a percent of the usable screen area
    "audio_viz": "full",            # PLAYER_VIZ_20261107: low | full for audio-only files
    "video_makeup": "low",          # PLAYER_MAKEUP_20261107: off | low | high make-up audio for video-only files
    "makeup_generator": "drone",
    "mem_budget_pct": 0,            # R32.8 DYNAMIC_RAM: 0 = auto by tier, else 25-90 % of RAM
    "workspace_pane_color": "blue_gray", # shared background for all three primary workspace panes
    "color_scheme": "normal",       # R32.8 ACCESSIBILITY: normal | high contrast | protan/deutan/tritan-safe | grayscale | warm night | inverted
    "color_scheme_outputs": False,  # also transform generated video (exports + live rig)
    "touch_keyboard": "auto",       # auto (touchscreens only) | on | off
    "no_mouse": False,              # focus outlines + keyboard navigation + Ctrl+K command palette
    "no_keyboard": False,           # on-screen keyboard always available for every field
    "break_reminder_min": 0,        # wellbeing: 0 = off, else minutes of active use
    "save_history_max": 64,         # R32.8: saves / autosaves kept (shrinks with free disk space); 0 = off
    "live_autosave": True,          # R32.8: autosave 20 s after each edit
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
    "quick_rack_side": "top",       # BAR_SIDE_20261112: top | left | right | bottom
    "projects_bar_side": "top",
    "deck_side": "top",
    "battery_warn_pct": 20,         # status notice when the battery falls to this level
    "battery_critical_pct": 8,      # autosave (and optionally export) when it falls to this level
    "battery_action": "autosave+export",   # notify | autosave | autosave+export
    "wait_factor": 1.0,             # scales how long hardware checks keep trying (0.25×–4×); waits end as soon as ready             # the Groovebox deck: top | left | right | bottom (right-click the deck)
    "thread_quality": "balanced",   # balanced | max | compatibility
    "compat_profile": "auto",       # auto | latitude | tablet | desktop | studio
    # SETTINGS_REPAIR_20261112: these keys were read/written elsewhere but missing here, so _clean()
    # raised KeyError('party_intensity') on every load/save/describe and every saved setting was ignored.
    "party_mode": True,             # Party Mode (main-window 🎉 toggle + System Settings): ON by default. It budgets its
                                    # own UI-thread share (adaptive frame rate) and pre-warms worker pools while idle.
    "party_intensity": 50.0,        # 0-100 % (float); PARTY_DEFAULT_R7: default level 0.5 (was 0.19758)
    "party_sounds": True,           # PARTY_SOUND_20261112: Party Mode is the UI sound
    "party_feel": "classic",        # PARTY_FEEL_R8: calm | classic | rave
    "emoji_labels": True,           # EMOJI_UI_R7: emoji on buttons, tabs, titles and labels
    "party_defaults_r6": True,      # one-time migration marker (older saves get Party ON at the default)
    "party_defaults_r7": True,      # PARTY_DEFAULT_R7: an untouched 19.758 % (the old default) becomes 50 % once
    "party_defaults_r33": True,     # one-time migration marker
    "party_defaults_final": True,   # one-time: Party Mode back ON by default (now self-throttling)
    "noisy_exports": False,
    "play_export_when_done": True,  # load a finished export into the main window meters
    "hardware_class": "auto",       # auto | tablet | laptop | desktop (System Settings profile)
    "math_background_enabled": True,  # window backgrounds ON by default (rendered off the UI thread)
    "window_background_image": "",    # '' = mathematical field; else a PNG / JPG / GIF / WebP path for every window
    "bg_defaults_final": True,        # one-time: backgrounds ON for settings saved while they were opt-in
    # DEV_OVERLAY_20261112: the developer overlay is never enabled at launch (Performance → 🧪 Dev Overlay, per
    # session). These decide when an enabled overlay falls back to the installed core by itself.
    "dev_overlay_rollback": "auto",     # auto (thermal / RAM / frozen UI / errors) | manual
    "dev_overlay_max_temp_c": 90,       # sustained CPU/SoC temperature that triggers rollback
    "dev_overlay_min_free_mb": 512,     # sustained free RAM floor
    "dev_overlay_stall_s": 3.0,         # a UI gap this long counts as a freeze (2 freezes → rollback)
    "dev_overlay_max_errors": 3,        # errors raised from overlay code before rollback
    "dev_overlay_script_timeout_s": 600,  # scratchpad script time limit
    # GROOVEBOX_R123_MOUSE_TRACER_20261119: subtle pointer trail, ON by default (System Settings ·
    # Settings/Compat → Mouse tracer). Works on Wayland: drawn inside Groovebox windows only.
    "mouse_tracer": True,
    "mouse_tracer_mode": "trail",       # trail | ring | trail+ring
    "mouse_tracer_length": 48,          # points kept in the trail (4-256)
    "mouse_tracer_fade_ms": 600,        # how long a point stays visible (100-5000 ms)
    "mouse_tracer_width": 4,            # px at the head (1-24)
    "mouse_tracer_color": "#4fd1ff",    # #rrggbb
    "mouse_tracer_clicks": True,        # brief ripple on mouse press
    # GROOVEBOX_R123_COMPAT_SCROLL_20261119 (window_scroll.py): windows = every tool window scrolls
    # when its content does not fit (WINDOW_SCROLL_R7 behaviour) · windows+main = compatibility mode,
    # the main window also gets one scroll area across all its panels · off = no wrapping.
    "scroll_panels": "windows",
    # Internal migration provenance. These keys are persisted but never shown as UI controls.
    "_user_touched_keys": [],
    "_default_migration_audit": {"count": 0, "sha256": ""},
}

# Environment variables this module may set. Used to tell "set by us" from "set by the user".
_MANAGED = ("GROOVEBOX_SMOOTH", "GROOVEBOX_THREADS", "GROOVEBOX_AUDIO_BLOCKSIZE", "GROOVEBOX_AUDIO_LATENCY",
            "GROOVEBOX_OUTPUT_SINGLE", "GROOVEBOX_AUDIO_VIA_PLAYER", "GROOVEBOX_NATIVE_VOICE",
            "GROOVEBOX_APPLIANCE_TUNING", "GROOVEBOX_CARRIER_MIX", "GROOVEBOX_VIDEO_TILE_MAX", "QT_SCALE_FACTOR",
            "GROOVEBOX_WORKERS")
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
    touched_raw = raw.get("_user_touched_keys", ())
    if isinstance(touched_raw, (list, tuple, set)):
        out["_user_touched_keys"] = sorted({str(x) for x in touched_raw if str(x) in DEFAULTS and not str(x).startswith("_")})
    mode = str(raw.get("smooth_mode", out["smooth_mode"])).strip().lower()
    out["smooth_mode"] = mode if mode in ("auto", "on", "off") else "auto"
    lat = str(raw.get("audio_latency", out["audio_latency"])).strip().lower()
    out["audio_latency"] = lat if lat in ("auto", "low", "high") else "auto"
    worker_mode = str(raw.get("worker_mode", out["worker_mode"])).strip().lower()
    out["worker_mode"] = worker_mode if worker_mode in ("adaptive", "balanced", "video", "memory") else "adaptive"
    party_feel = str(raw.get("party_feel", out["party_feel"])).strip().lower()
    out["party_feel"] = party_feel if party_feel in ("calm", "classic", "rave") else DEFAULTS["party_feel"]
    for key, allowed in (("quick_rack_side", ("top", "left", "right", "bottom")),
                         ("projects_bar_side", ("top", "left", "right", "bottom")),
                         ("deck_side", ("top", "left", "right", "bottom")),
                         ("thread_quality", ("balanced", "max", "compatibility")),
                         ("compat_profile", ("auto", "latitude", "tablet", "desktop", "studio")),
                         ("hardware_class", ("auto", "tablet", "laptop", "desktop")),
                         ("dev_overlay_rollback", ("auto", "manual"))):
        val = str(raw.get(key, out[key])).strip().lower()
        out[key] = val if val in allowed else out[key]
    for key, lo, hi in (("threads", 0, 64), ("audio_blocksize", 0, 16384), ("ui_scale", 50, 300), ("window_scale", 50, 100),
                         ("save_history_max", 0, 4096),
                         ("dev_overlay_max_temp_c", 50, 120), ("dev_overlay_min_free_mb", 64, 65536),
                         ("dev_overlay_max_errors", 1, 1000), ("dev_overlay_script_timeout_s", 5, 86400)):
        try:
            v = raw.get(key, out.get(key, DEFAULTS.get(key, lo)))
            if key == "ui_scale" and (str(v).strip().lower() == "auto" or int(float(v)) == 0):
                out[key] = 0               # UI_SCALE_AUTO_20261102: 0 = pick from the screen size at launch
                continue
            out[key] = max(lo, min(hi, int(float(v))))
        except (TypeError, ValueError):
            pass
    try:                                   # PARTY_DEFAULT_R6: float level, 0.001 % resolution
        out["party_intensity"] = round(max(0.0, min(100.0, float(raw.get("party_intensity", out["party_intensity"])))), 3)
    except (TypeError, ValueError):
        out["party_intensity"] = DEFAULTS["party_intensity"]
    for key, lo, hi in (("carrier_mix", 0.05, 1.0), ("video_tile_max", 0.05, 0.5), ("swap_limit", 0.25, 4.0),
                        ("dev_overlay_stall_s", 0.5, 60.0)):
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
    try:
        import accessibility as _a11y
        _schemes = tuple(_a11y.SCHEMES)
    except Exception:          # settings must load even if the accessibility module is missing/broken
        _schemes = ("normal",)
    pane_color = str(raw.get("workspace_pane_color", out.get("workspace_pane_color", "blue_gray"))).strip().lower()
    out["workspace_pane_color"] = pane_color if pane_color in ("blue_gray", "slate", "graphite", "midnight") else "blue_gray"
    cs_ = str(raw.get("color_scheme", out.get("color_scheme", "normal")))
    out["color_scheme"] = cs_ if cs_ in _schemes else "normal"
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
                "ask_session_name", "startup_chime", "noisy_exports", "play_export_when_done", "party_mode", "party_sounds", "emoji_labels",
                "live_autosave", "color_scheme_outputs", "no_mouse", "no_keyboard", "equation_audio_save"):
        if key in raw:
            out[key] = bool(raw[key])
    for key, lo, hi, dflt in (("pin_idle_minutes", 0, 240, 0), ("pin_digits", 4, 8, 4)):
        try:
            out[key] = max(lo, min(hi, int(float(raw.get(key, dflt) or dflt))))
        except (TypeError, ValueError):
            out[key] = dflt
    for key in ("pin_salt", "pin_hash"):
        v = str(raw.get(key, "") or "")
        out[key] = v if all(c in "0123456789abcdef" for c in v) and len(v) <= 128 else ""
    if not (out["pin_salt"] and out["pin_hash"]):
        out["pin_enabled"] = False
    if not raw.get("party_defaults_r6", False):          # PARTY_DEFAULT_R6: saved before R6 → Party ON at the default
        out["party_mode"] = True
        out["party_intensity"] = DEFAULTS["party_intensity"]
        out["party_sounds"] = True
    out["party_defaults_r6"] = True
    if not raw.get("party_defaults_r7", False):          # PARTY_DEFAULT_R7: the old default (untouched) → 50 %
        if abs(float(out["party_intensity"]) - 19.758) < 1e-9:
            out["party_intensity"] = DEFAULTS["party_intensity"]
    out["party_defaults_r7"] = True
    out["party_defaults_r33"] = True
    _bgi = str(raw.get("window_background_image", "") or "")
    out["window_background_image"] = _bgi if len(_bgi) < 4096 and "\x00" not in _bgi else ""
    if "math_background_enabled" in raw:
        out["math_background_enabled"] = bool(raw["math_background_enabled"])
    for _bk, _lo, _hi in (("battery_warn_pct", 5, 60), ("battery_critical_pct", 2, 30)):
        try:
            out[_bk] = int(max(_lo, min(_hi, int(raw.get(_bk, out[_bk])))))
        except (TypeError, ValueError):
            pass
    _ba = str(raw.get("battery_action", out.get("battery_action", "autosave+export")))
    out["battery_action"] = _ba if _ba in ("notify", "autosave", "autosave+export") else "autosave+export"
    try:
        out["wait_factor"] = round(max(0.25, min(4.0, float(raw.get("wait_factor", out.get("wait_factor", 1.0))))), 3)
    except (TypeError, ValueError):
        out["wait_factor"] = 1.0
    if not raw.get("bg_defaults_final", False):
        out["math_background_enabled"] = True
    out["bg_defaults_final"] = True
    # New profiles already inherit DEFAULTS["party_mode"] == True. An
    # existing profile with party_defaults_r6=True has crossed the legacy
    # migration boundary, so preserve its explicit saved False as well as True.
    out["party_defaults_final"] = True

    # R123: mouse tracer + compatibility scroll.
    out["mouse_tracer"] = bool(raw.get("mouse_tracer", out["mouse_tracer"]))
    out["mouse_tracer_clicks"] = bool(raw.get("mouse_tracer_clicks", out["mouse_tracer_clicks"]))
    _m = str(raw.get("mouse_tracer_mode", out["mouse_tracer_mode"])).strip().lower()
    out["mouse_tracer_mode"] = _m if _m in ("trail", "ring", "trail+ring") else DEFAULTS["mouse_tracer_mode"]
    for key, lo, hi in (("mouse_tracer_length", 4, 256), ("mouse_tracer_fade_ms", 100, 5000), ("mouse_tracer_width", 1, 24)):
        try:
            out[key] = max(lo, min(hi, int(float(raw.get(key, out[key])))))
        except (TypeError, ValueError):
            out[key] = DEFAULTS[key]
    _c = str(raw.get("mouse_tracer_color", out["mouse_tracer_color"])).strip()
    out["mouse_tracer_color"] = _c.lower() if (len(_c) == 7 and _c[0] == "#" and all(ch in "0123456789abcdefABCDEF" for ch in _c[1:])) else DEFAULTS["mouse_tracer_color"]
    _sp = str(raw.get("scroll_panels", out["scroll_panels"])).strip().lower()
    _sp = {"auto": "windows", "always": "windows+main", "main": "windows+main"}.get(_sp, _sp)
    out["scroll_panels"] = _sp if _sp in ("off", "windows", "windows+main") else DEFAULTS["scroll_panels"]

    # R97: UI scaling now defaults to the existing display-aware Auto mode.
    # Migrate only the exact former factory default (100%), and never rewrite
    # a key marked by an explicit save/update as user-touched.  Audio latency,
    # block size, worker counts, and canonical-owned controls remain adaptive
    # or source-owned; no hardware-independent numeric guesses are applied.
    out, audit = migrate_untouched_defaults(
        out,
        {"ui_scale": {
            "from": 100, "to": 0,
            "rationale": "Use existing screen-resolution-aware Auto scaling; explicit user scales remain unchanged.",
        }},
        touched=out.get("_user_touched_keys", ()),
        canonical_owned=(),
    )
    out["_default_migration_audit"] = {"count": audit["count"], "sha256": audit["sha256"]}
    return out


_BOOT_CACHE = {}


def boot_overrides(cmdline_path="/proc/cmdline"):
    """Cached per process: the kernel command line cannot change while we run, and the uncached
    version re-launched swaybg (set_background) on EVERY settings load."""
    if cmdline_path not in _BOOT_CACHE:
        _BOOT_CACHE[cmdline_path] = _boot_overrides_uncached(cmdline_path)
    return dict(_BOOT_CACHE[cmdline_path])


def _boot_overrides_uncached(cmdline_path="/proc/cmdline"):
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


_FILE_CACHE = {}


def _load_file():
    """Cleaned saved settings. Cached by (path, mtime, size): UI code calls load() many times per second, and each
    uncached call re-read and re-validated the JSON file on the UI thread. A save() changes the mtime → re-read."""
    try:
        _p = settings_path()
        _st = os.stat(_p)
        _key = (_p, _st.st_mtime_ns, _st.st_size)
        _hit = _FILE_CACHE.get("v")
        if _hit is not None and _hit[0] == _key:
            return dict(_hit[1])
    except OSError:
        _key = None
    out = _load_file_uncached()
    if _key is not None:
        _FILE_CACHE["v"] = (_key, dict(out))
    return out


def _load_file_uncached():
    try:
        raw = __import__("safe_io").load_json(settings_path(), encoding="utf-8")
    except FileNotFoundError:
        return dict(DEFAULTS)
    except Exception as exc:
        # Corrupt file: keep a copy for diagnosis instead of silently overwriting it on the next save.
        try:
            os.replace(settings_path(), settings_path() + ".corrupt")
        except Exception:
            pass
        print(f"[compat_settings] unreadable settings file ({exc}); using defaults")
        return dict(DEFAULTS)
    try:
        return _clean(raw)
    except Exception as exc:
        print(f"[compat_settings] settings could not be cleaned ({exc!r}); using defaults")
        return dict(DEFAULTS)


def load():
    """Saved settings (+ this boot's menu overrides). Never raises."""
    data = _load_file()
    boot = boot_overrides()          # a boot-menu choice wins over the saved value for this session only
    if boot:
        try:
            data = _clean({**data, **boot})
        except Exception:
            pass
    return data


def load_saved():
    """Saved settings WITHOUT boot overrides: use this as the base when writing, so a one-session
    boot-menu choice is not persisted by an unrelated save."""
    return _load_file()


def update(**changes):
    """Atomic read-modify-write of a few keys (thread-safe). Returns the saved dict, or None on failure."""
    with _SAVE_LOCK:
        cur = _load_file()
        cur.update(changes)
        touched = set(cur.get("_user_touched_keys", ()))
        touched.update(str(key) for key in changes if key in DEFAULTS and not str(key).startswith("_"))
        cur["_user_touched_keys"] = sorted(touched)
        return cur if save(cur) else None


def scaled_rect(x, y, w, h, percent):
    """The usable screen rectangle shrunk to ``percent`` (50-100) of its size and centred in it."""
    pct = max(50, min(100, int(percent))) / 100.0
    nw, nh = max(1, int(round(w * pct))), max(1, int(round(h * pct)))
    return int(x + (w - nw) // 2), int(y + (h - nh) // 2), nw, nh


def save(settings):
    """Validate and atomically write. Returns True/False; never raises."""
    try:
        data = _clean(settings)
    except Exception as exc:
        print(f"[compat_settings] refusing to save invalid settings: {exc!r}")
        return False
    path = settings_path()
    with _SAVE_LOCK:
        # Preserve explicitly touched fields across ordinary whole-dialog saves.
        # Compare against the normalized previous snapshot, so a one-time default
        # migration itself does not make an unrelated field appear user-edited.
        try:
            old_raw = __import__("safe_io").load_json(path, encoding="utf-8")
            old_clean = _clean(old_raw)
        except Exception:
            old_clean = None
        touched = set(data.get("_user_touched_keys", ()))
        if isinstance(old_clean, dict):
            for key in DEFAULTS:
                if key.startswith("_") or key not in settings:
                    continue
                if data.get(key) != old_clean.get(key):
                    touched.add(key)
        data["_user_touched_keys"] = sorted(touched)
        tmp = "%s.%d.%d.tmp" % (path, os.getpid(), threading.get_ident())
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass
            os.replace(tmp, path)
            return True
        except Exception as exc:
            print(f"[compat_settings] could not write {path}: {exc}")
            try:
                os.remove(tmp)
            except OSError:
                pass
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
    quality = s.get("thread_quality", "balanced")
    if quality == "max":
        s = dict(s); s["smooth_mode"] = "off"; s["audio_latency"] = "low"
    elif quality == "compatibility":
        s = dict(s); s["smooth_mode"] = "on"; s["audio_latency"] = "high"
        if s["threads"] == 0:
            s["threads"] = max(2, (cores or usable_cores()) // 2)
    return {
        "GROOVEBOX_SMOOTH": "1" if smooth_effective(s, cores) else "0",
        "GROOVEBOX_THREADS": str(s["threads"]) if s["threads"] > 0 else None,
        # POOL_CEILING_20261112: the shared pool ceiling (thread_budget.lane_workers). The old values
        # (14/16/8) were always clipped to 4, so worker_mode did nothing. Now: memory = 2, adaptive = auto (4),
        # balanced = 6, video = 8 -- always further bounded by real cores minus GUI/audio/OS headroom.
        "GROOVEBOX_WORKERS": {"adaptive": None, "balanced": "6", "video": "8", "memory": "2"}[s["worker_mode"]],
        "GROOVEBOX_AUDIO_BLOCKSIZE": str(s["audio_blocksize"]) if s["audio_blocksize"] > 0 else None,
        "GROOVEBOX_AUDIO_LATENCY": s["audio_latency"] if s["audio_latency"] in ("low", "high") else None,
        "GROOVEBOX_OUTPUT_SINGLE": None if s["play_all_outputs"] else "1",
        "GROOVEBOX_AUDIO_VIA_PLAYER": None if s["audio_via_video_player"] else "0",
        "GROOVEBOX_NATIVE_VOICE": None if s["native_voice"] else "off",
        "GROOVEBOX_APPLIANCE_TUNING": None if s["appliance_tuning"] else "0",
        "GROOVEBOX_CARRIER_MIX": None if abs(s["carrier_mix"] - 0.46) < 1e-6 else str(s["carrier_mix"]),
        "GROOVEBOX_VIDEO_TILE_MAX": None if abs(s["video_tile_max"] - 0.18) < 1e-6 else str(s["video_tile_max"]),
        # UI_SCALE_SNAP_R7: fractional QT_SCALE_FACTOR (e.g. 0.66) breaks some startup layouts
        # (clipped buttons, zero-height rows). Snap to 5% and prefer QT_SCALE_FACTOR only for
        # values that Qt handles cleanly; extreme under-scale uses font DPI instead via env below.
        "QT_SCALE_FACTOR": (None if effective_ui_scale(s) == 100 else f"{(round(effective_ui_scale(s) / 5) * 5) / 100.0:g}"),
    }


def apply_env(settings=None):
    """Apply the saved (or given) settings to this process's environment. Safe to call repeatedly."""
    global _USER_ENV
    if _USER_ENV is None:
        _USER_ENV = {k: os.environ[k] for k in _MANAGED if k in os.environ}
    settings = load() if settings is None else settings
    try:
        os.environ["GROOVEBOX_WAIT_PCT"] = str(int(round(100 * float(settings.get("wait_factor", 1.0)))))
    except Exception:
        pass
    try:
        wanted = env_for(settings)
    except Exception as exc:
        print(f"[compat_settings] apply_env fell back to defaults: {exc!r}")
        wanted = env_for(dict(DEFAULTS))
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
            _library_tuning.apply(smooth_effective(settings), _USER_ENV)
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
        lines.append(f"Threads: maths {thread_budget.compute_threads()} (logical, up to 8), helper pools {thread_budget.lane_workers()}")
        lines.append("Dell Latitude 4c/8t: 8 maths threads recommended; 4 is the physical core count only.")
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
    lines.append("Party mode: " + (f"ON at {float(s['party_intensity']):.3f}%" + (" + sounds" if s.get("party_sounds", True) else "") if s["party_mode"] else "off"))
    lines.append(f"Worker mode: {s['worker_mode']} · thread quality {s['thread_quality']}")
    held = [k for k in _MANAGED if _USER_ENV and k in _USER_ENV]
    if held:
        lines.append("Set in the environment (overrides the saved value): " + ", ".join(held))
    return lines


def hardware_class():
    """Best-effort class: tablet, laptop, or desktop."""
    cores = usable_cores()
    try:
        import power_profile as pp
        info = pp.summary_line() or ""
    except Exception:
        info = ""
    # A battery present usually means laptop or tablet.
    bat = os.path.isdir("/sys/class/power_supply") and any(
        "BAT" in n for n in os.listdir("/sys/class/power_supply")) if os.path.isdir("/sys/class/power_supply") else False
    if cores <= 4 and bat:
        return "tablet"
    if bat or cores <= 8:
        return "laptop"
    return "desktop"


HARDWARE_PROFILES = {
    "tablet": {"smooth_mode": "on", "threads": 2, "scene_size": "720p", "audio_latency": "high",
               "audio_blocksize": 1024, "worker_mode": "memory", "ui_scale": 125, "play_all_outputs": False},
    "laptop": {"smooth_mode": "auto", "threads": 0, "scene_size": "720p", "audio_latency": "auto",
               "audio_blocksize": 0, "worker_mode": "adaptive", "ui_scale": 100, "play_all_outputs": True},
    "desktop": {"smooth_mode": "off", "threads": 0, "scene_size": "1080p", "audio_latency": "low",
                "audio_blocksize": 512, "worker_mode": "balanced", "ui_scale": 100, "play_all_outputs": True},
}


def apply_hardware_class(kind=None):
    """Apply a hardware profile. kind None uses the detected class."""
    requested = kind or "auto"
    kind = kind if kind in HARDWARE_PROFILES else hardware_class()
    prof = dict(HARDWARE_PROFILES.get(kind) or HARDWARE_PROFILES["laptop"])
    with _SAVE_LOCK:
        cur = load_saved()
        cur.update(prof)
        cur["hardware_class"] = requested      # remember "auto" as auto, not as the class it resolved to
        save(cur)
    apply_env(cur)
    return kind, prof


def fit_dialog_to_screen(dlg, width_frac=0.55, height_frac=0.75, min_w=480, min_h=520):
    """Clamp a tool/startup dialog to the active screen's usable geometry.

    The previous implementation enforced 480×520 minimums even when the
    Latitude's available logical screen area was smaller. That pushed dialogs
    behind the panel and made their bottom controls appear missing. Minimums
    are now advisory and are always clamped to the actual work area.
    """
    try:
        from PyQt6.QtWidgets import QApplication
        screen = None
        try:
            screen = dlg.screen() or QApplication.primaryScreen()
        except Exception:
            screen = QApplication.primaryScreen()
        if screen is None:
            w = max(320, int(dlg.width()))
            h = max(240, int(dlg.height()))
            dlg.resize(w, h)
            return
        ag = screen.availableGeometry()
        max_w = max(240, int(ag.width()) - 24)
        max_h = max(200, int(ag.height()) - 24)
        min_w_fit = min(max(240, int(min_w)), max_w)
        min_h_fit = min(max(200, int(min_h)), max_h)
        w = min(max_w, max(min_w_fit, int(ag.width() * float(width_frac))))
        h = min(max_h, max(min_h_fit, int(ag.height() * float(height_frac))))
        # On unusually small logical desktops, the work-area clamp always wins.
        w = max(1, min(w, max_w))
        h = max(1, min(h, max_h))
        x = int(ag.x()) + max(0, (int(ag.width()) - w) // 2)
        y = int(ag.y()) + max(0, (int(ag.height()) - h) // 2)
        dlg.setMinimumSize(min(min_w_fit, w), min(min_h_fit, h))
        dlg.setMaximumSize(max_w, max_h)
        dlg.setGeometry(x, y, w, h)
        dlg.raise_()
    except Exception as exc:
        print(f"[compat_settings] fit_dialog_to_screen: {exc}")


def wait_s(seconds):
    """A hardware wait scaled by the wait factor (System Settings ▸ Hardware wait ×). Use only as the upper bound of a
    check loop — the loop itself should end as soon as the device is ready."""
    try:
        return float(seconds) * float(load().get("wait_factor", 1.0))
    except Exception:
        return float(seconds)
