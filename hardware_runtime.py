"""Process-wide lazy hardware refresh coordinator for Groovebox.

The first hardware-dependent action starts one full refresh in background.  Audio
paths can still force only the cheap PortAudio cache refresh synchronously so
play/record never waits on USB/display probes.  Later full refreshes are explicit
from Performance -> Hardware (or a genuine hot-plug handler).
"""
from __future__ import annotations
import os, shutil, subprocess, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed

GROOVEBOX_V35_22ZZ_R17_LAZY_GUARANTEED_HARDWARE_REFRESH_20260930 = True

_lock = threading.RLock()
_done = threading.Event()
_running = False
_generation = 0
_snapshot = {}
_last_reason = ""
_last_completed = 0.0


def _refresh_audio_cache():
    try:
        from audio_os_backend import invalidate_device_cache, _device_snapshot
        invalidate_device_cache()
        _device_snapshot(force=True)
    except Exception:
        pass


def _bounded_call(fn, timeout, default=None):
    """Run a cold device query on a daemon lane without blocking the caller."""
    box = {}; done = threading.Event()
    def _run():
        try: box['value'] = fn()
        except Exception: pass
        finally: done.set()
    threading.Thread(target=_run, daemon=True, name="GrooveboxAudioCache").start()
    if not done.wait(max(0.1, float(timeout))):
        return default
    return box.get('value', default)


def _audio_cache_timeout():
    try:
        return max(0.5, float(os.environ.get('GROOVEBOX_HW_AUDIO_CACHE_TIMEOUT', '2.5')))
    except Exception:
        return 2.5


def _request_removable_scan():
    helper = "/usr/bin/sos-removable-media"
    try:
        if os.path.isfile(helper) and os.access(helper, os.X_OK):
            subprocess.Popen([helper, "--request-scan"], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, close_fds=True)
    except Exception:
        pass


def _prime_all_audio_route():
    """Best-effort: create combined Pulse sink + unmute preferred ALSA/HDMI.

    Runs during first hardware refresh so Performance/Player/Trigger All share
    an audible default on ISO and desktop without waiting for UI open.
    """
    try:
        from media_output_router import (
            _ensure_all_pulse_outputs_sink,
            _preferred_alsa_output_device,
            _prepare_physical_alsa_output,
            _drm_hdmi_connected,
        )
        combined = _ensure_all_pulse_outputs_sink()
        if combined:
            try:
                subprocess.run(
                    [shutil.which("pactl") or "pactl", "set-default-sink", combined],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.5, check=False,
                )
            except Exception:
                pass
        alsa = _preferred_alsa_output_device()
        if alsa:
            _prepare_physical_alsa_output(alsa)
        # If HDMI is connected, also prepare the first HDMI PCM explicitly so
        # digital mute state is cleared before any player attaches.
        if _drm_hdmi_connected():
            try:
                from media_output_router import list_audio_targets
                for t in list_audio_targets() or []:
                    if getattr(t, "kind", "") == "hdmi" and getattr(t, "backend", "") == "alsa":
                        _prepare_physical_alsa_output(t.name)
                        break
            except Exception:
                pass
    except Exception:
        pass


_prime_gate = threading.Lock()
_prime_last = 0.0


def _prime_all_audio_route_throttled():
    """One all-outputs/HDMI prime at a time, at most every 8 s.

    GROOVEBOX_NO_GUI_STALL_20261030: ensure_audio_ready() runs on every Play.  A new
    prime thread per press stacked pactl/amixer runs that re-route the default sink
    while the stream was still opening.
    """
    global _prime_last
    if not _prime_gate.acquire(blocking=False):
        return
    try:
        if _prime_last and time.monotonic() - _prime_last < 8.0:
            return
        _prime_all_audio_route()
        _prime_last = time.monotonic()
    finally:
        _prime_gate.release()


def _scan_all(gen: int, reason: str):
    global _running, _snapshot, _last_completed
    results = {}
    try:
        # Audio first and synchronously-cached so Trigger All / media open
        # never wait on USB/display/input probes (Dell Latitude / generic ISO).
        # The cold PortAudio query is bounded; a wedged driver cannot pin this
        # background refresh or the scan_component("audio") lane behind it.
        _bounded_call(_refresh_audio_cache, _audio_cache_timeout())
        # Fire removable rescan and All-outputs prime in parallel with component scans.
        try:
            threading.Thread(target=_request_removable_scan, daemon=True, name="GrooveboxRemovableScan").start()
        except Exception:
            _request_removable_scan()
        try:
            threading.Thread(target=_prime_all_audio_route, daemon=True, name="GrooveboxAllAudioPrime").start()
        except Exception:
            _prime_all_audio_route()
        try:
            from hardware_hub import scan_component
            try:
                results["audio"] = scan_component("audio")
            except Exception as exc:
                results["audio"] = {"error": str(exc)}
            try:
                from memory_guard import adaptive_workers
                _hw_workers = adaptive_workers(3, heavy=False)
            except Exception:
                _hw_workers = 3
            try:
                import thread_budget as _tb
                scan_lane = _tb.make_lane("hardware-component-scan", max_workers=_hw_workers,
                                          max_pending=3, kind="bulk")
            except Exception:
                scan_lane = ThreadPoolExecutor(max_workers=min(_hw_workers, 2),
                                                thread_name_prefix="GrooveboxHW-fallback")
            futs = {scan_lane.submit(scan_component, k): k for k in ("video", "display", "input")}
            for fut in as_completed(futs):
                k = futs[fut]
                try: results[k] = fut.result()
                except Exception as exc: results[k] = {"error": str(exc)}
            try: scan_lane.shutdown(wait=False, cancel_futures=True)
            except Exception: pass
        except Exception as exc:
            results["error"] = str(exc)
    finally:
        with _lock:
            if gen == _generation:
                _snapshot = results
                _last_completed = time.monotonic()
                _running = False
                _done.set()


def ensure_first_hardware_refresh(reason: str = "hardware-use", *, block: bool = False, timeout: float = 2.0):
    """Start the one automatic full refresh; subsequent calls are nearly free."""
    global _running, _generation, _last_reason
    start = False
    with _lock:
        if _done.is_set():
            return snapshot()
        _last_reason = str(reason or "hardware-use")
        if not _running:
            _running = True
            _generation += 1
            gen = _generation
            start = True
        else:
            gen = _generation
    if start:
        threading.Thread(target=_scan_all, args=(gen, _last_reason), daemon=True,
                         name="GrooveboxFirstHardwareRefresh").start()
    if block:
        _done.wait(max(0.0, float(timeout)))
    return snapshot()


def ensure_audio_ready(reason: str = "audio-use"):
    """First-use gate plus an immediate audio-only cache refresh.

    Full hardware probing remains background-only, while audio enumeration is
    refreshed now because playback/record needs the result before opening.
    On appliance/ISO (Dell Latitude and generic PCs) this is the path Trigger
    All and media players take without ever opening the Performance surface.
    """
    ensure_first_hardware_refresh(reason, block=False)
    # GROOVEBOX_NO_GUI_STALL_20261030: this runs on the GUI thread every time a
    # stream opens.  Use the TTL cache (4 s) instead of invalidating + forcing a
    # PortAudio/ALSA enumeration on each Play/Record press; only force when the
    # cache is genuinely empty (cold boot PipeWire).
    try:
        from audio_os_backend import _device_snapshot
        rows = _device_snapshot(force=False)
        if not rows:
            _bounded_call(_refresh_audio_cache, _audio_cache_timeout())
    except Exception:
        pass
    # Non-blocking All-outputs / HDMI unmute so first mpv play is audible.
    try:
        threading.Thread(target=_prime_all_audio_route_throttled, daemon=True, name="GrooveboxAudioReadyPrime").start()
    except Exception:
        pass
    _hardware_volume_sync_throttled()


_HWVOL_SYNC_AT = [0.0]


def _hardware_volume_sync_throttled(min_interval: float = 30.0):
    """GROOVEBOX_R23R_HWVOL_LATE_SYNC_20261101: re-assert the desired hardware
    volume + unmute before playback (at most every 30 s). Fixes the Dell case where
    audio only worked after each volume slider had been moved once."""
    now = time.monotonic()
    if now - _HWVOL_SYNC_AT[0] < min_interval:
        return
    _HWVOL_SYNC_AT[0] = now
    try:
        from hardware_volume import request_hardware_volume
        request_hardware_volume('sync')
    except Exception:
        pass


def mark_manual_refresh(results=None):
    """Called after Performance -> Hardware completes an explicit scan."""
    global _snapshot, _last_completed, _running
    with _lock:
        if isinstance(results, dict): _snapshot = dict(results)
        _last_completed = time.monotonic()
        _running = False
        _done.set()


def snapshot():
    with _lock:
        return dict(_snapshot)


def refresh_state():
    with _lock:
        return {"done": _done.is_set(), "running": _running, "generation": _generation,
                "reason": _last_reason, "last_completed": _last_completed}
