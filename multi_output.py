"""Play one audio callback on several physical outputs at once (GROOVEBOX_FANOUT_20261102).

Used by audio_os_backend.open_output_stream when no sound server can combine the outputs
(no PipeWire/Pulse combine sink): the first device that opens is the *primary* and drives the
user callback; every other physical output that accepts the same sample rate / channel count
is a *secondary* that replays the primary's blocks from a small bounded ring. Devices that
refuse the format or fail to open are skipped, never fatal. Different device clocks drift, so
each ring is capped (oldest audio dropped) to keep every output within ~0.25 s of the primary.
"""
from __future__ import annotations

import re
import threading
import time
import numpy as np

_VIRTUAL = ("default", "sysdefault", "pipewire", "pulse", "dmix", "dsnoop", "samplerate",
            "speex", "lavrate", "upmix", "vdownmix", "jack", "monitor", "null", "dummy", "front:", "surround")
_HW_RE = re.compile(r"\(hw:(\d+),(\d+)\)")


def physical_targets(rows, ok):
    """Indexes of real hardware outputs, one per (card,device), best-ranked first."""
    seen, out = set(), []
    for i, d in enumerate(rows or []):
        try:
            if not ok(i):
                continue
            name = str(d.get("name", ""))
            low = name.casefold()
            if any(t == low or low.startswith(t) for t in _VIRTUAL):
                continue
            m = _HW_RE.search(name)
            key = (m.group(1), m.group(2)) if m else low
            if key in seen:
                continue
            seen.add(key)
            out.append(i)
        except Exception:
            continue
    return out


class _Ring:
    def __init__(self, channels, cap_frames):
        self.ch = int(channels); self.cap = int(cap_frames)
        self.buf = np.zeros((self.cap, self.ch), dtype=np.float32)
        self.n = 0; self.primed = False
        self.lock = threading.Lock()

    def write(self, block):
        b = np.asarray(block, dtype=np.float32)
        if b.ndim == 1:
            b = b[:, None]
        if b.shape[1] != self.ch:
            b = np.repeat(b[:, :1], self.ch, axis=1) if b.shape[1] == 1 else b[:, :self.ch]
        f = b.shape[0]
        with self.lock:
            if f >= self.cap:
                self.buf[:] = b[-self.cap:]; self.n = self.cap; return
            if self.n + f > self.cap:                   # drop oldest: bound the latency
                drop = self.n + f - self.cap
                self.buf[:self.n - drop] = self.buf[drop:self.n]; self.n -= drop
            self.buf[self.n:self.n + f] = b; self.n += f

    def read(self, frames, out):
        out.fill(0.0)
        with self.lock:
            if not self.primed:
                if self.n < min(self.cap // 2, frames * 2):
                    return                              # let a little audio accumulate first
                self.primed = True
            take = min(int(frames), self.n)
            if take <= 0:
                self.primed = False                     # underrun: re-prime
                return
            out[:take, :self.ch] = self.buf[:take]
            self.buf[:self.n - take] = self.buf[take:self.n]; self.n -= take


class FanOutStream:
    """sounddevice.OutputStream look-alike driving several devices from one callback."""

    def __init__(self, sd, user_cb, *, device_ids, samplerate, channels, dtype, blocksize, latency, extra, rescan=None, retry_s=3.0, on_join=None):
        self._sd = sd; self._cb = user_cb
        self._dtype = dtype; self._blocksize = blocksize; self._latency = latency
        self._rescan = rescan; self._on_join = on_join; self._retry_s = float(retry_s); self._cap = max(2048, int(int(samplerate) * 0.25))
        self._watch_stop = threading.Event(); self._watch = None; self._dead = {}
        self._sec_dev = []   # device id per secondary, parallel to self.secondaries / self.rings
        self.rate = int(samplerate); self.channels = int(channels)
        self.primary = None; self.secondaries = []; self.rings = []; self.skipped = []
        self.devices = []
        cap = max(2048, int(self.rate * 0.25))
        for dev in device_ids:
            try:
                sd.check_output_settings(device=dev, samplerate=self.rate, channels=self.channels, dtype=dtype)
            except Exception as exc:
                self.skipped.append((dev, f"format: {exc}")); continue
            if self.primary is None:
                try:
                    self.primary = sd.OutputStream(device=dev, samplerate=self.rate, channels=self.channels,
                                                   dtype=dtype, callback=self._primary_cb,
                                                   blocksize=blocksize, latency=latency, **extra)
                    self.devices.append(dev)
                except Exception as exc:
                    self.skipped.append((dev, f"open: {exc}"))
                continue
            ring = _Ring(self.channels, cap)

            def sec_cb(outdata, frames, _t, _s, _r=ring):
                try:
                    _r.read(frames, outdata)
                except Exception:
                    outdata.fill(0.0)
            try:
                st = sd.OutputStream(device=dev, samplerate=self.rate, channels=self.channels, dtype=dtype,
                                     callback=sec_cb, blocksize=blocksize, latency=latency)
                self.secondaries.append(st); self.rings.append(ring); self.devices.append(dev); self._sec_dev.append(dev)
            except Exception as exc:
                self.skipped.append((dev, f"open: {exc}"))
        if self.primary is None:
            raise RuntimeError("no physical output opened: " + "; ".join(f"{d}: {m}" for d, m in self.skipped[:6]))

    def _primary_cb(self, outdata, frames, time_info, status):
        self._cb(outdata, frames, time_info, status)
        for r in self.rings:
            try:
                r.write(outdata[:frames])
            except Exception:
                pass

    # -- sounddevice.OutputStream surface used by Groovebox -----------------
    def start(self):
        for s in self.secondaries:
            try: s.start()
            except Exception: pass
        self.primary.start()
        self._start_watch()

    # -- ALL_AUDIO_HARDWARE_20261102: keep every output in the chorus while playing --------------
    def _start_watch(self):
        if self._watch is not None and self._watch.is_alive():
            return
        self._watch_stop.clear()
        self._watch = threading.Thread(target=self._watch_loop, daemon=True, name="GrooveboxFanOutWatch")
        self._watch.start()

    def _watch_loop(self):
        while not self._watch_stop.wait(self._retry_s):
            try:
                self.refresh_outputs()
            except Exception:
                pass

    def _open_secondary(self, dev):
        self._sd.check_output_settings(device=dev, samplerate=self.rate, channels=self.channels, dtype=self._dtype)
        ring = _Ring(self.channels, self._cap)

        def sec_cb(outdata, frames, _t, _s, _r=ring):
            try:
                _r.read(frames, outdata)
            except Exception:
                outdata.fill(0.0)
        st = self._sd.OutputStream(device=dev, samplerate=self.rate, channels=self.channels, dtype=self._dtype,
                                   callback=sec_cb, blocksize=self._blocksize, latency=self._latency)
        st.start()
        # copy-on-write so the audio callback never iterates a list being modified
        self.secondaries = self.secondaries + [st]; self.rings = self.rings + [ring]
        self._sec_dev = self._sec_dev + [dev]
        if dev not in self.devices:
            self.devices = self.devices + [dev]
        if self._on_join is not None:
            try: self._on_join()          # set volume / unmute on the newly joined output too
            except Exception: pass

    def refresh_outputs(self):
        """Restart secondaries that stopped, drop ones that cannot restart, and (re)try every physical
        output that is not currently playing (busy at open, plugged in later, format refused earlier)."""
        for i, st in enumerate(list(self.secondaries)):
            try:
                if getattr(st, "active", True):
                    continue
                st.start()
            except Exception:
                self._drop_secondary(st)
        want = []
        if self._rescan is not None:
            try:
                want = [d for d in (self._rescan() or [])]
            except Exception:
                want = []
        else:
            want = [d for d, _m in list(self.skipped)]
        have = set(self.devices)
        for dev in want:
            if dev in have or dev == self.devices[0]:
                continue
            now = time.monotonic()
            if now < self._dead.get(dev, 0.0):
                continue
            try:
                self._open_secondary(dev)
            except Exception:
                self._dead[dev] = now + min(60.0, self._retry_s * 4)

    def _drop_secondary(self, st):
        try:
            i = self.secondaries.index(st)
        except ValueError:
            return
        dev = self._sec_dev[i] if i < len(self._sec_dev) else None
        self.rings = self.rings[:i] + self.rings[i + 1:]
        self._sec_dev = self._sec_dev[:i] + self._sec_dev[i + 1:]
        self.secondaries = self.secondaries[:i] + self.secondaries[i + 1:]
        self.devices = [d for d in self.devices if d != dev]
        try: st.close()
        except Exception: pass
        if dev is not None:
            self._dead[dev] = time.monotonic() + self._retry_s * 4

    def stop(self):
        self._watch_stop.set()
        try: self.primary.stop()
        except Exception: pass
        for s in self.secondaries:
            try: s.stop()
            except Exception: pass

    def close(self):
        self._watch_stop.set()
        try: self.primary.close()
        except Exception: pass
        for s in self.secondaries:
            try: s.close()
            except Exception: pass

    abort = stop

    @property
    def active(self):
        return bool(getattr(self.primary, "active", True))

    @property
    def stopped(self):
        return bool(getattr(self.primary, "stopped", False))

    @property
    def samplerate(self):
        return self.rate

    @property
    def latency(self):
        return getattr(self.primary, "latency", 0.0)

    def __getattr__(self, item):               # anything else comes from the primary stream
        return getattr(self.primary, item)
