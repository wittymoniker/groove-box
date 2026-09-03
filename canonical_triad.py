"""Canonical Trio tensor correspondence helpers.

The runtime may stream these operations for performance; this module provides a
small, explicit mathematical representation for regression tests and decoding.
"""
from __future__ import annotations
import hashlib, json
import numpy as np

DOMAINS = ("audio", "visual", "game")
FEATURES = (
    "seed", "time", "step", "phase", "energy", "spectrum", "goava",
    "euclidean", "bpm", "pair", "entropy", "x", "y", "z",
)

def canonical_tensor(rows: list[dict], domain: str) -> np.ndarray:
    """Encode canonical rows as C[domain,row,feature]. Missing values are zero."""
    if domain not in DOMAINS:
        raise ValueError(domain)
    out = np.zeros((1, len(rows), len(FEATURES)), dtype=np.float64)
    for r, row in enumerate(rows):
        for k, name in enumerate(FEATURES):
            try:
                v = float(row.get(name, 0.0))
                out[0, r, k] = v if np.isfinite(v) else 0.0
            except Exception:
                out[0, r, k] = 0.0
    return out

def domain_contract(C: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Reference contraction Y[t] = sum(row,feature) W[t,row,feature] C[row,feature]."""
    C = np.asarray(C, dtype=np.float64)
    W = np.asarray(weights, dtype=np.float64)
    if C.ndim == 3 and C.shape[0] == 1:
        C = C[0]
    if C.ndim != 2 or W.ndim != 3 or W.shape[1:] != C.shape:
        raise ValueError(f"shape mismatch C={C.shape}, W={W.shape}")
    return np.einsum("trf,rf->t", W, C, optimize=True)

def stable_fingerprint(payload) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:16]

def ot_master_tensor_reference(x, meum_norm):
    """Explicit tensor/reference form of ot_master_transform's pre-memory stages."""
    x = np.asarray(x, dtype=np.float64).ravel()
    bands = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    # First-match indicator tensor: I[k,n].
    I = np.vstack([np.abs(x) <= b for b in bands]).astype(np.float64)
    # First-match only: zero later matches once an earlier band has matched.
    I[1] *= 1.0 - I[0]
    I[2] *= 1.0 - I[0] - I[1]
    default = 1.0 - np.clip(I.sum(axis=0), 0.0, 1.0)
    B = np.einsum("kn,k->n", I, bands, optimize=True) + default
    out = x + 0.35 * np.sign(x) * B
    out = out * (1.0 + float(meum_norm) * 0.15 / (1.0 + np.abs(out)))
    S = np.zeros((len(out), len(out)), dtype=np.float64)
    if len(out):
        S[0, 0] = 1.0
        if len(out) > 1:
            S[1:, :-1] = np.eye(len(out)-1)
    prev = S @ out
    neg = (out < 0.0) & (prev < 0.0)
    return np.where(neg, -np.abs(out) * 1.15, out).astype(np.float32)
