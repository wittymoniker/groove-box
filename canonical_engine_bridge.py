"""Shared canonical Global Play projection contract for music, visual, and game consumers.

The bridge deliberately carries descriptors rather than engine-specific mutable state.
Each consumer resolves the same canonical definition against its own local context.
"""
from __future__ import annotations
import hashlib, json


def fingerprint(global_algo):
    return hashlib.sha256(json.dumps(global_algo or {}, sort_keys=True, default=str).encode()).hexdigest()[:16]


def project(global_algo, instrument_index=0, instrument_name="", sequence_id=None):
    gas = dict(global_algo or {})
    scope = str(gas.get("scope") or "global")
    if scope != "local_instrument":
        return None
    params = dict(gas.get("params") or {})
    return {
        "canonical_ref": "global_algo_state",
        "canonical_fingerprint": fingerprint(gas),
        "scope": scope,
        "context_mode": str(gas.get("context_mode") or "instrument"),
        "instrument_index": int(instrument_index),
        "instrument": str(instrument_name or ""),
        "sequence": sequence_id,
        "apply_enabled": bool(gas.get("apply_enabled", False)),
        "enable_script": bool(params.get("enable_script", True)),
        "enable_domain": bool(params.get("enable_domain", True)),
        "enable_wire": bool(params.get("enable_wire", True)),
        "script_amount": float(params.get("script_amount", 1.0)),
        "domain_amount": float(params.get("domain_amount", 1.0)),
        "wire_amount": float(params.get("wire_amount", 1.0)),
        "mix": float(params.get("mix", 0.35)),
    }


def game_payload(global_algo, instruments):
    gas = dict(global_algo or {})
    rows = []
    if str(gas.get("scope") or "global") == "local_instrument":
        for i, name in enumerate(list(instruments or [])[:16]):
            rows.append(project(gas, i, name))
    return {
        "canonical_fingerprint": fingerprint(gas),
        "scope": str(gas.get("scope") or "global"),
        "context_mode": str(gas.get("context_mode") or "instrument"),
        "local_projections": rows,
    }
