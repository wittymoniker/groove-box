"""Groovebox Meum semantic container (.MEUM).

This is deliberately conservative: it performs exact structural DAG reuse on the
JSON-compatible project document and records the project's Meum search roles.
It does not claim arbitrary information can be recovered from a seed, and it
falls back to exact lossless reconstruction only.
"""
from __future__ import annotations
import hashlib, json, os, tempfile
from typing import Any, Dict

FORMAT = "Groovebox-Meum-Compression"
VERSION = 1
EXTENSION = ".MEUM"
M = 1.1975807343385265

def _canon(x: Any) -> bytes:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")

def _intern(value: Any, nodes: Dict[str, Any]) -> Any:
    if isinstance(value, dict):
        body = {"t":"d","v":[[str(k), _intern(v, nodes)] for k,v in sorted(value.items(), key=lambda kv: str(kv[0]))]}
    elif isinstance(value, list):
        body = {"t":"l","v":[_intern(v, nodes) for v in value]}
    elif isinstance(value, tuple):
        body = {"t":"l","v":[_intern(v, nodes) for v in value]}
    else:
        return {"v": value}
    key = hashlib.sha256(_canon(body)).hexdigest()
    nodes.setdefault(key, body)
    return {"r": key}

def _expand(ref: Any, nodes: Dict[str, Any]) -> Any:
    if "v" in ref and "r" not in ref:
        return ref["v"]
    body = nodes[ref["r"]]
    if body["t"] == "l":
        return [_expand(v, nodes) for v in body["v"]]
    return {k:_expand(v, nodes) for k,v in body["v"]}

def encode_document(document: Dict[str, Any]) -> Dict[str, Any]:
    nodes: Dict[str, Any] = {}
    root = _intern(document, nodes)
    raw = _canon(document)
    return {
        "format": FORMAT,
        "version": VERSION,
        "method": "lossless-structural-reuse",
        "meum": {
            "M": M,
            "normalize": "2-M",
            "ambiguity": "M^-p",
            "prediction": "(M-1)^p",
            "ideal_compare": "2^M",
            "certificate_rule": "exact reconstruction required",
        },
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_bytes": len(raw),
        "root": root,
        "nodes": nodes,
    }

def decode_document(package: Dict[str, Any]) -> Dict[str, Any]:
    if package.get("format") != FORMAT or int(package.get("version",0)) != VERSION:
        raise ValueError("Not a supported Groovebox .MEUM container")
    doc = _expand(package["root"], package["nodes"])
    raw = _canon(doc)
    if hashlib.sha256(raw).hexdigest() != package.get("source_sha256"):
        raise ValueError(".MEUM reconstruction checksum mismatch")
    return doc

def save(path: str, document: Dict[str, Any]) -> str:
    if not path.lower().endswith(".meum"):
        path += EXTENSION
    pkg = encode_document(document)
    parent = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".meum-", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(pkg, f, ensure_ascii=False, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp): os.unlink(tmp)
        except Exception:
            pass
    return path

def load(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return decode_document(json.load(f))
