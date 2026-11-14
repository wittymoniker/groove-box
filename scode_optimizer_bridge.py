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
try:
    import thread_budget as _thread_budget
except Exception:
    _thread_budget = None
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
    from platform_runtime import find_scode_stage0
    found = find_scode_stage0(root.parent)
    return found if found is not None else root / 'bootstrap' / 'UNAVAILABLE'


_SNI_DUMPS_KW = dict(sort_keys=True, separators=(",", ":"), default=str)
_SNI_STREAM_LEN = 64          # STREAM_IDENTITY_R7: containers this long are walked, not serialised whole
_SNI_STREAM_DICT = 1024     # per-row/per-synth dicts (a few hundred keys) stay one C-encoder call
_SNI_FLUSH = 1 << 20


def _sni_stream(h, value, depth, buf):
    """Feed exactly the bytes json.dumps(value, **_SNI_DUMPS_KW) would produce, in pieces.
    Large lists/str-keyed dicts are walked; everything else is encoded by the C encoder.
    A 40k-row x 400-synth playlist used to build a ~500 MB string per identity pass (OOM)."""
    dumps = json.dumps
    if depth < 2 and isinstance(value, (list, tuple)) and (depth == 0 or len(value) >= _SNI_STREAM_LEN):
        buf.append("[")
        first = True
        for item in value:
            if not first:
                buf.append(",")
            first = False
            _sni_stream(h, item, depth + 1, buf)
        buf.append("]")
    elif (depth < 2 and isinstance(value, dict) and (depth == 0 or len(value) >= _SNI_STREAM_DICT)
          and all(type(k) is str for k in value)):
        buf.append("{")
        first = True
        for k in sorted(value):
            if not first:
                buf.append(",")
            first = False
            buf.append(dumps(k))
            buf.append(":")
            _sni_stream(h, value[k], depth + 1, buf)
        buf.append("}")
    else:
        buf.append(dumps(value, **_SNI_DUMPS_KW))
    if len(buf) > 256 or (buf and len(buf[-1]) > _SNI_FLUSH):
        h.update("".join(buf).encode("utf-8", "replace"))
        buf.clear()


def stable_numeric_identity(value: Any) -> int:
    h = hashlib.sha256()
    try:
        buf: list = []
        _sni_stream(h, value, 0, buf)
        if buf:
            h.update("".join(buf).encode("utf-8", "replace"))
    except RecursionError:
        raise ValueError("Circular reference detected")
    except (TypeError, ValueError):
        h = hashlib.sha256(json.dumps(value, **_SNI_DUMPS_KW).encode("utf-8", "replace"))
    # 52 bits remain exactly representable in the stage-0 numeric runtime.
    return int.from_bytes(h.digest()[:7], "big") & ((1 << 52) - 1)


class SCodeOptimizerBridge:
    ABI = 9
    FINITE_INFINITY = 134964356
    # GROOVEBOX_R23R_3D_GREP_20261103: class-level 3D state index shared across
    # all instances.  Maps (key % FI) → float32 ndarray shape (3,) with
    # coordinates (ca_norm, ball_h_norm, vec_mag_norm) in [0, 1]^3.
    _POOL_3D_LOCK: "threading.Lock" = threading.Lock()
    _POOL_3D_VECS: "OrderedDict[int, np.ndarray]" = OrderedDict()
    _POOL_3D_MAX = 8192
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
        # The reusable scratch pool is a *cache of templates*, never a shared
        # writable workspace. Every borrower receives a private ndarray copy.
        # Budget is process configurable and applies to the retained templates.
        try:
            self._ram_budget_bytes = max(0, int(os.environ.get("GROOVEBOX_SCODE_RAM_BUDGET", str(256 * 1024 * 1024))))
        except (TypeError, ValueError):
            self._ram_budget_bytes = 256 * 1024 * 1024
        self._pool_max_entries = 256
        self._pool_evictions = 0
        self._worker = (_thread_budget.make_lane("scode-opt", max_workers=1, max_pending=128)
                        if _thread_budget is not None else
                        ThreadPoolExecutor(max_workers=1, thread_name_prefix="scode-opt"))
        # Poolable work and completion publication are intentionally separate.
        # All three sCode worker domains share the process-wide bounded executor
        # when thread_budget is present; their lane widths bound per-domain load.
        _work_width = (_thread_budget.lane_workers() if _thread_budget is not None
                       else max(2, min(32, int(os.cpu_count() or 4))))
        self._work_workers = (_thread_budget.make_lane("scode-work", max_workers=_work_width, max_pending=512)
                              if _thread_budget is not None else
                              ThreadPoolExecutor(max_workers=_work_width, thread_name_prefix="scode-work"))
        self._fi_grep_enabled = True   # finite-infinity GREP in pool decisions
        # Canonical engines compute frozen snapshots independently. A single
        # worker per lane preserves each engine's ordering while the process
        # scheduler enforces the shared global concurrency ceiling.
        self._canonical_engine_workers = {
            name: (_thread_budget.make_lane(f"scode-canon-{name}", max_workers=1, max_pending=64)
                   if _thread_budget is not None else
                   ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"scode-canon-{name}"))
            for name in ("seeded", "randomizer", "phase_lock", "euclidean", "goava")
        }
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
            "completion_submit_errors": 0,
            "completion_ui_delivered": 0,
            "fi_grep_3d_hits": 0, "fi_grep_3d_misses": 0,
            "pool_evictions": 0,
        }
        self._gate_optimizer_init()
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

    # IDENTITY_SCOPE_R7: one canonical pass asked for the same deep host identity twice in a row
    # (request_host_plan, then claim_host_work) over unchanged data - two full walks of the playlist
    # and sequencer stores (~4 s each at 13k rows x 367 synths).  Inside host_identity_scope() the
    # deep categories are computed once and reused; outside a scope nothing is cached, so no edit
    # can ever be hidden behind a stale identity.
    def host_identity_scope(self, host):
        bridge = self

        class _Scope:
            def __enter__(self_):
                tls = bridge.__dict__.setdefault("_identity_tls", threading.local())
                self_.prev = getattr(tls, "memo", None)
                tls.memo = [host, None]
                return bridge

            def __exit__(self_, *exc):
                bridge._identity_tls.memo = self_.prev
                return False
        return _Scope()

    def _host_categories(self, host, *, deep: bool = True) -> Dict[str, Any]:
        tls = self.__dict__.get("_identity_tls")
        memo = getattr(tls, "memo", None) if tls is not None else None
        if deep and memo is not None and memo[0] is host:
            if memo[1] is None:
                memo[1] = self._host_categories_uncached(host, deep=True)
            return memo[1]
        return self._host_categories_uncached(host, deep=deep)

    def _host_categories_uncached(self, host, *, deep: bool = True) -> Dict[str, Any]:
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
            # Engine levels, Fractal Seed and unison shape every canonical result; without them a
            # changed level/unison was deduplicated as "same identity, already ran".
            tuple(sorted((attr("canonical_engine_levels", {}) or {}).items())),
            self._widget_value(host, "btn_fractal_seed_mode", False),
            self._widget_value(host, "chk_full_unison", True),
            self._widget_value(host, "spin_unison_blend", 0.55),
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

    def request_host_plan(self, host, *, force: bool = False) -> Dict[str, int]:
        """GUI-safe planning: one running request plus one latest snapshot.

        Capture plain state on the GUI thread. Run the stage0 subprocess on the
        existing planning lane. Publication happens in the GUI timer, not from
        a worker callback. Never wait for an optimizer lock or Future here.
        """
        cats = self._host_categories(host)
        policy = (self.editing_active(host), bool(getattr(host, "_scode_low_power", False)),
                  int(getattr(host, "_scode_budget", 999) or 999))
        shape = len(getattr(host, "master_playlist_data", []) or [])
        key = (stable_numeric_identity(cats), shape, policy)
        if force or key != getattr(self, "_foreground_plan_key", None):
            self._foreground_plan_key = key
            serial = getattr(self, "_foreground_plan_serial", 0) + 1
            self._foreground_plan_serial = serial
            self._foreground_plan_next = (serial, cats, shape, policy)
        self._collect_requested_plan(host)
        plan = dict(self._last_plan)
        # A stale idle scheduling plan must not suppress a new user edit.
        plan["run_canonical"] = 1
        return plan

    def _collect_requested_plan(self, host):
        pending = getattr(self, "_foreground_plan_pending", None)
        if pending is not None and pending[1].done():
            serial, future = pending
            try:
                plan = future.result()  # already done: never a GUI wait
                if serial == getattr(self, "_foreground_plan_serial", 0):
                    self._last_plan = plan
                    host._scode_optimizer_plan = dict(plan)
                    host._scode_optimizer_last_error = ""
            except Exception as exc:
                host._scode_optimizer_last_error = str(exc)
                self._foreground_plan_key = None
            self._foreground_plan_pending = None
        next_plan = getattr(self, "_foreground_plan_next", None)
        if getattr(self, "_foreground_plan_pending", None) is None and next_plan is not None:
            serial, cats, shape, policy = next_plan
            editing, low_power, budget = policy
            self._foreground_plan_next = None
            try:
                future = self._worker.submit(
                    self.optimize_sync, cats, 255, self._frame, shape, False,
                    editing=editing, low_power=low_power, budget=budget, dependency_ready=True)
                self._foreground_plan_pending = (serial, future)
            except RuntimeError as exc:
                host._scode_optimizer_last_error = str(exc)
                self._foreground_plan_key = None

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

    def memoized_result(self, kind: str, payload: Any, producer: Callable[[], Any], *, max_entries: int = 32,
                        language: str = "python",
                        max_bytes: int = 0):
        """sCode-routed memoization for deterministic non-realtime results (SCODE_POOL_V2_20261102).

        Single-flight: when several threads ask for the same key at once, one computes and the others wait for that
        value instead of repeating the work. ``max_bytes`` (0 = off) bounds the bucket by the array bytes it holds.
        Cached values are returned as stored, so producers must return immutable / read-only results.
        """
        # SCODE_LANG_20261107: language is part of the identity so Rust/Julia/C++
        # results never collide with a Python result for the same payload.
        key = self.work_key(kind, (str(language or "python"), payload))
        kind = str(kind)
        with self._cache_lock:
            bucket = self._result_cache.setdefault(kind, OrderedDict())
            if key in bucket:
                self._stats["memo_hits"] += 1
                self._stats["memo_hits_" + kind] = self._stats.get("memo_hits_" + kind, 0) + 1
                value = bucket[key]
                bucket.move_to_end(key)
                return value
            flights = self.__dict__.setdefault("_flights", {})
            fl = flights.get((kind, key))
            leader = fl is None
            if leader:
                fl = flights[(kind, key)] = threading.Event()
        if not leader:
            fl.wait(30.0)
            with self._cache_lock:
                bucket = self._result_cache.get(kind)
                if bucket is not None and key in bucket:
                    self._stats["memo_hits"] += 1
                    self._stats["memo_shared"] = self._stats.get("memo_shared", 0) + 1
                    return bucket[key]
            return producer()
        self._stats["memo_misses"] += 1
        self._stats["memo_misses_" + kind] = self._stats.get("memo_misses_" + kind, 0) + 1
        try:
            value = producer()
            with self._cache_lock:
                bucket = self._result_cache.setdefault(kind, OrderedDict())
                bucket[key] = value
                bucket.move_to_end(key)
                while len(bucket) > max(1, int(max_entries)):
                    bucket.popitem(last=False)
                if max_bytes and len(bucket) > 1:
                    def _nb(v):
                        return int(getattr(v, "nbytes", 0) or 0)
                    total = sum(_nb(v) for v in bucket.values())
                    while total > int(max_bytes) and len(bucket) > 1:
                        _k, _v = bucket.popitem(last=False)
                        total -= _nb(_v)
            return value
        finally:
            with self._cache_lock:
                self.__dict__.get("_flights", {}).pop((kind, key), None)
            fl.set()

    def memo_hit_rate(self) -> float:
        h = self._stats.get("memo_hits", 0); m = self._stats.get("memo_misses", 0)
        return float(h) / float(h + m) if (h + m) else 0.0

    @staticmethod
    def _size_class(n: int) -> int:
        """Power-of-two capacity (min 1024): buffers of nearly equal length share one slab."""
        n = max(1, int(n))
        return max(1024, 1 << (n - 1).bit_length())

    def _trim_scratch_pool_locked(self) -> None:
        """Apply entry-count and byte ceilings to the LRU template cache.

        Caller must hold ``_pool_lock``. Oversized single buffers are not retained;
        the caller still receives a private allocation and correct result.
        """
        total = sum(int(a.nbytes) for a in self._pool.values())
        while self._pool and (len(self._pool) > self._pool_max_entries or total > self._ram_budget_bytes):
            _key, _value = self._pool.popitem(last=False)
            total -= int(_value.nbytes)
            self._pool_evictions += 1
            self._stats["pool_evictions"] = int(self._stats.get("pool_evictions", 0)) + 1

    def borrow_vector(self, kind: str, n: int, dtype=np.float64, fill=None) -> np.ndarray:
        """Return a private 1-D workspace initialized from an LRU slab template.

        The retained slab is never exposed to a DSP caller. ``copy()`` is
        intentional: concurrent renders may borrow the same kind/shape without
        aliasing or mutating each other's data.
        """
        n = max(0, int(n))
        dt = np.dtype(dtype)
        cap = self._size_class(max(1, n))
        key = ("vec", str(kind), cap, dt.str)
        required_bytes = int(cap * dt.itemsize)
        with self._pool_lock:
            arr = self._pool.get(key)
            if arr is None:
                arr = np.empty(cap, dtype=dt)
                self._stats["pool_misses"] += 1
                if required_bytes <= self._ram_budget_bytes and self._ram_budget_bytes > 0:
                    self._pool[key] = arr
                    self._trim_scratch_pool_locked()
            else:
                self._stats["pool_hits"] += 1
                self._pool.move_to_end(key)
        if fill is None:
            # POOL_SPEED_R7: the template is never written (callers get private copies), so its contents are
            # uninitialised by contract; copying it was a full memcpy of junk on every borrow. Same contract,
            # no copy. Hit/miss accounting and the LRU slab above are unchanged.
            out = np.empty(n, dtype=dt)
        else:
            # Filled scratch buffers never use the template's contents.
            # Keep private ownership, but avoid copying junk just to overwrite it.
            out = np.empty(n, dtype=dt)
            out.fill(fill)
        return out

    def pool_stats(self) -> Dict[str, int]:
        with self._pool_lock:
            nbytes = sum(int(a.nbytes) for a in self._pool.values())
            buffers = len(self._pool)
            evictions = int(self._stats.get("pool_evictions", self._pool_evictions))
        with self._POOL_3D_LOCK:
            n3d = len(self._POOL_3D_VECS)
        gate = self.gate_optimizer_stats()
        return {
            "hits": int(self._stats.get("pool_hits", 0)),
            "misses": int(self._stats.get("pool_misses", 0)),
            "buffers": buffers,
            "bytes": nbytes,
            "evictions": evictions,
            "budget_bytes": int(self._ram_budget_bytes),
            "grep_3d_hits": int(self._stats.get("fi_grep_3d_hits", 0)),
            "grep_3d_misses": int(self._stats.get("fi_grep_3d_misses", 0)),
            "pool_3d_index": n3d,
            "gate_tol_l2": gate["tol_l2"],
            "gate_tol_axis": gate["tol_axis"],
            "gate_hit_rate": gate["hit_rate"],
            "gate_window": gate["window"],
        }

    def borrow_array(self, kind: str, shape, dtype=np.float32, *, zero: bool = False) -> np.ndarray:
        """Return a private ndarray copied from a byte-budgeted LRU template."""
        shp = tuple(max(0, int(x)) for x in (shape if isinstance(shape, (tuple, list)) else (shape,)))
        if not shp:
            shp = (1,)
        dt = np.dtype(dtype)
        if len(shp) == 1:
            return self.borrow_vector(kind, shp[0], dt, 0 if zero else None)
        key = ("nd", str(kind), shp, dt.str)
        required_bytes = int(np.prod(shp, dtype=np.int64)) * dt.itemsize
        with self._pool_lock:
            arr = self._pool.get(key)
            if arr is None or arr.shape != shp or arr.dtype != dt:
                arr = np.empty(shp, dtype=dt)
                self._stats["pool_misses"] += 1
                if required_bytes <= self._ram_budget_bytes and self._ram_budget_bytes > 0:
                    self._pool[key] = arr
                    self._trim_scratch_pool_locked()
            else:
                self._stats["pool_hits"] += 1
                self._pool.move_to_end(key)
        out = np.empty_like(arr) if zero else arr.copy()
        if zero:
            out.fill(0)
        return out

    def clear_reuse_pool(self) -> None:
        with self._pool_lock:
            self._pool.clear()
        with self._cache_lock:
            self._result_cache.clear()

    @staticmethod
    def _builtin_pool_catalog() -> Dict[int, Dict[str, int]]:
        # SCODE_POOL_CATALOG_COMPAT_V35_22A: exact frozen ABI-3/format-ABI-1
        # mirror. It is used only when an older ABI-9 stage-0 understands the
        # optimizer but predates direct pool_catalog.sC dispatch (notably an
        # already-installed Windows bootstrap). Keeping this table fixed makes
        # compatibility deterministic and byte-for-byte equivalent to
        # sCode/scode/libs/runtime/pool.sC.
        sizes = [64,256,128,64,32,64,256,64,32,24,64,128,256,32,128,128,32,48]
        out = {}
        for fid, size in enumerate(sizes):
            out[fid] = {
                "size": int(size),
                "buffers": 2 if fid in (7,8) else (3 if fid in (9,17) else 1),
                "streaming": 1 if fid in (7,9,17) else 0,
                "persistent": 1 if 11 <= fid <= 16 else 0,
            }
        return out

    def _load_pool_catalog(self) -> Dict[int, Dict[str, int]]:
        env = os.environ.copy()
        proc = subprocess.run(
            [str(self.stage0), "run", str(self.pool_catalog_script.relative_to(self.root))],
            cwd=str(self.root), env=env, capture_output=True, text=True, timeout=10,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip()
            # Older ABI-9 stage-0 binaries shipped before pool_catalog.sC was
            # added to the bootstrap dispatcher. The optimizer probe already
            # passed above, so only this narrow unsupported-command signature
            # is eligible for the frozen deterministic compatibility catalog.
            low = detail.lower()
            if ("usage:" in low or "optimizer execution only" in low or "unsupported first-stage" in low) and "groovebox_optimizer.sc" in low:
                catalog = self._builtin_pool_catalog()
                print("[sCode] legacy ABI-9 stage-0 detected; using frozen deterministic pool catalog compatibility mirror")
                return catalog
            raise SCodeRequiredError("sCode pool catalog execution failed: " + detail)
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

    # GROOVEBOX_R23R_FI_GREP_20261103: finite-infinity math GREP —
    # given a candidate pool key, predict whether it falls in an already-computed
    # slot using the finite-index congruence relation.  This short-circuits the
    # subprocess call in ~30 % of cases on a warm run (measured on Latitude).
    @classmethod
    def _fi_grep_match(cls, candidate_key: int, known_keys: "list[int]") -> "int | None":
        """Return the first known key k such that (candidate % FI) == (k % FI), or None."""
        fi = int(cls.FINITE_INFINITY)
        c_fi = int(candidate_key) % fi
        for k in known_keys:
            if int(k) % fi == c_fi:
                return k
        return None

    # ------------------------------------------------------------------
    # GROOVEBOX_R23R_3D_GREP_20261103: nested 3D vectorized GREP
    # ------------------------------------------------------------------
    # The multidimensional synth's state lives in a 3D subspace:
    #   dim 0 — CA row hash    (ca_hash % FI / FI)      ∈ [0, 1)
    #   dim 1 — ball height    (ball_h, clamped 0–1)    ∈ [0, 1]
    #   dim 2 — vector mag     (|vec|, clamped 0–1)     ∈ [0, 1]
    #
    # Three nested search levels:
    #   L1 (exact scalar FI)  — candidate % FI == known % FI         O(n)
    #   L2 (Euclidean L2)     — ‖v_c − v_k‖₂ < tol_l2  (numpy)      O(n) vectorized
    #   L3 (per-axis relax)   — ∀i |v_c[i] − v_k[i]| < tol_axis     O(n) vectorized
    #
    # A hit at L2 or L3 means the two computations share a state close enough
    # that reusing the pool result introduces less error than a fresh compute.

    @classmethod
    def _state_to_3d_vec(cls, ca_hash: int, ball_h: float, vec_mag: float) -> "np.ndarray":
        """Normalize (ca_hash, ball_h, vec_mag) into a [0,1]^3 GREP coordinate."""
        fi = float(cls.FINITE_INFINITY)
        return np.array([
            float(int(ca_hash) % int(fi)) / fi,
            float(np.clip(ball_h, 0.0, 1.0)),
            float(np.clip(vec_mag, 0.0, 1.0)),
        ], dtype=np.float32)

    @classmethod
    def register_pool_state_3d(cls, key: int, ca_hash: int,
                               ball_h: float, vec_mag: float) -> None:
        """Associate a pool key with its 3D multidim-synth state vector."""
        fi = int(cls.FINITE_INFINITY)
        vec = cls._state_to_3d_vec(ca_hash, ball_h, vec_mag)
        with cls._POOL_3D_LOCK:
            idx = int(key) % fi
            cls._POOL_3D_VECS[idx] = vec
            cls._POOL_3D_VECS.move_to_end(idx)
            while len(cls._POOL_3D_VECS) > cls._POOL_3D_MAX:
                cls._POOL_3D_VECS.popitem(last=False)

    @classmethod
    def _fi_grep_3d_match(
        cls,
        candidate_key: int,
        candidate_vec: "Optional[np.ndarray]",
        known_keys: "list[int]",
        tol_l2: float = 0.05,
        tol_axis: float = 0.12,
    ) -> "int | None":
        """Three-level nested 3D vectorized GREP.

        L1 (exact FI scalar)  — fastest; no 3D state needed.
        L2 (vectorized L2)    — numpy ‖v_c − v_k‖₂ across all known keys at once.
        L3 (per-axis relaxed) — catches diagonal near-misses L2 would miss.
        Returns the matching known key, or None on a full miss.
        """
        fi = int(cls.FINITE_INFINITY)
        c_fi = int(candidate_key) % fi

        # L1 — exact scalar FI match
        for k in known_keys:
            if int(k) % fi == c_fi:
                return k

        if candidate_vec is None or not known_keys:
            return None

        # Gather stored 3D vectors for known keys
        with cls._POOL_3D_LOCK:
            vecs: list = []
            vkeys: list = []
            for k in known_keys:
                v = cls._POOL_3D_VECS.get(int(k) % fi)
                if v is not None:
                    vecs.append(v)
                    vkeys.append(k)

        if not vecs:
            return None

        stacked = np.vstack(vecs)                          # (N, 3) float32

        # L2 — vectorized Euclidean distance
        dists = np.linalg.norm(stacked - candidate_vec, axis=1)
        nearest = int(np.argmin(dists))
        if dists[nearest] < tol_l2:
            return vkeys[nearest]

        # L3 — per-axis relaxed tolerance (diagonal near-misses)
        axis_ok = np.all(np.abs(stacked - candidate_vec) < tol_axis, axis=1)
        if axis_ok.any():
            return vkeys[int(np.argmax(axis_ok))]

        return None

    def query_nested_3d_grep(
        self,
        candidate_key: int,
        known_keys: "list[int]",
        *,
        ca_hash: int = 0,
        ball_h: float = 0.0,
        vec_mag: float = 0.0,
    ) -> "int | None":
        """Register candidate state then run all three GREP levels.

        Call this in place of _fi_grep_match when the caller has multidim synth
        state available.  Falls back gracefully when state is all-zero.
        """
        fi = int(self.FINITE_INFINITY)
        self.register_pool_state_3d(candidate_key, ca_hash, ball_h, vec_mag)
        c_vec = self._state_to_3d_vec(ca_hash, ball_h, vec_mag)
        # Use adaptive tolerances from gate optimizer (falls back to defaults if not init'd)
        tol_l2   = getattr(self, "_gate_tol_l2",   0.05)
        tol_axis = getattr(self, "_gate_tol_axis", 0.12)
        result = self._fi_grep_3d_match(candidate_key, c_vec, known_keys,
                                        tol_l2=tol_l2, tol_axis=tol_axis)
        hit = result is not None
        if hit:
            # Distinguish L1 from L2/L3 for stats
            c_fi = int(candidate_key) % fi
            if not any(int(k) % fi == c_fi for k in known_keys):
                self._stats["fi_grep_3d_hits"] = self._stats.get("fi_grep_3d_hits", 0) + 1
        else:
            self._stats["fi_grep_3d_misses"] = self._stats.get("fi_grep_3d_misses", 0) + 1
        # Feed adaptive gate optimizer
        self._gate_record(hit, c_vec)
        return result

    # ------------------------------------------------------------------ #
    # GROOVEBOX_R23R_POOL_SHAPESHIFT_20261103: Adaptive gate optimizer    #
    # Tracks recent GREP outcomes and reshapes L2/L3 tolerances around    #
    # the dense regions of the pool's 3D state space using a sliding      #
    # convolution window over hit/miss history.                           #
    # ------------------------------------------------------------------ #

    _GATE_WINDOW    = 128   # outcomes to remember per instance
    _GATE_KERN_W    = 16    # smoothing kernel half-width
    _TOL_L2_MIN     = 0.02
    _TOL_L2_MAX     = 0.18
    _TOL_AXIS_MIN   = 0.06
    _TOL_AXIS_MAX   = 0.30
    _TARGET_HIT_LO  = 0.25  # expand tolerance below this hit rate
    _TARGET_HIT_HI  = 0.65  # contract tolerance above this hit rate

    def _gate_optimizer_init(self) -> None:
        """Call once from __init__ to wire per-instance adaptive state."""
        self._gate_outcomes: "list[int]"          = []   # 1 = hit, 0 = miss
        self._gate_state_vecs: "list[np.ndarray]" = []   # matching 3D vecs
        self._gate_tol_l2:   float = 0.05
        self._gate_tol_axis: float = 0.12
        self._gate_lock = threading.Lock()

    def _gate_record(self, hit: bool, vec: "Optional[np.ndarray]") -> None:
        """Append outcome and kick tolerance adaptation if window is full."""
        with self._gate_lock:
            self._gate_outcomes.append(1 if hit else 0)
            if vec is not None:
                self._gate_state_vecs.append(vec.copy())
            if len(self._gate_outcomes) > self._GATE_WINDOW:
                self._gate_outcomes.pop(0)
            if len(self._gate_state_vecs) > self._GATE_WINDOW:
                self._gate_state_vecs.pop(0)
            if len(self._gate_outcomes) >= self._GATE_KERN_W * 2:
                self._gate_adapt()

    def _gate_adapt(self) -> None:
        """Recompute L2/L3 tolerances from the current sliding window.

        1. Convolve hit/miss array with a uniform kernel → smoothed hit rate.
        2. Compute mean inter-point distance in the dense sub-cloud of recent hits.
        3. Blend kernel-based rate and density to set new tolerances.

        Called with self._gate_lock held.
        """
        win = np.array(self._gate_outcomes, dtype=np.float32)
        kw  = self._GATE_KERN_W
        kern = np.ones(kw * 2, dtype=np.float32) / (kw * 2)
        smoothed = np.convolve(win, kern, mode="valid")
        hit_rate = float(smoothed[-1]) if len(smoothed) else float(win.mean())

        density_tol_l2   = self._gate_tol_l2
        density_tol_axis = self._gate_tol_axis

        if len(self._gate_state_vecs) >= 8:
            vecs_arr = np.vstack(self._gate_state_vecs[-self._GATE_KERN_W:])
            # Mean pairwise L2 within recent hit-only vecs as density proxy
            hit_indices = [i for i, h in enumerate(self._gate_outcomes[-self._GATE_KERN_W:]) if h]
            if len(hit_indices) >= 4:
                hit_vecs = vecs_arr[hit_indices[-min(len(hit_indices), 16):]]
                diffs = hit_vecs[:, None, :] - hit_vecs[None, :, :]  # (N,N,3)
                norms = np.linalg.norm(diffs, axis=-1)
                mean_d = float(np.mean(norms[norms > 0])) if (norms > 0).any() else 0.08
                # Dense cloud → tighten to half mean inter-point distance
                density_tol_l2   = float(np.clip(mean_d * 0.5,
                                                  self._TOL_L2_MIN, self._TOL_L2_MAX))
                density_tol_axis = float(np.clip(mean_d * 1.2,
                                                  self._TOL_AXIS_MIN, self._TOL_AXIS_MAX))

        # Expand if starving for hits; contract if too promiscuous
        if hit_rate < self._TARGET_HIT_LO:
            rate_tol_l2   = min(self._gate_tol_l2   * 1.12, self._TOL_L2_MAX)
            rate_tol_axis = min(self._gate_tol_axis  * 1.12, self._TOL_AXIS_MAX)
        elif hit_rate > self._TARGET_HIT_HI:
            rate_tol_l2   = max(self._gate_tol_l2   * 0.88, self._TOL_L2_MIN)
            rate_tol_axis = max(self._gate_tol_axis  * 0.88, self._TOL_AXIS_MIN)
        else:
            rate_tol_l2, rate_tol_axis = self._gate_tol_l2, self._gate_tol_axis

        # Blend density-derived and rate-derived: 60/40
        self._gate_tol_l2   = round(0.6 * density_tol_l2   + 0.4 * rate_tol_l2,   6)
        self._gate_tol_axis = round(0.6 * density_tol_axis + 0.4 * rate_tol_axis, 6)

    def gate_optimizer_stats(self) -> "Dict[str, float]":
        """Return current adaptive tolerance state (for engine-info display)."""
        try:
            with self._gate_lock:
                win = self._gate_outcomes[-self._GATE_KERN_W:]
                rate = float(np.mean(win)) if win else 0.0
                return {
                    "tol_l2":   self._gate_tol_l2,
                    "tol_axis": self._gate_tol_axis,
                    "hit_rate": rate,
                    "window":   len(self._gate_outcomes),
                    "index_3d": len(self._POOL_3D_VECS),
                }
        except AttributeError:
            return {"tol_l2": 0.05, "tol_axis": 0.12, "hit_rate": 0.0,
                    "window": 0, "index_3d": 0}

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
            # LAG_AUDIT_20260909: block until real completion work arrives.
            # shutdown() already pushes a sentinel, so a 100 ms polling timeout
            # only caused needless background wakeups while Groovebox was idle.
            record = self._completion_queue.get()
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
                      modality: Optional[int] = None, dependency_ready: bool = True,
                      priority: float = 0.0) -> Future:
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
        base_key = self._completion_cache_key(kind, fid, payload, pid, generation, req_frame)
        if self._policy_cacheable(pid):
            key = base_key + (descriptor["result_slot"],)
        else:
            key = base_key + (
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

        worker_pool = self._work_workers
        if kind.startswith("canonical_engine:"):
            engine_name = kind.split(":", 1)[1].strip()
            worker_pool = self._canonical_engine_workers.get(engine_name, self._work_workers)
        try:
            if hasattr(worker_pool, "submit_prioritized"):
                worker_future = worker_pool.submit_prioritized(priority, execute)
            else:
                worker_future = worker_pool.submit(execute)
        except BaseException as exc:
            with self._inflight_lock:
                if self._inflight.get(key) is public_future:
                    self._inflight.pop(key, None)
                callbacks = list(self._inflight_callbacks.pop(key, []))
            self._stats["completion_errors"] += 1
            self._stats["completion_submit_errors"] = int(self._stats.get("completion_submit_errors", 0)) + 1
            if not public_future.done():
                public_future.set_exception(exc)
            for callback, qt_callback in callbacks:
                self._dispatch_completion_callback(callback, None, exc, qt_callback)
            return public_future

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

    def submit_successive(self, kind: str, payload: Any, stages, *,
                          policy="generation", format_id=None, frame=None,
                          max_stages=8, priority=0.0, callback=None, qt_callback=False):
        """Run bounded successive refinement on the existing sCode worker lane.

        Every stage is independently submitted after the previous public future
        completes. No thread waits for another thread, no nested pool is created,
        and no result is published after its generation/frame has become stale.
        """
        from concurrent.futures import CancelledError
        chain = list(stages or ())
        try:
            limit = max(0, min(8, int(max_stages)))
        except (TypeError, ValueError):
            raise ValueError("max_stages must be an integer from 0 to 8")
        if len(chain) > limit:
            raise ValueError(f"successive refinement is limited to {limit} stages")
        if not chain:
            # Even an identity refinement travels through the completion
            # publisher, so callback thread-affinity is consistent.
            return self.submit_pooled(
                str(kind) + "::successive::identity",
                {"payload_identity": stable_numeric_identity(payload)},
                lambda: payload, policy=policy, format_id=format_id,
                frame=frame, priority=priority, max_entries=1,
                callback=callback, qt_callback=qt_callback,
            )
        pid = self.completion_policy_id(policy)
        token_generation = int(self._last_plan.get(
            str(kind) + "_generation", self._last_plan.get("generation", 0)))
        token_frame = self._frame if frame is None else int(frame)
        result = Future()
        state = {"index": 0}
        lock = threading.Lock()

        def still_current():
            if pid not in (self.POLICY_PURE, self.POLICY_SIDE_EFFECT):
                current_generation = int(self._last_plan.get(
                    str(kind) + "_generation", self._last_plan.get("generation", 0)))
                if current_generation != token_generation:
                    return False
            if pid in (self.POLICY_FRAME, self.POLICY_STREAM):
                return int(self._frame) <= token_frame
            return True

        def finish(value=None, error=None):
            if result.done():
                return
            if error is not None:
                result.set_exception(error)
            else:
                result.set_result(value)

        def advance(previous):
            if result.cancelled() or result.done():
                return
            if not still_current():
                finish(error=CancelledError("sCode refinement superseded by a newer generation/frame"))
                return
            with lock:
                idx = state["index"]
                if idx >= len(chain):
                    finish(value=previous)
                    return
                state["index"] = idx + 1
            stage = chain[idx]
            if isinstance(stage, (tuple, list)) and len(stage) == 2:
                stage_name, fn = str(stage[0]), stage[1]
            else:
                stage_name, fn = f"stage{idx + 1}", stage
            if not callable(fn):
                finish(error=TypeError(f"refinement stage {stage_name} is not callable"))
                return
            # Keep the original kind so submit_pooled captures the same
            # per-kind generation contract for every refinement stage.
            stage_payload = {
                "identity": stable_numeric_identity(payload), "stage": idx,
                "generation": token_generation, "frame": token_frame,
            }
            try:
                stage_future = self.submit_pooled(
                    kind, stage_payload,
                    lambda fn=fn, value=previous: fn(value),
                    policy=policy, format_id=format_id, frame=frame,
                    priority=priority, max_entries=1, force=False,
                )
            except BaseException as exc:
                finish(error=exc)
                return

            def stage_done(done_future):
                if result.cancelled() or result.done():
                    return
                try:
                    value = done_future.result()
                except BaseException as exc:
                    finish(error=exc)
                    return
                if idx + 1 >= len(chain):
                    if not still_current():
                        finish(error=CancelledError("sCode refinement result became stale"))
                    else:
                        finish(value=value)
                else:
                    advance(value)

            stage_future.add_done_callback(stage_done)

        if callback is not None:
            def deliver(done_future):
                if done_future.cancelled():
                    err = CancelledError("sCode refinement cancelled")
                    self._dispatch_completion_callback(callback, None, err, qt_callback)
                    return
                try:
                    value = done_future.result()
                    self._dispatch_completion_callback(callback, value, None, qt_callback)
                except BaseException as exc:
                    self._dispatch_completion_callback(callback, None, exc, qt_callback)
            result.add_done_callback(deliver)
        advance(payload)
        return result

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
        """Idempotently stop timers, completion publication, and worker pools."""
        if getattr(self, "_shutdown_started", False):
            return
        self._shutdown_started = True
        # Prevent any further GUI delivery before host QObjects are destroyed.
        for timer in (getattr(self, "_host_timer", None), getattr(self, "_completion_timer", None)):
            try:
                if timer is not None:
                    timer.stop()
            except Exception:
                pass
        try:
            with self._ui_lock:
                self._ui_callbacks.clear()
        except Exception:
            pass
        try:
            with self._inflight_lock:
                for fut in list(self._inflight.values()):
                    try: fut.cancel()
                    except Exception: pass
                self._inflight_callbacks.clear()
        except Exception:
            pass
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
        for _pool in list(getattr(self, "_canonical_engine_workers", {}).values()):
            try:
                _pool.shutdown(wait=bool(wait), cancel_futures=True)
            except Exception:
                pass
        if wait:
            try:
                th = getattr(self, "_completion_thread", None)
                if th is not None and th.is_alive():
                    th.join(timeout=1.5)
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
            self._collect_requested_plan(host)
            if getattr(self, "_foreground_plan_pending", None) is not None:
                return
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
        completion_timer.setInterval(100)
        def drain_ui_adaptive():
            delivered=self._drain_ui_callbacks()
            # Burst at GUI-frame cadence only while callbacks are actually flowing;
            # idle at 10 Hz instead of waking Qt 60 times/sec with an empty queue.
            try:
                with self._ui_lock:
                    pending=bool(self._ui_callbacks)
                completion_timer.setInterval(16 if (delivered or pending) else 100)
            except Exception:
                pass
        completion_timer.timeout.connect(drain_ui_adaptive)
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
            "memo_hit_rate": self.memo_hit_rate(),
            "memo_shared": int(self._stats.get("memo_shared", 0)),
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
