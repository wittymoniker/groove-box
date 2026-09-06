"""Exact-reconstructing .MEUM project container for Mathematician's Groovebox.

This module implements the public ``save(path, project)`` / ``load(path)`` API
used by Groovebox.  The canonical project document is serialized as stable
UTF-8 JSON, SHA-256 authenticated, then zlib-compressed.  Compression changes
storage representation only; it does not alter canonical project values.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import tempfile
import zlib
from pathlib import Path
from typing import Any

MAGIC = b"MEUMGBX1"
VERSION = 1
_HEADER = struct.Struct(">8sBQQ32s")  # magic, version, raw_len, comp_len, sha256


def _canonical_json_bytes(project: Any) -> bytes:
    return json.dumps(
        project,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    ).encode("utf-8")


def _ensure_path(path: os.PathLike[str] | str) -> Path:
    p = Path(path).expanduser()
    if p.suffix.lower() != ".meum":
        p = p.with_suffix(p.suffix + ".MEUM" if p.suffix else ".MEUM")
    return p


def dumps(project: Any, level: int = 9) -> bytes:
    raw = _canonical_json_bytes(project)
    digest = hashlib.sha256(raw).digest()
    comp = zlib.compress(raw, max(0, min(9, int(level))))
    return _HEADER.pack(MAGIC, VERSION, len(raw), len(comp), digest) + comp


def loads(blob: bytes) -> Any:
    if len(blob) < _HEADER.size:
        raise ValueError("Not a complete .MEUM container")
    magic, version, raw_len, comp_len, digest = _HEADER.unpack_from(blob, 0)
    if magic != MAGIC:
        raise ValueError("Invalid .MEUM magic")
    if version != VERSION:
        raise ValueError(f"Unsupported .MEUM version: {version}")
    comp = blob[_HEADER.size:]
    if len(comp) != comp_len:
        raise ValueError("Truncated or overlong .MEUM payload")
    raw = zlib.decompress(comp)
    if len(raw) != raw_len:
        raise ValueError(".MEUM reconstructed length mismatch")
    if hashlib.sha256(raw).digest() != digest:
        raise ValueError(".MEUM SHA-256 integrity check failed")
    return json.loads(raw.decode("utf-8"))


def save(path: os.PathLike[str] | str, project: Any) -> str:
    """Atomically save *project* and return the final .MEUM path as a string."""
    p = _ensure_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    blob = dumps(project)
    fd, tmp_name = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=p.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, p)
        try:
            dfd = os.open(str(p.parent), os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return str(p)


def load(path: os.PathLike[str] | str) -> Any:
    return loads(Path(path).expanduser().read_bytes())
