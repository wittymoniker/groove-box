"""seed_function.py — Bridge between the seed evaluator and every generator.

The seed evaluator is the authority. Seed identity is the evaluated values
(at t=0, with retry rules), not raw text. Scripts drive generation as
functions of time. Raw function mode samples s(t) at audio rate for use
as a signal generator.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Callable, List, Optional, Sequence, Tuple, Union

import numpy as np

# Import the project's evaluator. Adjust import if the module structure differs.
try:
    from groovebox import (
        _eval_seed_python,
        evaluate_seed_expression_at_time,
        _seed_script_env,
    )
except ImportError:
    # Fallback stubs for standalone use / testing
    def _eval_seed_python(seed_text, t_value=0.0, canonical_context=None, allow_scrape=True):
        return []

    def evaluate_seed_expression_at_time(seed_text, t_value, canonical_context=None):
        return 0.0

    def _seed_script_env(t_scalar=0.0, canonical_context=None):
        return {"t": t_scalar}


EVALUATOR_VERSION = "R31.7-seed-eval-1"


def seed_identity(seed_text: str, canonical_context: Any = None) -> Tuple[Tuple[float, ...], str]:
    """Identify a seed by its evaluated values at t=0 (with retries).

    Returns (tuple of finite floats, fingerprint string).
    Falls back to digit scrape only if nothing evaluates, then raw text hash.
    """
    vals = _eval_seed_python(seed_text, t_value=0.0, canonical_context=canonical_context, allow_scrape=False)
    if not vals:
        for probe in (1e-6, -1e-6, 1e-3, 0.25, 0.5, 1.0):
            vals = _eval_seed_python(seed_text, t_value=probe, canonical_context=canonical_context, allow_scrape=False)
            if vals:
                break
    if not vals:
        vals = _eval_seed_python(seed_text, t_value=0.0, canonical_context=canonical_context, allow_scrape=True)

    if vals:
        # Round to reduce floating-point noise for identity
        rounded = tuple(round(float(v), 8) for v in vals if math.isfinite(v))
        if rounded:
            fp = hashlib.sha256(repr(rounded).encode()).hexdigest()[:16]
            return rounded, fp

    # Absolute last resort: hash of raw text
    raw = str(seed_text or "").encode("utf-8", errors="replace")
    fp = hashlib.sha256(raw).hexdigest()[:16]
    return (float(int(fp, 16) % 10000) / 10000.0,), fp


def evaluate_over_time(
    seed_text: str,
    times: Sequence[float],
    canonical_context: Any = None,
) -> np.ndarray:
    """Evaluate the seed script at a sequence of time values.

    Returns array of shape (len(times), n_components) or (len(times),) .
    """
    results = []
    n_comp = None
    for t in times:
        vals = _eval_seed_python(seed_text, t_value=float(t), canonical_context=canonical_context, allow_scrape=False)
        if not vals:
            v = evaluate_seed_expression_at_time(seed_text, t, canonical_context)
            vals = [v]
        if n_comp is None:
            n_comp = len(vals)
        # Pad or truncate to consistent length
        padded = list(vals) + [0.0] * max(0, (n_comp or 1) - len(vals))
        results.append(padded[: n_comp or 1])
    return np.asarray(results, dtype=np.float64)


def raw_function_render(
    seed_text: str,
    sample_rate: int = 48000,
    duration_sec: float = 1.0,
    canonical_context: Any = None,
) -> np.ndarray:
    """Sample the evaluator directly at audio sample rate: output = s(t).

    Writes 32-bit float conceptually (returned as float64 array).
    Lists become channels. Fast path where possible; falls back per-sample.
    """
    n_samples = int(round(duration_sec * sample_rate))
    times = np.linspace(0.0, duration_sec, n_samples, endpoint=False)

    # Probe to see if vectorization is safe
    try:
        # Simple check: does it accept array-like? For now always per-sample
        # with compiled reuse planned; here we use the existing evaluator.
        channels = []
        max_comp = 1
        for t in times[:: max(1, n_samples // 8)]:  # sparse probe
            vals = _eval_seed_python(seed_text, t_value=float(t), canonical_context=canonical_context, allow_scrape=False)
            max_comp = max(max_comp, len(vals) or 1)
        out = np.zeros((n_samples, max_comp), dtype=np.float64)
        for i, t in enumerate(times):
            vals = _eval_seed_python(seed_text, t_value=float(t), canonical_context=canonical_context, allow_scrape=False)
            if not vals:
                vals = [evaluate_seed_expression_at_time(seed_text, t, canonical_context)]
            for c, v in enumerate(vals[:max_comp]):
                if math.isfinite(v):
                    out[i, c] = float(v)
        return out if max_comp > 1 else out[:, 0]
    except Exception:
        # Minimal fallback
        return np.zeros(n_samples, dtype=np.float64)


def seed_provenance(seed_text: str, canonical_context: Any = None) -> dict:
    """Record script, evaluator version, context fingerprint, and evaluated values."""
    identity, fp = seed_identity(seed_text, canonical_context)
    return {
        "script": str(seed_text or ""),
        "evaluator_version": EVALUATOR_VERSION,
        "identity": identity,
        "fingerprint": fp,
        "context_hash": hashlib.sha256(repr(canonical_context).encode()).hexdigest()[:12] if canonical_context is not None else "",
    }


def verify_seed(provenance: dict, current_evaluator_version: str = EVALUATOR_VERSION) -> bool:
    """Confirm that this build still reproduces the same evaluated values."""
    if provenance.get("evaluator_version") != current_evaluator_version:
        return False
    script = provenance.get("script", "")
    expected = tuple(provenance.get("identity", ()))
    actual, _ = seed_identity(script)
    return actual == expected
