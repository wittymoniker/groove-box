"""R89 post-write export verification.

Verification is read-only: it never rewrites the user's output.  It checks a
stable file snapshot (size + SHA-256), format/container structure where the
standard library can do so, and optional ffprobe decoding for media containers.
"""
from __future__ import annotations
import hashlib, json, os, shutil, subprocess, wave

class ExportIntegrityError(RuntimeError):
    pass

def _sha256(path, chunk=4 * 1024 * 1024):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()

def verify_file(path, *, kind='auto', min_bytes=64, decode=True):
    path = os.path.abspath(os.fspath(path))
    if not os.path.isfile(path):
        raise ExportIntegrityError(f'export file missing: {path}')
    size = os.path.getsize(path)
    if size < int(min_bytes):
        raise ExportIntegrityError(f'export file is too small ({size} bytes): {path}')
    ext = os.path.splitext(path)[1].lower()
    report = {'path': path, 'bytes': size, 'sha256': _sha256(path), 'format': ext.lstrip('.') or 'unknown'}
    if ext == '.wav':
        # Parse RIFF chunks directly: Python's wave module rejects valid IEEE-float
        # WAVs on some supported Python versions.
        try:
            with open(path, 'rb') as f:
                head = f.read(12)
                if len(head) != 12 or head[:4] != b'RIFF' or head[8:12] != b'WAVE':
                    raise ExportIntegrityError('WAV RIFF/WAVE signature is invalid')
                fmt = None; data_size = None; data_offset = None
                while True:
                    chunk = f.read(8)
                    if len(chunk) < 8: break
                    tag, length = chunk[:4], int.from_bytes(chunk[4:], 'little')
                    if tag == b'fmt ' and length >= 16:
                        import struct
                        payload = f.read(16)
                        if len(payload) != 16: raise ExportIntegrityError('WAV fmt chunk is truncated')
                        fmt = struct.unpack('<HHIIHH', payload)
                        f.seek(length - 16, 1)
                    else:
                        if tag == b'data':
                            data_size = length; data_offset = f.tell()
                        f.seek(length, 1)
                    if length & 1: f.seek(1, 1)
                if fmt is None or data_size is None:
                    raise ExportIntegrityError('WAV is missing fmt or data chunk')
                code, channels, rate, _byte_rate, block_align, bits = fmt
                if code not in (1, 3) or channels < 1 or rate < 8000 or bits not in (8, 16, 24, 32, 64) or block_align < 1:
                    raise ExportIntegrityError('WAV header has unsupported format/channels/rate/bit depth')
                if data_size < block_align:
                    raise ExportIntegrityError('WAV contains no complete sample frame')
                if data_offset is None or data_offset + data_size > size:
                    raise ExportIntegrityError('WAV audio payload is truncated')
                frames = data_size // block_align
                report.update(channels=channels, sample_width=bits // 8, sample_rate=rate, frames=frames,
                              duration_seconds=frames / float(rate), encoding=('float' if code == 3 else 'pcm'))
        except ExportIntegrityError: raise
        except Exception as exc:
            raise ExportIntegrityError(f'invalid WAV container: {exc}') from exc
    elif ext in ('.mp4', '.m4v', '.mov'):
        with open(path, 'rb') as f: head = f.read(32)
        if b'ftyp' not in head:
            raise ExportIntegrityError('MP4-family file has no ftyp container signature')
        report['container_signature'] = 'ftyp'
    elif ext in ('.mkv', '.webm'):
        with open(path, 'rb') as f: head = f.read(4)
        if head != b'\x1aE\xdf\xa3':
            raise ExportIntegrityError('Matroska/WebM EBML signature is missing')
        report['container_signature'] = 'ebml'
    elif ext == '.npy':
        try:
            import numpy as np
            arr = np.load(path, mmap_mode='r', allow_pickle=False)
            if arr.size < 1 or arr.dtype.kind not in 'fiu':
                raise ExportIntegrityError('NumPy export has no numeric samples')
            finite = True
            if arr.dtype.kind == 'f':
                for start in range(0, int(arr.size), 1_000_000):
                    if not np.isfinite(arr.reshape(-1)[start:start+1_000_000]).all():
                        finite = False; break
            if not finite: raise ExportIntegrityError('NumPy export contains NaN or infinite samples')
            report.update(shape=list(arr.shape), dtype=str(arr.dtype), finite=True)
        except ExportIntegrityError: raise
        except Exception as exc: raise ExportIntegrityError(f'invalid NumPy export: {exc}') from exc
    elif ext in ('.flac',):
        with open(path, 'rb') as f:
            if f.read(4) != b'fLaC': raise ExportIntegrityError('FLAC signature is missing')
    if decode and ext in ('.mp4', '.m4v', '.mov', '.mkv', '.webm', '.flac', '.mp3', '.ogg'):
        ffprobe = shutil.which('ffprobe')
        if ffprobe:
            p = subprocess.run([ffprobe, '-v', 'error', '-show_entries', 'format=duration,size',
                                '-of', 'json', path], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, timeout=45)
            if p.returncode != 0:
                raise ExportIntegrityError('ffprobe could not parse export: ' + (p.stderr.strip()[:500] or 'unknown error'))
            try: meta = json.loads(p.stdout or '{}').get('format') or {}
            except Exception: meta = {}
            if not meta: raise ExportIntegrityError('ffprobe returned no media format metadata')
            report['probe'] = meta
        else:
            report['decode_check'] = 'not_run_ffprobe_unavailable'
    # Detect a file changing while it was being hashed/inspected.
    if os.path.getsize(path) != size:
        raise ExportIntegrityError('export changed during verification')
    return report

def verify_outputs(paths, *, kind='auto', min_bytes=64):
    reports = []
    for path in paths or ():
        if path:
            reports.append(verify_file(path, kind=kind, min_bytes=min_bytes))
    if not reports:
        raise ExportIntegrityError('no completed export files were supplied for verification')
    return {'verified': True, 'file_count': len(reports), 'files': reports}
