"""Equation-described, lossless float32 audio attachments for Groovebox projects.

The file stores a compact reconstruction equation plus deterministic compressed
IEEE-754 float32 PCM.  It is not a claim that arbitrary audio has a short
closed-form symbolic expression.  The complete .eqaudio file is capped at
25 MiB; decoding is bounded to avoid oversized or malicious payloads.
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

MAGIC = b"EQAUDIO1"
FORMAT_VERSION = 1
MAX_PAYLOAD_BYTES = 25 * 1024 * 1024
MAX_HEADER_BYTES = 64 * 1024
MAX_DECODED_BYTES = 512 * 1024 * 1024


class EquationAudioError(ValueError):
    pass


class EquationAudioTooLarge(EquationAudioError):
    pass


def _pcm_bytes(signal: Any, sample_rate: int, channels: int | None):
    try:
        import numpy as np
        arr = np.asarray(signal, dtype=np.float32)
        if arr.ndim == 1:
            ch = int(channels or 1)
            if ch < 1 or arr.size % ch:
                raise EquationAudioError("mono/interleaved sample count does not match channel count")
            frames = int(arr.size // ch)
            arr = arr.reshape((frames, ch))
        elif arr.ndim == 2:
            frames, detected = map(int, arr.shape)
            ch = int(channels or detected)
            if ch != detected:
                raise EquationAudioError("explicit channel count does not match 2-D signal shape")
        else:
            raise EquationAudioError("audio signal must be one- or two-dimensional")
        if not (1 <= ch <= 64):
            raise EquationAudioError("channel count must be between 1 and 64")
        # Little-endian, C-contiguous interleaved float32 is the canonical wire format.
        arr = np.asarray(arr, dtype="<f4", order="C")
        return arr.tobytes(order="C"), frames, ch
    except ImportError:
        if isinstance(signal, (bytes, bytearray, memoryview)):
            raw = bytes(signal)
            ch = int(channels or 1)
            if len(raw) % (4 * ch):
                raise EquationAudioError("raw float32 byte count does not align to channels")
            return raw, len(raw) // (4 * ch), ch
        raise EquationAudioError("NumPy is required to encode non-byte audio input")


def encode_payload(signal: Any, sample_rate: int, channels: int | None = None,
                   *, origin: str = "project-master") -> bytes:
    sr = int(sample_rate)
    if not (1 <= sr <= 768000):
        raise EquationAudioError("sample rate must be between 1 and 768000 Hz")
    raw, frames, ch = _pcm_bytes(signal, sr, channels)
    if frames < 0 or len(raw) != frames * ch * 4:
        raise EquationAudioError("inconsistent PCM frame metadata")
    raw_sha = hashlib.sha256(raw).hexdigest()
    compressed = zlib.compress(raw, level=9)
    header = {
        "format": "groovebox-equation-audio",
        "version": FORMAT_VERSION,
        "equation": "x[n,c] = IEEE754-F32LE(decoded_payload[4*(n*channels+c):4*(n*channels+c+1)])",
        "sample_rate": sr,
        "channels": ch,
        "frames": frames,
        "interleaving": "frame-major-interleaved",
        "precision": "IEEE-754-float32-little-endian",
        "origin": str(origin)[:160],
        "codec": "zlib-deflate-9",
        "decoded_bytes": len(raw),
        "decoded_sha256": raw_sha,
    }
    header_bytes = json.dumps(header, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=False).encode("utf-8")
    if len(header_bytes) > MAX_HEADER_BYTES:
        raise EquationAudioError("equation audio metadata exceeds header limit")
    payload = MAGIC + struct.pack(">I", len(header_bytes)) + header_bytes + compressed
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise EquationAudioTooLarge(
            f"equation audio payload is {len(payload)} bytes; limit is {MAX_PAYLOAD_BYTES} bytes"
        )
    return payload


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".part", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        try:
            dfd = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass


def write_payload(path: str | os.PathLike[str], signal: Any, sample_rate: int,
                  channels: int | None = None, *, origin: str = "project-master") -> dict:
    payload = encode_payload(signal, sample_rate, channels, origin=origin)
    digest = hashlib.sha256(payload).hexdigest()
    target = Path(path)
    _atomic_write(target, payload)
    return {"file": target.name, "format": "eqaudio", "version": FORMAT_VERSION,
            "bytes": len(payload), "payload_sha256": digest,
            "max_payload_bytes": MAX_PAYLOAD_BYTES}


def decode_payload(payload: bytes, *, as_numpy: bool = True):
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise EquationAudioTooLarge("equation audio payload exceeds 25 MiB")
    if len(payload) < 12 or payload[:8] != MAGIC:
        raise EquationAudioError("invalid equation audio signature")
    header_len = struct.unpack(">I", payload[8:12])[0]
    if header_len < 2 or header_len > MAX_HEADER_BYTES or 12 + header_len > len(payload):
        raise EquationAudioError("invalid equation audio header length")
    try:
        header = json.loads(payload[12:12 + header_len].decode("utf-8"))
    except Exception as exc:
        raise EquationAudioError(f"invalid equation audio metadata: {exc}") from exc
    if header.get("format") != "groovebox-equation-audio" or int(header.get("version", 0)) != FORMAT_VERSION:
        raise EquationAudioError("unsupported equation audio format/version")
    frames, channels = int(header.get("frames", -1)), int(header.get("channels", 0))
    expected = int(header.get("decoded_bytes", -1))
    if frames < 0 or not (1 <= channels <= 64) or expected != frames * channels * 4:
        raise EquationAudioError("invalid equation audio dimensions")
    if expected > MAX_DECODED_BYTES:
        raise EquationAudioTooLarge("decoded audio exceeds the 512 MiB safety bound")
    inflater = zlib.decompressobj()
    try:
        raw = inflater.decompress(payload[12 + header_len:], expected + 1)
        if len(raw) <= expected:
            raw += inflater.flush(expected + 1 - len(raw))
    except zlib.error as exc:
        raise EquationAudioError(f"equation audio decompression failed: {exc}") from exc
    if len(raw) != expected or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
        raise EquationAudioError("equation audio decoded size/stream boundary mismatch")
    if hashlib.sha256(raw).hexdigest() != str(header.get("decoded_sha256", "")):
        raise EquationAudioError("equation audio decoded SHA-256 mismatch")
    if as_numpy:
        try:
            import numpy as np
            return header, np.frombuffer(raw, dtype="<f4").reshape((frames, channels)).copy()
        except ImportError:
            pass
    return header, raw


def read_payload(path: str | os.PathLike[str], *, as_numpy: bool = True):
    target = Path(path)
    size = target.stat().st_size
    if size > MAX_PAYLOAD_BYTES:
        raise EquationAudioTooLarge("equation audio payload exceeds 25 MiB")
    return decode_payload(target.read_bytes(), as_numpy=as_numpy)


def verify_payload(path: str | os.PathLike[str], expected: dict | None = None) -> dict:
    target = Path(path)
    size = target.stat().st_size
    if size > MAX_PAYLOAD_BYTES:
        raise EquationAudioTooLarge("equation audio payload exceeds 25 MiB")
    raw = target.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if isinstance(expected, dict):
        if int(expected.get("bytes", size)) != size:
            raise EquationAudioError("project attachment byte count does not match sidecar")
        if expected.get("payload_sha256") and expected["payload_sha256"] != digest:
            raise EquationAudioError("project attachment SHA-256 does not match sidecar")
    header, _ = decode_payload(raw, as_numpy=False)
    return {"valid": True, "file": target.name, "bytes": size,
            "payload_sha256": digest, "sample_rate": header["sample_rate"],
            "channels": header["channels"], "frames": header["frames"]}


def attach_to_project(project_path: str | os.PathLike[str], document: dict,
                      signal: Any, sample_rate: int, channels: int | None = None,
                      *, origin: str = "project-master") -> dict:
    """Write a content-addressed sibling and update a copied document reference.

    Content addressing preserves the previous good sidecar if the subsequent
    MCC JSON commit fails, avoiding a broken two-file replacement transaction.
    """
    if not isinstance(document, dict):
        raise EquationAudioError("project document must be a dictionary")
    path = Path(project_path)
    payload = encode_payload(signal, sample_rate, channels, origin=origin)
    digest = hashlib.sha256(payload).hexdigest()
    sidecar_name = f"{path.name}.{digest[:20]}.eqaudio"
    sidecar = path.with_name(sidecar_name)
    if not sidecar.exists():
        _atomic_write(sidecar, payload)
    meta = {"file": sidecar_name, "format": "eqaudio", "version": FORMAT_VERSION,
            "bytes": len(payload), "payload_sha256": digest,
            "max_payload_bytes": MAX_PAYLOAD_BYTES}
    updated = dict(document)
    updated["equation_audio_payload"] = meta
    return updated


def verify_project_attachment(project_path: str | os.PathLike[str], document: dict) -> dict | None:
    meta = document.get("equation_audio_payload") if isinstance(document, dict) else None
    if not isinstance(meta, dict) or not meta.get("file"):
        return None
    name = str(meta["file"])
    # Never permit absolute paths or directory traversal from a project document.
    if Path(name).name != name or not name.endswith(".eqaudio"):
        raise EquationAudioError("unsafe equation audio sidecar reference")
    return verify_payload(Path(project_path).with_name(name), meta)
