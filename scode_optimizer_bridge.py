#!/usr/bin/env python3
"""Required sCode acceleration bridge for Mathematician's Groovebox.

sCode owns the number<->logic policy, dirty-state classification, finite pool
routing, cadence selection, and reusable work identities. Python/NumPy owns the
actual buffers and DSP kernels so there is no IPC inside realtime audio callbacks.

ABI 9 keeps universal asynchronous completion semantics and freezes the saturated full-cycle symbol contract on top of the format-aware
pool contract: worker execution and result publication are separated, stale
generation/frame work is rejected, streams publish latest-ready buffers, side
effects are never replayed from cache, and Qt callbacks are marshalled back to
the GUI thread without putting IPC or blocking locks in realtime audio callbacks.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import queue
import subprocess
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np


class SCodeRequiredError(RuntimeError):
    pass


class SCodeStaleCompletion(RuntimeError):
    """A worker completed after its sCode publication window had expired."""
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
    ABI = 9
    FINITE_INFINITY = 134964356
    COMPLETION_ABI = 1
    POLICY_PURE = 0
    POLICY_GENERATION = 1
    POLICY_FRAME = 2
    POLICY_STREAM = 3
    POLICY_SIDE_EFFECT = 4
    _POLICY_NAMES = {
        "pure": POLICY_PURE,
        "generation": POLICY_GENERATION,
        "frame": POLICY_FRAME,
        "stream": POLICY_STREAM,
        "side_effect": POLICY_SIDE_EFFECT,
        "side-effect": POLICY_SIDE_EFFECT,
    }
    _POOL_FORMATS = {
        "generic": 0, "scalar": 1, "vector": 2, "matrix": 3,
        "tensor": 4, "bytes": 5, "text": 6, "audio": 7,
        "image": 8, "video_frame": 9, "object": 10, "compiled": 11,
        "symbol": 12, "project": 13, "sequence": 14, "automation": 15,
        "world": 16, "media_stream": 17,
    }
    _MODALITY_IDS = {
        "audio": 1, "visual": 2, "game": 3, "media": 4,
        "ui": 5, "canonical": 6, "symbols": 7, "symbol": 7, "project": 8,
    }
    _BITS = {
        "audio": 1, "visual": 2, "game": 4, "media": 8,
        "ui": 16, "project": 32, "canonical": 64, "symbols": 128,
    }

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root or _root()).resolve()
        self.stage0 = _find_stage0(self.root)
        self.script = self.root / "apps" / "groovebox" / "groovebox_optimizer.sC"
        self.pool_catalog_script = self.root / "apps" / "groovebox" / "pool_catalog.sC"
        self.pool_request_probe_script = self.root / "apps" / "groovebox" / "pool_request_probe.sC"
        self._pool_catalog: Dict[int, Dict[str, int]] = {}
        self._cache: "OrderedDict[Tuple[int,int,int,int,int,int,int,int], Dict[str,int]]" = OrderedDict()
        self._pool: "OrderedDict[Tuple[int,str,Tuple[int,...],str], np.ndarray]" = OrderedDict()
        self._result_cache: Dict[str, OrderedDict] = {}
        self._last_work_keys: Dict[str, Tuple[int, str, int, int]] = {}
        self._pool_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        self._plan_lock = threading.Lock()
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scode-opt")
        # Poolable work and completion publication are intentionally separate.
        # The requesting/UI/audio threads only perform cheap identity/lookup work.
        self._work_workers = ThreadPoolExecutor(
            max_workers=max(2, min(8, int(os.cpu_count() or 4))),
            thread_name_prefix="scode-work",
        )
        self._completion_queue = queue.Queue()
        self._completion_stop = threading.Event()
        self._completion_thread = None
        self._inflight_lock = threading.Lock()
        self._inflight: Dict[Tuple[Any, ...], Future] = {}
        self._inflight_callbacks: Dict[Tuple[Any, ...], list] = {}
        self._latest_requests: Dict[str, Tuple[int, int, Tuple[Any, ...], int]] = {}
        self._stream_results: Dict[str, Tuple[int, int, Any]] = {}
        self._ui_callbacks = []
        self._ui_lock = threading.Lock()
        self._completion_timer = None
        self._submission_seq = 0
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
            "completion_submitted": 0, "completion_cache_hits": 0,
            "completion_coalesced": 0, "completion_published": 0,
            "completion_stale_dropped": 0, "completion_errors": 0,
            "completion_ui_delivered": 0,
        }
        self.require_runtime()
        self._start_completion_thread()

    def require_runtime(self) -> None:
        if not self.root.is_dir():
            raise SCodeRequiredError(f"Bundled sCode tree is missing: {self.root}")
        if not self.script.is_file():
            raise SCodeRequiredError(f"Groovebox sCode optimizer is missing: {self.script}")
        if not self.pool_catalog_script.is_file():
            raise SCodeRequiredError(f"sCode universal pool catalog is missing: {self.pool_catalog_script}")
        if not self.pool_request_probe_script.is_file():
            raise SCodeRequiredError(f"sCode universal pool request probe is missing: {self.pool_request_probe_script}")
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
            "pool_abi", "scheduler_abi", "completion_abi", "completion_policy_count", "symbol_abi", "pool_slot", "generation",
            "audio_lane", "visual_lane", "game_lane", "media_lane", "ui_lane",
            "canonical_lane", "symbol_lane", "project_lane",
            "run_audio", "run_visual", "run_game", "run_media", "run_ui",
            "run_project", "run_canonical", "run_symbols",
            "audio_pool_slot", "visual_pool_slot", "game_pool_slot", "media_pool_slot",
            "ui_pool_slot", "canonical_pool_slot", "symbol_pool_slot", "project_pool_slot",
            "audio_result_slot", "visual_result_slot", "game_result_slot", "media_result_slot",
            "ui_result_slot", "canonical_result_slot", "symbol_result_slot", "project_result_slot",
            "audio_cadence", "visual_cadence", "game_cadence", "media_cadence",
            "ui_cadence", "canonical_cadence", "symbol_cadence", "project_cadence",
            "background_cadence", "parallel_width", "coalesce_bucket",
            "symbol_base", "symbol_full_cycle", "symbol_half_denominator",
            "symbol_subscale_bits", "symbol_variant_count", "symbol_pool_key",
            "symbol_full_cycle_dividers", "symbol_full_cycle_main_strokes", "symbol_full_cycle_main_strokes_solid", "symbol_full_cycle_solid_mask",
            "symbol_full_cycle_dotted_mask", "symbol_divider_full_milli",
            "symbol_divider_dotted_milli", "symbol_crossbar_count",
            "symbol_crossbar_state_count",
        )
        if any(k not in probe for k in required):
            missing = [k for k in required if k not in probe]
            raise SCodeRequiredError("Bundled sCode optimizer returned an incomplete ABI-9 plan: " + ", ".join(missing))
        expected_symbols = {
            "pool_abi": 3, "scheduler_abi": 2, "completion_abi": 1,
            "completion_policy_count": 5, "symbol_abi": 4,
            "symbol_base": 16, "symbol_full_cycle": 16,
            "symbol_half_denominator": 2, "symbol_subscale_bits": 4,
            "symbol_variant_count": 5188, "symbol_crossbar_count": 4,
            "symbol_crossbar_state_count": 3, "symbol_full_cycle_dividers": 4,
            "symbol_full_cycle_main_strokes": 12, "symbol_full_cycle_main_strokes_solid": 12,
            "symbol_full_cycle_solid_mask": 15, "symbol_full_cycle_dotted_mask": 0,
            "symbol_divider_full_milli": 1000, "symbol_divider_dotted_milli": 500,
        }
        bad = [k for k, v in expected_symbols.items() if int(probe.get(k, -1)) != v]
        if bad:
            raise SCodeRequiredError("Bundled sCode symbol codec contract mismatch: " + ", ".join(bad))
        self._pool_catalog = self._load_pool_catalog()
        if len(self._pool_catalog) != 18:
            raise SCodeRequiredError(f"Bundled sCode pool catalog is incomplete: {len(self._pool_catalog)}/18 formats")
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
                      shape: int = 0, bypass_cache: bool = False, *,
                      editing: bool = False, low_power: bool = False,
                      budget: int = 999, dependency_ready: bool = True) -> Dict[str, int]:
        identity = stable_numeric_identity(state)
        frame_bucket = int(frame) // 4
        key = (identity, int(dirty_mask) & 255, frame_bucket, int(shape),
               int(bool(editing)), int(bool(low_power)), int(budget), int(bool(dependency_ready)))
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
            "GB_OPT_EDITING": "1" if editing else "0",
            "GB_OPT_LOW_POWER": "1" if low_power else "0",
            "GB_OPT_BUDGET": str(int(budget)),
            "GB_OPT_DEP_READY": "1" if dependency_ready else "0",
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
            raise SCodeRequiredError("Required sCode optimizer returned an invalid ABI-9 plan")
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
            "font_cache": "base16-squiggle-crossbar-subscale-v7",
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
        editing = self.editing_active(host)
        low_power = bool(getattr(host, "_scode_low_power", False))
        budget = int(getattr(host, "_scode_budget", 999) or 999)
        with self._plan_lock:
            self._last_plan = self.optimize_sync(
                cats, dirty_mask=dirty or 255, frame=self._frame, shape=shape,
                editing=editing, low_power=low_power, budget=budget, dependency_ready=True,
            )
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

    def work_key(self, kind: str, payload: Any) -> Tuple[int, str, int, int]:
        result_slot = int(self._last_plan.get(kind + "_result_slot", self._last_plan.get(kind + "_pool_slot", self._last_plan.get("pool_slot", 0)))) & 63
        generation = int(self._last_plan.get(kind + "_generation", self._last_plan.get("generation", 0)))
        return (result_slot, str(kind), generation, stable_numeric_identity(payload))

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

    def symbol_packet_key(self, payload: Any) -> Tuple[int, str, int, int]:
        """Stable sCode-selected cache identity for an immutable symbol packet."""
        slot = int(self._last_plan.get("symbol_result_slot", self._last_plan.get("symbol_pool_slot", self._last_plan.get("pool_slot", 0)))) & 63
        generation = int(self._last_plan.get("symbol_generation", self._last_plan.get("generation", 0)))
        return (slot, "symbol", generation, stable_numeric_identity(payload))

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

    def _load_pool_catalog(self) -> Dict[int, Dict[str, int]]:
        env = os.environ.copy()
        proc = subprocess.run(
            [str(self.stage0), "run", str(self.pool_catalog_script.relative_to(self.root))],
            cwd=str(self.root), env=env, capture_output=True, text=True, timeout=10,
        )
        if proc.returncode != 0:
            raise SCodeRequiredError("sCode pool catalog execution failed: " + (proc.stderr or proc.stdout).strip())
        header = self._parse(proc.stdout)
        if int(header.get("pool_catalog_abi", -1)) != 1 or int(header.get("pool_abi", -1)) != 3 or int(header.get("pool_format_count", -1)) != 18:
            raise SCodeRequiredError("sCode pool catalog ABI mismatch")
        out: Dict[int, Dict[str, int]] = {}
        for raw in proc.stdout.splitlines():
            raw = raw.strip()
            if not raw.startswith("format="):
                continue
            fields = {}
            for part in raw.split(","):
                k, v = part.split("=", 1)
                fields[k] = int(round(float(v)))
            fid = fields.pop("format")
            out[int(fid)] = fields
        return out

    @classmethod
    def _finite_index(cls, value: int) -> int:
        return int(value) % int(cls.FINITE_INFINITY)

    @classmethod
    def _pool_mix2(cls, a: int, b: int) -> int:
        return cls._finite_index(cls._finite_index(a) + 131 * cls._finite_index(b))

    @classmethod
    def _pool_mix3(cls, a: int, b: int, c: int) -> int:
        return cls._pool_mix2(cls._pool_mix2(a, b), c)

    @classmethod
    def _pool_mix4(cls, a: int, b: int, c: int, d: int) -> int:
        return cls._pool_mix2(cls._pool_mix3(a, b, c), d)

    @classmethod
    def _pool_mix6(cls, a: int, b: int, c: int, d: int, e: int, f: int) -> int:
        return cls._pool_mix2(cls._pool_mix4(a, b, c, d), cls._pool_mix2(e, f))

    @classmethod
    def _pool_slot_numeric(cls, identity: int, size: int) -> int:
        n = max(1, int(size))
        return max(0, int(identity)) % n

    @classmethod
    def _pool_generation_numeric(cls, identity: int, size: int) -> int:
        n = max(1, int(size))
        i = max(0, int(identity))
        return (i - (i % n)) // n

    @staticmethod
    def _shape_signature(payload: Any) -> Any:
        if isinstance(payload, np.ndarray):
            return ("ndarray", tuple(int(x) for x in payload.shape), str(payload.dtype))
        if isinstance(payload, (bytes, bytearray, memoryview, str, list, tuple, set, dict)):
            try:
                return (type(payload).__name__, len(payload))
            except Exception:
                pass
        shape = getattr(payload, "shape", None)
        if shape is not None:
            try:
                return (type(payload).__name__, tuple(int(x) for x in shape))
            except Exception:
                pass
        return type(payload).__name__

    def _modality_id_for(self, kind: str, format_id: int) -> int:
        key = str(kind).strip().lower().replace("-", "_")
        for prefix, mid in self._MODALITY_IDS.items():
            if key == prefix or key.startswith(prefix + "_"):
                return int(mid)
        reverse_defaults = {7: 1, 8: 2, 9: 2, 16: 3, 17: 4, 12: 7, 13: 8, 14: 6, 15: 5}
        return int(reverse_defaults.get(int(format_id), 0))

    def pool_request_descriptor(self, kind: str, payload: Any, *, format_id=None,
                                frame: Optional[int] = None, shape_id: Optional[int] = None,
                                subtype: int = 0, modality: Optional[int] = None,
                                pool_size: Optional[int] = None, dependency_ready: bool = True,
                                side_effecting: bool = False) -> Dict[str, int]:
        """Exact host mirror of sCode pool ABI-3 request arithmetic.

        The format catalog itself is executed by bundled sCode at startup. This
        mirror avoids a subprocess per hot-path request and is parity-tested
        against ``pool_request_probe.sC``.
        """
        fid = self.pool_format_id(format_id)
        spec = dict(self._pool_catalog.get(fid) or {})
        n = int(pool_size or spec.get("size", 64) or 64)
        identity = self._finite_index(stable_numeric_identity(payload))
        shape = self._finite_index(shape_id if shape_id is not None else stable_numeric_identity(self._shape_signature(payload)))
        sub = self._finite_index(subtype)
        mid = self._finite_index(self._modality_id_for(kind, fid) if modality is None else modality)
        fr = self._frame if frame is None else int(frame)
        bucket = max(0, int(fr)) // 4
        lanes = max(1, int(self._last_plan.get("parallel_width", min(8, int(os.cpu_count() or 4))) or 1))
        request_key = self._pool_mix6(identity, fid, mid, shape, sub, bucket)
        base_identity = self._pool_mix6(identity, fid, mid, shape, sub, 0)
        generation = self._pool_generation_numeric(base_identity, n)
        buffers = max(1, int(spec.get("buffers", 1)))
        base_slot = self._pool_slot_numeric(base_identity, n)
        buffer_slot = base_slot * buffers + (max(0, int(fr)) % buffers)
        result_key = self._pool_mix6(identity, fid, mid, shape, sub, generation)
        return {
            "format_id": fid, "modality": mid, "identity": identity, "shape": shape,
            "subtype": sub, "frame": int(fr), "frame_bucket": bucket,
            "pool_size": n, "buffer_count": buffers,
            "streaming": int(spec.get("streaming", 0)),
            "persistent": int(spec.get("persistent", 0)),
            "request_key": request_key,
            "slot": self._pool_slot_numeric(request_key, n),
            "generation": generation,
            "lane": self._pool_slot_numeric(request_key, lanes),
            "coalesce_slot": self._pool_slot_numeric(request_key, n),
            "buffer_slot": buffer_slot,
            "result_slot": self._pool_slot_numeric(result_key, n),
            "poolable": int(bool(dependency_ready) and not bool(side_effecting)),
        }

    @classmethod
    def completion_policy_id(cls, policy) -> int:
        if isinstance(policy, str):
            key = policy.strip().lower().replace(" ", "_")
            if key not in cls._POLICY_NAMES:
                raise ValueError(f"unknown sCode completion policy: {policy}")
            return int(cls._POLICY_NAMES[key])
        pid = int(policy)
        if pid < 0 or pid >= 5:
            raise ValueError(f"invalid sCode completion policy id: {pid}")
        return pid

    @classmethod
    def pool_format_id(cls, format_id) -> int:
        if format_id is None:
            return 0
        if isinstance(format_id, str):
            key = format_id.strip().lower().replace("-", "_").replace(" ", "_")
            if key not in cls._POOL_FORMATS:
                raise ValueError(f"unknown sCode pool format: {format_id}")
            return int(cls._POOL_FORMATS[key])
        fid = int(format_id)
        if fid < 0 or fid >= 18:
            raise ValueError(f"invalid sCode pool format id: {fid}")
        return fid

    @staticmethod
    def _policy_cacheable(policy: int) -> bool:
        return int(policy) in (0, 1)

    @staticmethod
    def _policy_coalescible(policy: int) -> bool:
        return int(policy) in (0, 1, 2, 3)

    def _start_completion_thread(self) -> None:
        if self._completion_thread is not None and self._completion_thread.is_alive():
            return
        self._completion_stop.clear()
        self._completion_thread = threading.Thread(
            target=self._completion_loop,
            daemon=True,
            name="scode-complete",
        )
        self._completion_thread.start()

    def _completion_cache_key(self, kind: str, format_id: int, payload: Any, policy: int,
                              generation: int, frame: int) -> Tuple[Any, ...]:
        # PURE is intentionally generation independent. GENERATION is tied to the
        # sCode generation. FRAME/STREAM are not memoized, but still need stable
        # request identities for coalescing/publication.
        ident = stable_numeric_identity(payload)
        gen_key = 0 if int(policy) == self.POLICY_PURE else int(generation)
        frame_key = int(frame) if int(policy) in (self.POLICY_FRAME, self.POLICY_STREAM) else 0
        return (int(format_id), str(kind), int(policy), gen_key, frame_key, ident)

    def _dispatch_completion_callback(self, callback, result, error, qt_callback: bool) -> None:
        if callback is None:
            return
        if qt_callback:
            with self._ui_lock:
                self._ui_callbacks.append((callback, result, error))
            return
        try:
            callback(result, error)
        except Exception:
            self._stats["completion_errors"] += 1

    def _drain_ui_callbacks(self, limit: int = 64) -> int:
        batch = []
        with self._ui_lock:
            n = min(max(1, int(limit)), len(self._ui_callbacks))
            if n:
                batch = self._ui_callbacks[:n]
                del self._ui_callbacks[:n]
        for callback, result, error in batch:
            try:
                callback(result, error)
            except Exception:
                self._stats["completion_errors"] += 1
            self._stats["completion_ui_delivered"] += 1
        return len(batch)

    def _completion_is_current(self, record: dict) -> bool:
        policy = int(record["policy"])
        if policy in (self.POLICY_PURE, self.POLICY_SIDE_EFFECT):
            return True
        kind = str(record["kind"])
        latest = self._latest_requests.get(kind)
        if latest is None:
            return False
        current_generation, current_frame, current_key, current_policy = latest
        if int(record["generation"]) != int(current_generation):
            return False
        if policy == self.POLICY_FRAME:
            return int(record["frame"]) == int(current_frame) and record["key"] == current_key
        if policy == self.POLICY_STREAM:
            prior = self._stream_results.get(kind)
            if prior is not None:
                prior_generation, prior_frame, _ = prior
                if int(prior_generation) > int(record["generation"]):
                    return False
                if int(prior_generation) == int(record["generation"]) and int(prior_frame) > int(record["frame"]):
                    return False
        return True

    def _completion_loop(self) -> None:
        while not self._completion_stop.is_set():
            try:
                record = self._completion_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if record is None:
                break
            key = record["key"]
            public_future = record["future"]
            callbacks = []
            with self._inflight_lock:
                callbacks = list(self._inflight_callbacks.pop(key, []))
                self._inflight.pop(key, None)
            error = record.get("error")
            result = record.get("result")
            if error is not None:
                self._stats["completion_errors"] += 1
                if not public_future.done():
                    public_future.set_exception(error)
                for callback, qt_callback in callbacks:
                    self._dispatch_completion_callback(callback, None, error, qt_callback)
                continue
            if not self._completion_is_current(record):
                self._stats["completion_stale_dropped"] += 1
                stale = SCodeStaleCompletion(
                    f"stale {record['kind']} completion generation={record['generation']} frame={record['frame']}"
                )
                if not public_future.done():
                    public_future.set_exception(stale)
                continue
            policy = int(record["policy"])
            if self._policy_cacheable(policy):
                bucket_name = "async:" + str(record["kind"])
                with self._cache_lock:
                    bucket = self._result_cache.setdefault(bucket_name, OrderedDict())
                    bucket[key] = result
                    bucket.move_to_end(key)
                    while len(bucket) > max(1, int(record.get("max_entries", 32))):
                        bucket.popitem(last=False)
            if policy == self.POLICY_STREAM:
                # Single pointer replacement: the realtime consumer only performs
                # a dictionary get and never waits on completion/cache locks.
                self._stream_results[str(record["kind"])] = (
                    int(record["generation"]), int(record["frame"]), result
                )
            if not public_future.done():
                public_future.set_result(result)
            self._stats["completion_published"] += 1
            for callback, qt_callback in callbacks:
                self._dispatch_completion_callback(callback, result, None, qt_callback)

    def submit_pooled(self, kind: str, payload: Any, producer: Callable[[], Any], *,
                      policy="generation", format_id=None, frame: Optional[int] = None,
                      callback: Optional[Callable[[Any, Optional[BaseException]], None]] = None,
                      qt_callback: bool = False, side_effecting: bool = False,
                      force: bool = False, max_entries: Optional[int] = None,
                      shape_id: Optional[int] = None, subtype: int = 0,
                      modality: Optional[int] = None, dependency_ready: bool = True) -> Future:
        """Submit one universal pool request without blocking the caller.

        Lookup/claim is synchronous and cheap. Actual computation runs on the
        sCode work executor. A dedicated completion thread validates publication
        against the current generation/frame and only then resolves the returned
        Future or queues a Qt callback. SIDE_EFFECT work never coalesces/reuses.
        """
        pid = self.completion_policy_id(self.POLICY_SIDE_EFFECT if side_effecting else policy)
        fid = self.pool_format_id(format_id)
        kind = str(kind)
        generation = int(self._last_plan.get(kind + "_generation", self._last_plan.get("generation", 0)))
        req_frame = self._frame if frame is None else int(frame)
        descriptor = self.pool_request_descriptor(
            kind, payload, format_id=fid, frame=req_frame, shape_id=shape_id,
            subtype=subtype, modality=modality, dependency_ready=dependency_ready,
            side_effecting=(pid == self.POLICY_SIDE_EFFECT),
        )
        key = self._completion_cache_key(kind, fid, payload, pid, generation, req_frame) + (
            descriptor["request_key"], descriptor["result_slot"], descriptor["buffer_slot"]
        )
        if max_entries is None:
            max_entries = int(descriptor["pool_size"])
        public_future = Future()
        if pid == self.POLICY_SIDE_EFFECT:
            # Identical side effects are intentionally distinct executions.
            with self._inflight_lock:
                self._submission_seq += 1
                key = key + ("side_effect", self._submission_seq)

        # Update latest publication window before cache/inflight checks. STREAM
        # keeps the newest generation but may still publish an earlier ready frame.
        self._latest_requests[kind] = (generation, req_frame, key, pid)

        if self._policy_cacheable(pid) and not force:
            bucket_name = "async:" + kind
            with self._cache_lock:
                bucket = self._result_cache.get(bucket_name)
                if bucket is not None and key in bucket:
                    result = bucket[key]
                    bucket.move_to_end(key)
                    self._stats["completion_cache_hits"] += 1
                    public_future.set_result(result)
                    self._dispatch_completion_callback(callback, result, None, qt_callback)
                    return public_future

        with self._inflight_lock:
            if self._policy_coalescible(pid) and not force and key in self._inflight:
                existing = self._inflight[key]
                if callback is not None:
                    self._inflight_callbacks.setdefault(key, []).append((callback, bool(qt_callback)))
                self._stats["completion_coalesced"] += 1
                return existing
            self._inflight[key] = public_future
            self._inflight_callbacks[key] = [] if callback is None else [(callback, bool(qt_callback))]

        self._stats["completion_submitted"] += 1

        def execute():
            return producer()

        worker_future = self._work_workers.submit(execute)

        def done(wf):
            try:
                result = wf.result()
                error = None
            except BaseException as exc:
                result = None
                error = exc
            self._completion_queue.put({
                "key": key, "kind": kind, "policy": pid, "format_id": fid,
                "generation": generation, "frame": req_frame,
                "result": result, "error": error, "future": public_future,
                "max_entries": int(max_entries), "descriptor": descriptor,
            })

        worker_future.add_done_callback(done)
        return public_future

    def latest_stream_result(self, kind: str, default=None):
        """Lock-free latest-ready stream read suitable for realtime callbacks."""
        item = self._stream_results.get(str(kind))
        return default if item is None else item[2]

    def latest_stream_metadata(self, kind: str):
        item = self._stream_results.get(str(kind))
        if item is None:
            return None
        return {"generation": int(item[0]), "frame": int(item[1])}

    def shutdown(self, wait: bool = False) -> None:
        try:
            self._completion_stop.set()
            self._completion_queue.put(None)
        except Exception:
            pass
        try:
            self._worker.shutdown(wait=bool(wait), cancel_futures=True)
        except Exception:
            pass
        try:
            self._work_workers.shutdown(wait=bool(wait), cancel_futures=True)
        except Exception:
            pass

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
        self._last_plan = self.optimize_sync(
            cats, dirty_mask=mask, frame=0,
            editing=self.editing_active(host),
            low_power=bool(getattr(host, "_scode_low_power", False)),
            budget=int(getattr(host, "_scode_budget", 999) or 999),
        )
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
            editing_now = self.editing_active(host)
            low_power_now = bool(getattr(host, "_scode_low_power", False))
            budget_now = int(getattr(host, "_scode_budget", 999) or 999)
            shallow_policy_key = (shallow_identity, int(editing_now), int(low_power_now), budget_now)
            shallow_changed = (self._last_shallow_identity != shallow_policy_key)
            self._last_shallow_identity = shallow_policy_key
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
            editing = editing_now
            low_power = low_power_now
            budget = budget_now
            self._pending_key = (shallow_identity, dirty, self._frame, shape, int(editing), int(low_power), budget)
            self._pending = self._worker.submit(
                self.optimize_sync, cats2, dirty, self._frame, shape, False,
                editing=editing, low_power=low_power, budget=budget, dependency_ready=True,
            )

        timer = QTimer(host)
        timer.setInterval(max(120, int(interval_ms)))
        timer.timeout.connect(tick)
        timer.start()
        self._host_timer = timer
        host._scode_optimizer_timer = timer

        # Dedicated GUI-thread publication drain. The completion worker never
        # invokes Qt widgets directly.
        completion_timer = QTimer(host)
        completion_timer.setInterval(16)
        completion_timer.timeout.connect(self._drain_ui_callbacks)
        completion_timer.start()
        self._completion_timer = completion_timer
        host._scode_completion_timer = completion_timer

    def state_for_project(self) -> Dict[str, Any]:
        return {
            "required": True,
            "abi": self.ABI,
            "pool_abi": int(self._last_plan.get("pool_abi", 0)),
            "scheduler_abi": int(self._last_plan.get("scheduler_abi", 0)),
            "completion_abi": int(self._last_plan.get("completion_abi", 0)),
            "symbol_abi": int(self._last_plan.get("symbol_abi", 0)),
            "plan": dict(self._last_plan),
            "pool_entries": len(self._pool),
            "memo_entries": sum(len(x) for x in self._result_cache.values()),
            "pool_format_catalog": {str(k): dict(v) for k, v in sorted(self._pool_catalog.items())},
            "policy": "number_logic_cross_cast_universal_pool_completion_dependency_qos_symbol_codec_v9",
            "completion": {
                "threaded": True,
                "policies": ["PURE", "GENERATION", "FRAME", "STREAM", "SIDE_EFFECT"],
                "stale_generation_rejection": True,
                "stale_frame_rejection": True,
                "side_effect_reuse": False,
                "qt_main_thread_delivery": True,
                "realtime_stream_read": "lock_free_latest_ready",
            },
            "optimizer_script": "apps/groovebox/groovebox_optimizer.sC",
            "coalescing": True,
            "reusable_buffers": True,
            "hot_path_consumers": ["canonical", "visual_preview", "background", "media_layers", "game_identity", "symbols", "project_save", "project_autosave", "audio_record", "media_probe", "media_provenance"],
            "symbol_codec": {
                "scheme": "base16-squiggle-crossbar-subscale-v7",
                "base": 16, "full_cycle": 16, "half_denominator": 2,
                "subscale_bits": 4, "variant_count": 5188,
                "crossbar_count": 4, "crossbar_states": [0, 0.5, 1],
                "full_cycle_dividers": 4, "full_cycle_main_strokes": 12,
                "full_cycle_main_strokes_solid": 12, "full_cycle_solid_mask": 15,
                "full_cycle_dotted_mask": 0,
                "divider_full_value": 1.0, "divider_dotted_value": 0.5,
                "sCode_pool_slot": int(self._last_plan.get("symbol_pool_slot", 0)),
                "sCode_result_slot": int(self._last_plan.get("symbol_result_slot", 0)),
                "sCode_generation": int(self._last_plan.get("symbol_generation", 0)),
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
