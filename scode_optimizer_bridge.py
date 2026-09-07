#!/usr/bin/env python3
"""Required sCode acceleration bridge for Mathematician's Groovebox.

sCode owns the number<->logic policy, dirty-state classification, finite pool
routing, cadence selection, and reusable work identities. Python/NumPy owns the
actual buffers and DSP kernels so there is no IPC inside realtime audio callbacks.

ABI 5 retains the host-consumed acceleration primitives and makes the author-number
codec/pool contract explicit: on-demand host planning,
per-modality work claims, result memoization, deterministic ndarray pools,
background cadence/QoS, and measurable hit/skip statistics.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np


class SCodeRequiredError(RuntimeError):
    pass


def _root() -> Path:
    return Path(__file__).resolve().parent / "sCode"


def _find_stage0(root: Path) -> Path:
    sysname = platform.system().lower()
    machine = platform.machine().lower()
    if sysname == "linux" and machine in {"x86_64", "amd64"}:
        return root / "bootstrap" / "linux-x86_64" / "scode0"
    if sysname == "darwin" and machine in {"x86_64", "amd64"}:
        return root / "bootstrap" / "macos-x86_64" / "scode0"
    if sysname == "darwin" and machine in {"arm64", "aarch64"}:
        return root / "bootstrap" / "macos-arm64" / "scode0"
    if os.name == "nt" and machine in {"x86_64", "amd64"}:
        return root / "bootstrap" / "windows-x86_64" / "scode0.exe"
    return root / "bootstrap" / "UNAVAILABLE"


def stable_numeric_identity(value: Any) -> int:
    blob = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8", "replace")
    # 52 bits remain exactly representable in the stage-0 numeric runtime.
    return int.from_bytes(hashlib.sha256(blob).digest()[:7], "big") & ((1 << 52) - 1)


class SCodeOptimizerBridge:
    ABI = 5
    _BITS = {
        "audio": 1, "visual": 2, "game": 4, "media": 8,
        "ui": 16, "project": 32, "canonical": 64, "symbols": 128,
    }

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root or _root()).resolve()
        self.stage0 = _find_stage0(self.root)
        self.script = self.root / "apps" / "groovebox" / "groovebox_optimizer.sC"
        self._cache: "OrderedDict[Tuple[int,int,int,int], Dict[str,int]]" = OrderedDict()
        self._pool: "OrderedDict[Tuple[int,str,Tuple[int,...],str], np.ndarray]" = OrderedDict()
        self._result_cache: Dict[str, OrderedDict] = {}
        self._last_work_keys: Dict[str, Tuple[int, str, int]] = {}
        self._pool_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        self._plan_lock = threading.Lock()
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scode-opt")
        self._pending = None
        self._pending_key = None
        self._last_plan: Dict[str, int] = {}
        self._last_categories: Dict[str, int] = {}
        self._last_shallow_identity: Optional[int] = None
        self._frame = 0
        self._host_timer = None
        self._stats = {
            "plans": 0, "plan_cache_hits": 0, "work_claims": 0, "work_skips": 0,
            "memo_hits": 0, "memo_misses": 0, "pool_hits": 0, "pool_misses": 0,
        }
        self.require_runtime()

    def require_runtime(self) -> None:
        if not self.root.is_dir():
            raise SCodeRequiredError(f"Bundled sCode tree is missing: {self.root}")
        if not self.script.is_file():
            raise SCodeRequiredError(f"Groovebox sCode optimizer is missing: {self.script}")
        if not self.stage0.is_file():
            raise SCodeRequiredError(
                "This Groovebox build requires the bundled sCode stage-0 runtime. "
                f"No verified stage-0 is present for {platform.system()} {platform.machine()}."
            )
        try:
            mode = self.stage0.stat().st_mode
            if os.name != "nt" and not (mode & 0o111):
                self.stage0.chmod(mode | 0o755)
        except Exception:
            pass
        probe = self.optimize_sync({"probe": 1}, dirty_mask=255, frame=0, shape=0, bypass_cache=True)
        if int(probe.get("scode_optimizer_abi", -1)) != self.ABI:
            raise SCodeRequiredError(
                f"Bundled sCode optimizer ABI mismatch: expected {self.ABI}, got {probe.get('scode_optimizer_abi')}"
            )
        required = (
            "pool_slot", "audio_lane", "visual_lane", "game_lane", "media_lane",
            "canonical_lane", "run_audio", "run_visual", "run_media",
            "visual_pool_slot", "media_pool_slot", "canonical_pool_slot",
            "background_cadence", "parallel_width",
            "symbol_base", "symbol_full_cycle", "symbol_half_denominator",
            "symbol_subscale_bits", "symbol_variant_count", "symbol_pool_key",
        )
        if any(k not in probe for k in required):
            missing = [k for k in required if k not in probe]
            raise SCodeRequiredError("Bundled sCode optimizer returned an incomplete ABI-5 plan: " + ", ".join(missing))
        expected_symbols = {
            "symbol_base": 16, "symbol_full_cycle": 16,
            "symbol_half_denominator": 2, "symbol_subscale_bits": 4,
            "symbol_variant_count": 68,
        }
        bad = [k for k, v in expected_symbols.items() if int(probe.get(k, -1)) != v]
        if bad:
            raise SCodeRequiredError("Bundled sCode symbol codec contract mismatch: " + ", ".join(bad))
        # Seed the shared runtime plan with the verified probe so symbol cache
        # routing is concrete before the first host timer tick.
        self._last_plan = dict(probe)

    @staticmethod
    def _parse(stdout: str) -> Dict[str, int]:
        plan: Dict[str, int] = {}
        for raw in (stdout or "").splitlines():
            if "=" not in raw:
                continue
            k, v = raw.split("=", 1)
            k, v = k.strip(), v.strip()
            if not k:
                continue
            try:
                plan[k] = int(round(float(v)))
            except Exception:
                continue
        return plan

    def optimize_sync(self, state: Any, dirty_mask: int = 255, frame: int = 0,
                      shape: int = 0, bypass_cache: bool = False) -> Dict[str, int]:
        identity = stable_numeric_identity(state)
        frame_bucket = int(frame) // 4
        key = (identity, int(dirty_mask) & 255, frame_bucket, int(shape))
        with self._cache_lock:
            if not bypass_cache and key in self._cache:
                self._stats["plan_cache_hits"] += 1
                plan = dict(self._cache[key])
                self._cache.move_to_end(key)
                return plan
        env = os.environ.copy()
        env.update({
            "GB_OPT_ID": str(identity),
            "GB_OPT_DIRTY": str(int(dirty_mask) & 255),
            "GB_OPT_FRAME": str(int(frame)),
            "GB_OPT_LANES": str(max(1, min(64, os.cpu_count() or 4))),
            "GB_OPT_POOL": "64",
            "GB_OPT_SHAPE": str(int(shape)),
        })
        t0 = time.perf_counter_ns()
        proc = subprocess.run(
            [str(self.stage0), "run", str(self.script.relative_to(self.root))],
            cwd=str(self.root), env=env, capture_output=True, text=True, timeout=5,
            check=False,
        )
        if proc.returncode != 0:
            raise SCodeRequiredError(
                "Required sCode optimizer failed\n" + (proc.stderr or proc.stdout or "unknown error")[-2000:]
            )
        plan = self._parse(proc.stdout)
        if int(plan.get("scode_optimizer_abi", -1)) != self.ABI:
            raise SCodeRequiredError("Required sCode optimizer returned an invalid ABI-5 plan")
        plan["identity"] = identity
        plan["dirty"] = int(dirty_mask) & 255
        plan["plan_ns"] = int(time.perf_counter_ns() - t0)
        with self._cache_lock:
            self._cache[key] = dict(plan)
            self._cache.move_to_end(key)
            while len(self._cache) > 512:
                self._cache.popitem(last=False)
        self._stats["plans"] += 1
        return plan

    def category_dirty_mask(self, categories: Dict[str, Any]) -> int:
        mask = 0
        current: Dict[str, int] = {}
        for name, bit in self._BITS.items():
            ident = stable_numeric_identity(categories.get(name))
            current[name] = ident
            if self._last_categories.get(name) != ident:
                mask |= bit
        self._last_categories = current
        return mask

    @staticmethod
    def _widget_value(host, name, default=None):
        try:
            obj = getattr(host, name, None)
            if obj is None:
                return default
            if hasattr(obj, "isChecked"):
                return bool(obj.isChecked())
            if hasattr(obj, "value"):
                return obj.value()
            if hasattr(obj, "currentText"):
                return obj.currentText()
            if hasattr(obj, "text"):
                return obj.text()
        except Exception:
            pass
        return default

    def _host_categories(self, host, *, deep: bool = True) -> Dict[str, Any]:
        def attr(name, default=None):
            try:
                return getattr(host, name, default)
            except Exception:
                return default
        try:
            seed_text = host._seed_text() if hasattr(host, "_seed_text") else str(host.get_numeric_seed())
        except Exception:
            seed_text = "0"
        # Do not recompute the full canonical fingerprint every optimizer tick.
        fp = str(attr("_scode_cached_fp", "") or "")
        if not fp:
            try:
                lbl = attr("lbl_canonical_fp", None)
                txt = lbl.text() if lbl is not None and hasattr(lbl, "text") else ""
                fp = str(txt).replace("ID:", "").strip()
            except Exception:
                fp = ""
        playlist = attr("master_playlist_data", []) or []
        seq_banks = attr("instrument_sequence_banks", {}) or {}
        seq_mem = attr("instrument_sequencer_memory", {}) or {}
        global_algo = attr("global_algo_state", {}) or {}
        step_algos = attr("step_algorithms", {}) or {}
        toggles = (
            self._widget_value(host, "btn_goava", bool(attr("goava_active", False))),
            self._widget_value(host, "btn_local_randomize", False),
            self._widget_value(host, "btn_local_phase_lock", False),
            self._widget_value(host, "btn_idealize_rhythm", False),
            self._widget_value(host, "btn_seeded_randomize", False),
        )
        if deep:
            _algo_id = stable_numeric_identity(global_algo)
            _step_id = stable_numeric_identity(step_algos)
            _banks_id = stable_numeric_identity(seq_banks)
            _mem_id = stable_numeric_identity(seq_mem)
            _playlist_id = stable_numeric_identity(playlist)
            _hyper_id = stable_numeric_identity(attr("hyperdrive_state", {}))
        else:
            # Timer/QoS sampling never walks or serializes the large project stores.
            # Exact hashes are computed only at an expensive work boundary.
            _algo_id = (len(global_algo) if hasattr(global_algo, "__len__") else 0)
            _step_id = (len(step_algos) if hasattr(step_algos, "__len__") else 0)
            _banks_id = len(seq_banks)
            _mem_id = len(seq_mem)
            _playlist_id = (len(playlist), fp)
            _hyper_id = bool(attr("hyperdrive_state", {}))
        core = (
            seed_text,
            self._widget_value(host, "spin_bpm", 120.0),
            self._widget_value(host, "spin_base_frequency", 432.0),
            self._widget_value(host, "spin_seq_length", 16),
            self._widget_value(host, "spin_playlist_length", len(playlist)),
            toggles, _algo_id, _step_id, _banks_id, _mem_id, _playlist_id, _hyper_id,
        )
        media = {
            "global": attr("_global_carrier_path", ""),
            "wav": attr("_wav_carrier_path", ""),
            "video": attr("_video_carrier_path", ""),
            "workbench": stable_numeric_identity(attr("media_workbench_state", {})) if deep else bool(attr("media_workbench_state", {})),
            "instrument_media": stable_numeric_identity(attr("instrument_media_samples", {})) if deep else len(attr("instrument_media_samples", {}) or {}),
        }
        effects = (
            self._widget_value(host, "slider_eqr", 0),
            self._widget_value(host, "slider_fractalizer", 0),
            self._widget_value(host, "slider_pkp_envelope", 0),
            self._widget_value(host, "slider_pkp_boost", 0),
        )
        symbols = {
            "enabled": bool(attr("math_symbols_enabled", False)),
            "font_cache": "base16-squiggle-subscale-v4",
        }
        return {
            "audio": (core, effects, media["global"], media["wav"]),
            "visual": (core, fp, attr("visualizer_mode", None), media["video"]),
            "game": (core, fp, stable_numeric_identity(attr("_last_videogame_identity", None))),
            "media": media,
            "ui": (attr("_current_sequence_id", None), attr("_current_instrument", None), symbols["enabled"]),
            "project": (core, media, attr("_current_project_path", None)),
            "canonical": core,
            "symbols": symbols,
        }

    def plan_host_now(self, host, *, force: bool = False) -> Dict[str, int]:
        """Synchronously refresh the compact sCode plan before expensive GUI work."""
        cats = self._host_categories(host)
        dirty = self.category_dirty_mask(cats)
        if dirty == 0 and self._last_plan and not force:
            return dict(self._last_plan)
        if force and dirty == 0:
            dirty = 255
        shape = len(getattr(host, "master_playlist_data", []) or [])
        with self._plan_lock:
            self._last_plan = self.optimize_sync(cats, dirty_mask=dirty or 255, frame=self._frame, shape=shape)
        host._scode_optimizer_plan = dict(self._last_plan)
        return dict(self._last_plan)

    def should_run(self, kind: str) -> bool:
        return bool(int(self._last_plan.get("run_" + kind, 1)))

    def lane(self, kind: str) -> int:
        return int(self._last_plan.get(kind + "_lane", 0))

    def cadence_value(self, kind: str, default: int = 1) -> int:
        return max(1, int(self._last_plan.get(kind + "_cadence", self._last_plan.get("background_cadence" if kind == "background" else "", default))))

    def cadence_due(self, kind: str, frame: Optional[int] = None, base_divisor: Optional[int] = None) -> bool:
        f = self._frame if frame is None else int(frame)
        lane = max(0, self.lane(kind))
        div = max(1, int(base_divisor if base_divisor is not None else self.cadence_value(kind, 1)))
        return ((f + lane) % div) == 0

    def work_key(self, kind: str, payload: Any) -> Tuple[int, str, int]:
        slot = int(self._last_plan.get(kind + "_pool_slot", self._last_plan.get("pool_slot", 0))) & 63
        return (slot, str(kind), stable_numeric_identity(payload))

    def claim_work(self, kind: str, payload: Any, *, force: bool = False) -> bool:
        """Return True only when this deterministic work identity needs execution."""
        key = self.work_key(kind, payload)
        self._stats["work_claims"] += 1
        if not force and self._last_work_keys.get(kind) == key:
            self._stats["work_skips"] += 1
            return False
        self._last_work_keys[kind] = key
        return True

    def claim_host_work(self, host, kind: str, *, force: bool = False, extra: Any = None) -> bool:
        cats = self._host_categories(host)
        payload = cats.get(kind)
        if extra is not None:
            payload = (payload, extra)
        return self.claim_work(kind, payload, force=force)

    def symbol_packet_key(self, payload: Any) -> Tuple[int, str, int]:
        """Stable sCode-selected cache identity for an immutable symbol packet."""
        slot = int(self._last_plan.get("symbol_pool_slot", self._last_plan.get("pool_slot", 0))) & 63
        return (slot, "symbol", stable_numeric_identity(payload))

    def memoized_symbol_spelling(self, payload: Any, producer: Callable[[], Any], *, max_entries: int = 4096):
        """Large bounded cache for value->author-symbol semantic spellings.

        The sCode plan selects the symbol pool slot; Python stores the immutable
        packet so no subprocess/IPC is paid in the Qt hot path.
        """
        key = self.symbol_packet_key(payload)
        with self._cache_lock:
            bucket = self._result_cache.setdefault("symbol_spelling", OrderedDict())
            if key in bucket:
                self._stats["memo_hits"] += 1
                value = bucket[key]
                bucket.move_to_end(key)
                return value
        self._stats["memo_misses"] += 1
        value = producer()
        with self._cache_lock:
            bucket = self._result_cache.setdefault("symbol_spelling", OrderedDict())
            bucket[key] = value
            bucket.move_to_end(key)
            while len(bucket) > max(128, int(max_entries)):
                bucket.popitem(last=False)
        return value

    def invalidate_work(self, kind: Optional[str] = None) -> None:
        if kind is None:
            self._last_work_keys.clear()
            with self._cache_lock:
                self._result_cache.clear()
        else:
            self._last_work_keys.pop(str(kind), None)
            with self._cache_lock:
                self._result_cache.pop(str(kind), None)

    def memoized_result(self, kind: str, payload: Any, producer: Callable[[], Any], *, max_entries: int = 32):
        """sCode-routed memoization for deterministic non-realtime results."""
        key = self.work_key(kind, payload)
        with self._cache_lock:
            bucket = self._result_cache.setdefault(str(kind), OrderedDict())
            if key in bucket:
                self._stats["memo_hits"] += 1
                value = bucket[key]
                bucket.move_to_end(key)
                return value
        self._stats["memo_misses"] += 1
        value = producer()
        with self._cache_lock:
            bucket = self._result_cache.setdefault(str(kind), OrderedDict())
            bucket[key] = value
            bucket.move_to_end(key)
            while len(bucket) > max(1, int(max_entries)):
                bucket.popitem(last=False)
        return value

    def borrow_array(self, kind: str, shape, dtype=np.float32, *, zero: bool = False) -> np.ndarray:
        """Return a bounded reusable NumPy buffer in the sCode-selected pool slot."""
        shp = tuple(int(x) for x in (shape if isinstance(shape, (tuple, list)) else (shape,)))
        dt = np.dtype(dtype)
        slot = int(self._last_plan.get(kind + "_pool_slot", self._last_plan.get("pool_slot", 0))) & 63
        key = (slot, str(kind), shp, dt.str)
        with self._pool_lock:
            arr = self._pool.get(key)
            if arr is None or arr.shape != shp or arr.dtype != dt:
                arr = np.empty(shp, dtype=dt)
                self._pool[key] = arr
                self._stats["pool_misses"] += 1
            else:
                self._stats["pool_hits"] += 1
                self._pool.move_to_end(key)
            while len(self._pool) > 256:
                self._pool.popitem(last=False)
            if zero:
                arr.fill(0)
            return arr

    def clear_reuse_pool(self) -> None:
        with self._pool_lock:
            self._pool.clear()
        with self._cache_lock:
            self._result_cache.clear()

    @staticmethod
    def editing_active(host) -> bool:
        """Cheap QoS predicate: decorative work yields while an editor has focus."""
        try:
            from PyQt6.QtWidgets import QApplication, QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox
            w = QApplication.focusWidget()
            return isinstance(w, (QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox))
        except Exception:
            return False

    def install_on_host(self, host, interval_ms: int = 250) -> None:
        host._scode_optimizer = self
        host._scode_optimizer_required = True
        host._scode_optimizer_plan = dict(self._last_plan)
        cats = self._host_categories(host)
        mask = self.category_dirty_mask(cats) or 255
        self._last_plan = self.optimize_sync(cats, dirty_mask=mask, frame=0)
        host._scode_optimizer_plan = dict(self._last_plan)
        # The startup composition is already committed before this bridge attaches.
        for kind in ("canonical", "game", "media", "symbols"):
            self._last_work_keys[kind] = self.work_key(kind, cats.get(kind))
        try:
            from PyQt6.QtCore import QTimer
        except Exception:
            return

        def tick():
            self._frame += 1
            cats2 = self._host_categories(host, deep=False)
            shallow_identity = stable_numeric_identity(cats2)
            shallow_changed = (self._last_shallow_identity != shallow_identity)
            self._last_shallow_identity = shallow_identity
            fut = self._pending
            if fut is not None and fut.done():
                try:
                    self._last_plan = fut.result()
                    host._scode_optimizer_plan = dict(self._last_plan)
                    host._scode_optimizer_last_error = ""
                except Exception as exc:
                    host._scode_optimizer_last_error = str(exc)
                self._pending = None
                self._pending_key = None
            if not shallow_changed or self._pending is not None:
                return
            shape = len(getattr(host, "master_playlist_data", []) or [])
            # Shallow plan changes only scheduling/pool placement, never semantic
            # dirty decisions. Use a full modality mask; exact work claims are
            # separately checked with deep state at execution boundaries.
            dirty = 255
            self._pending_key = (shallow_identity, dirty, self._frame, shape)
            self._pending = self._worker.submit(self.optimize_sync, cats2, dirty, self._frame, shape)

        timer = QTimer(host)
        timer.setInterval(max(120, int(interval_ms)))
        timer.timeout.connect(tick)
        timer.start()
        self._host_timer = timer
        host._scode_optimizer_timer = timer

    def state_for_project(self) -> Dict[str, Any]:
        return {
            "required": True,
            "abi": self.ABI,
            "plan": dict(self._last_plan),
            "pool_entries": len(self._pool),
            "memo_entries": sum(len(x) for x in self._result_cache.values()),
            "policy": "number_logic_cross_cast_pool_scheduler_symbol_codec_v5",
            "optimizer_script": "apps/groovebox/groovebox_optimizer.sC",
            "coalescing": True,
            "reusable_buffers": True,
            "hot_path_consumers": ["canonical", "visual_preview", "background", "media_layers", "game_identity", "symbols"],
            "symbol_codec": {
                "scheme": "base16-squiggle-subscale-v4",
                "base": 16, "full_cycle": 16, "half_denominator": 2,
                "subscale_bits": 4, "variant_count": 68,
                "sCode_pool_slot": int(self._last_plan.get("symbol_pool_slot", 0)),
            },
            "stats": dict(self._stats),
        }


_BRIDGE_SINGLETON: Optional[SCodeOptimizerBridge] = None
_BRIDGE_SINGLETON_LOCK = threading.Lock()

def require_scode_runtime() -> SCodeOptimizerBridge:
    # Preflight and the main QApplication share one verified optimizer, one plan
    # cache and one finite buffer pool instead of paying bootstrap twice.
    global _BRIDGE_SINGLETON
    with _BRIDGE_SINGLETON_LOCK:
        if _BRIDGE_SINGLETON is None:
            _BRIDGE_SINGLETON = SCodeOptimizerBridge()
        return _BRIDGE_SINGLETON
