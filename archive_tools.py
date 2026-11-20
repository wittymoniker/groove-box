"""GROOVEBOX_R123_ARCHIVE_TOOLS_20261119 — compress / extract for the File Manager.

Formats (create and extract):
    .zip               zipfile (deflate)
    .tar.gz / .tgz     tarfile (gzip)    — extract also reads .tar, .tar.xz, .tar.bz2
    .7z                py7zr when importable, else a 7-Zip program (7zz / 7z / 7za)
    .MCC (package)     mcc_media "mcc-pack-v1" (lossless, sha256-verified, Groovebox native)

A project .MCC (plain JSON composition) or a media .MCC (audio / video / image) is not an
archive: extract() reports that clearly instead of failing silently.

Safety (every format): members are confined to the destination folder (no absolute paths,
no "..", no symlink/hardlink that points outside), device/FIFO members are skipped, the
uncompressed size is checked against free space before anything is written, and new
archives are written to "<name>.part" then renamed, so a cancelled or failed run never
leaves a half archive under the final name.  Pure functions; the UI runs them off-thread.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tarfile
import zipfile
from pathlib import Path
from typing import Callable, Iterable, List, Optional

Progress = Optional[Callable[[int, int], None]]
Cancel = Optional[Callable[[], bool]]

CREATE_FORMATS = ("zip", "tar.gz", "7z", "mcc")
FORMAT_LABELS = {"zip": ".zip", "tar.gz": ".tar.gz", "7z": ".7z", "mcc": ".MCC (Groovebox package)"}
SUFFIX = {"zip": ".zip", "tar.gz": ".tar.gz", "7z": ".7z", "mcc": ".MCC"}
_TAR_SUFFIXES = (".tar.gz", ".tgz", ".tar", ".tar.xz", ".txz", ".tar.bz2", ".tbz2")
SPACE_MARGIN = 64 * 1024 * 1024


class ArchiveError(RuntimeError):
    """A user-facing archive failure (the message is shown as-is)."""


class Cancelled(ArchiveError):
    pass


# ---------------------------------------------------------------------------- detection
def detect_format(path: str) -> Optional[str]:
    """'zip' | 'tar' | '7z' | 'mcc' | 'mcc-project' | 'mcc-media' | None (by magic, then suffix)."""
    p = str(path)
    low = p.lower()
    try:
        with open(p, "rb") as f:
            head = f.read(16)
    except OSError:
        head = b""
    if head.startswith(b"MCCMEDIA"):
        try:
            import mcc_media
            return "mcc" if mcc_media.media_kind(p) == "package" else "mcc-media"
        except Exception:
            return "mcc"
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06"):
        return "zip"
    if head.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "7z"
    if head[:2] == b"\x1f\x8b" or head[:3] == b"BZh" or head[:6] == b"\xfd7zXZ\x00":
        return "tar" if low.endswith(_TAR_SUFFIXES) or tarfile.is_tarfile(p) else None
    if low.endswith(".mcc"):
        return "mcc-project" if head.lstrip()[:1] in (b"{", b"[") else None
    if low.endswith(_TAR_SUFFIXES):
        return "tar"
    try:
        if tarfile.is_tarfile(p):
            return "tar"
    except Exception:
        pass
    return None


def is_archive(path: str) -> bool:
    return detect_format(path) in ("zip", "tar", "7z", "mcc")


def output_path(out_path: str, fmt: str) -> str:
    fmt = normalize_format(fmt)
    suf = SUFFIX[fmt]
    return str(out_path) if str(out_path).lower().endswith(suf.lower()) else str(out_path) + suf


def normalize_format(fmt: str) -> str:
    f = str(fmt or "").strip().lower().lstrip(".")
    f = {"tgz": "tar.gz", "targz": "tar.gz", "mcc (groovebox package)": "mcc"}.get(f, f)
    if f.startswith("mcc"):
        f = "mcc"
    if f not in CREATE_FORMATS:
        raise ArchiveError(f"Unsupported archive format: {fmt!r} (use .zip, .tar.gz, .7z or .MCC)")
    return f


# ---------------------------------------------------------------------------- 7-Zip backend
def _py7zr():
    try:
        import py7zr  # type: ignore
        return py7zr
    except Exception:
        return None


def seven_zip_program() -> Optional[str]:
    for name in ("7zz", "7z", "7za"):
        exe = shutil.which(name)
        if exe:
            return exe
    return None


def seven_zip_available() -> bool:
    return _py7zr() is not None or seven_zip_program() is not None


def capabilities() -> dict:
    return {"zip": True, "tar.gz": True, "mcc": True, "7z": seven_zip_available(),
            "7z_backend": "py7zr" if _py7zr() else (seven_zip_program() or "")}


def _no_7z() -> ArchiveError:
    return ArchiveError(".7z needs py7zr (pip install py7zr) or 7-Zip (Debian/Ubuntu: apt install 7zip; "
                        "Fedora: dnf install 7zip; macOS: brew install sevenzip; Windows: 7-zip.org).")


# ---------------------------------------------------------------------------- helpers
def _check(cancel: Cancel):
    if cancel and cancel():
        raise Cancelled("Cancelled.")


def _collect(paths: Iterable[str], base: Optional[str] = None):
    """(absolute file or dir, archive name) for every entry under the selected paths."""
    sel = [os.path.abspath(str(p)) for p in paths if str(p)]
    if not sel:
        raise ArchiveError("Select one or more files or folders first.")
    for p in sel:
        if not os.path.lexists(p):
            raise ArchiveError(f"Not found: {p}")
    if base:
        base = os.path.abspath(base)
    elif len(sel) == 1:
        base = os.path.dirname(sel[0])
    else:
        common = os.path.commonpath(sel)
        base = os.path.dirname(common) if common in sel else common   # siblings keep their own names
    out = []
    for p in sel:
        if os.path.isdir(p) and not os.path.islink(p):
            out.append((p, os.path.relpath(p, base).replace(os.sep, "/")))
            for dp, dns, fns in os.walk(p):
                dns.sort()
                for d in dns:
                    full = os.path.join(dp, d)
                    out.append((full, os.path.relpath(full, base).replace(os.sep, "/")))
                for fn in sorted(fns):
                    full = os.path.join(dp, fn)
                    out.append((full, os.path.relpath(full, base).replace(os.sep, "/")))
        else:
            out.append((p, os.path.relpath(p, base).replace(os.sep, "/")))
    return base, out


def _safe_target(dest: Path, name: str) -> Optional[Path]:
    n = str(name).replace("\\", "/")
    if not n or n.startswith("/") or (len(n) > 1 and n[1] == ":"):
        raise ArchiveError(f"Refusing absolute path in archive: {name}")
    parts = [x for x in n.split("/") if x not in ("", ".")]
    if any(x == ".." for x in parts):
        raise ArchiveError(f"Refusing path outside the destination: {name}")
    if not parts:
        return None
    t = (dest / Path(*parts)).resolve()
    if t != dest and dest not in t.parents:
        raise ArchiveError(f"Refusing path outside the destination: {name}")
    return t


def _free(path: Path) -> int:
    p = path
    while not p.exists() and p != p.parent:
        p = p.parent
    try:
        return int(shutil.disk_usage(str(p)).free)
    except Exception:
        return 1 << 62


def _space_check(dest: Path, need: int):
    free = _free(dest)
    if need + SPACE_MARGIN > free:
        raise ArchiveError(f"Not enough free space: needs {need / 1e6:.1f} MB, {free / 1e6:.1f} MB free at {dest}")


# ---------------------------------------------------------------------------- listing
def list_members(path: str) -> List[dict]:
    """[{name, size, is_dir}] for any supported archive."""
    fmt = detect_format(path)
    if fmt == "zip":
        with zipfile.ZipFile(path) as z:
            return [{"name": i.filename, "size": i.file_size, "is_dir": i.is_dir()} for i in z.infolist()]
    if fmt == "tar":
        with tarfile.open(path, "r:*") as t:
            return [{"name": m.name, "size": m.size, "is_dir": m.isdir()} for m in t.getmembers()]
    if fmt == "mcc":
        import mcc_media
        return [{"name": m["path"], "size": int(m.get("size", 0)), "is_dir": False} for m in mcc_media.list_package(path)]
    if fmt == "7z":
        lib = _py7zr()
        if lib is not None:
            with lib.SevenZipFile(path, "r") as z:
                return [{"name": i.filename, "size": int(i.uncompressed or 0), "is_dir": bool(i.is_directory)} for i in z.list()]
        exe = seven_zip_program()
        if not exe:
            raise _no_7z()
        r = subprocess.run([exe, "l", "-slt", "-ba", "--", path], capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise ArchiveError(f"7-Zip could not read {os.path.basename(path)}: {(r.stderr or r.stdout).strip()[:300]}")
        out, cur = [], {}
        for line in r.stdout.splitlines() + [""]:
            if not line.strip():
                if "Path" in cur:
                    out.append({"name": cur["Path"], "size": int(cur.get("Size") or 0),
                                "is_dir": "D" in cur.get("Attributes", "")[:1] or cur.get("Folder") == "+"})
                cur = {}
            elif " = " in line:
                k, v = line.split(" = ", 1)
                cur[k.strip()] = v.strip()
        return out
    raise ArchiveError(_not_archive_message(path, fmt))


def _not_archive_message(path, fmt):
    name = os.path.basename(str(path))
    if fmt == "mcc-project":
        return f"{name} is a Groovebox project (.MCC composition), not an archive — open it with Open Project."
    if fmt == "mcc-media":
        return f"{name} is a Groovebox media .MCC (audio/video/image) — open it in the Player or convert it."
    return f"{name} is not a supported archive (.zip, .tar.gz, .7z or .MCC package)."


# ---------------------------------------------------------------------------- create
def create_archive(paths: Iterable[str], out_path: str, fmt: str = "zip", *, base: Optional[str] = None,
                   level: int = 6, progress: Progress = None, cancel: Cancel = None) -> str:
    """Compress files/folders into one archive. Returns the final path."""
    fmt = normalize_format(fmt)
    out_path = output_path(out_path, fmt)
    base, entries = _collect(paths, base)
    out_abs = os.path.abspath(out_path)
    entries = [(a, n) for a, n in entries if os.path.abspath(a) not in (out_abs, out_abs + ".part")]
    files = [(a, n) for a, n in entries if not (os.path.isdir(a) and not os.path.islink(a))]
    total = max(1, len(files))
    need = sum(os.path.getsize(a) for a, _ in files if os.path.isfile(a) and not os.path.islink(a))
    _space_check(Path(out_abs).parent, need // 2)
    tmp = out_abs + ".part"
    try:
        os.makedirs(os.path.dirname(out_abs) or ".", exist_ok=True)
        done = 0
        if fmt == "zip":
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=max(0, min(9, int(level)))) as z:
                for a, n in entries:
                    _check(cancel)
                    if os.path.isdir(a) and not os.path.islink(a):
                        z.writestr(n.rstrip("/") + "/", b"")
                        continue
                    if os.path.islink(a) or not os.path.isfile(a):
                        continue
                    z.write(a, n)
                    done += 1
                    progress and progress(done, total)
        elif fmt == "tar.gz":
            with tarfile.open(tmp, "w:gz", compresslevel=max(1, min(9, int(level)))) as t:
                for a, n in entries:
                    _check(cancel)
                    t.add(a, arcname=n, recursive=False)
                    if not os.path.isdir(a):
                        done += 1
                        progress and progress(done, total)
        elif fmt == "mcc":
            stage = [(a, n) for a, n in files if os.path.isfile(a) and not os.path.islink(a)]
            _write_mcc(stage, tmp, level, progress, cancel)
        else:
            lib = _py7zr()
            if lib is not None:
                with lib.SevenZipFile(tmp, "w") as z:
                    for a, n in entries:
                        _check(cancel)
                        if os.path.isdir(a) and not os.path.islink(a):
                            continue
                        if os.path.islink(a) or not os.path.isfile(a):
                            continue
                        z.write(a, n)
                        done += 1
                        progress and progress(done, total)
            else:
                exe = seven_zip_program()
                if not exe:
                    raise _no_7z()
                names = sorted({n.split("/", 1)[0] for _, n in entries})
                r = subprocess.run([exe, "a", "-t7z", f"-mx={max(0, min(9, int(level)))}", "-y", "-bso0", "-bsp0",
                                    tmp, "--", *names], cwd=base, capture_output=True, text=True, timeout=24 * 3600)
                if r.returncode != 0:
                    raise ArchiveError(f"7-Zip failed: {(r.stderr or r.stdout).strip()[:300]}")
                progress and progress(total, total)
        os.replace(tmp, out_abs)
        return out_abs
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _write_mcc(stage, tmp, level, progress, cancel):
    """mcc-pack-v1 from an explicit (abs, name) list (keeps the selection's own top folders)."""
    import time
    import mcc_media
    hdr = {"kind": "package", "codec": "mcc-pack-v1", "files": len(stage),
           "manifest": {"name": "File Manager archive", "created": time.strftime("%Y-%m-%d %H:%M:%S")}}
    w = mcc_media._Writer(tmp, hdr, max(1, min(9, int(level))))
    try:
        for i, (a, n) in enumerate(stage):
            _check(cancel)
            st = os.stat(a)
            with open(a, "rb") as f:
                w.block(b"F", {"path": n, "mode": st.st_mode & 0o777, "size": st.st_size}, f.read())
            progress and progress(i + 1, len(stage))
    finally:
        w.close()


# ---------------------------------------------------------------------------- extract
def default_extract_dir(path: str) -> str:
    p = str(path)
    name = os.path.basename(p)
    low = name.lower()
    for suf in _TAR_SUFFIXES + (".zip", ".7z", ".mcc"):
        if low.endswith(suf):
            name = name[: -len(suf)]
            break
    parent = os.path.dirname(os.path.abspath(p))
    cand = os.path.join(parent, name or "extracted")
    i = 2
    while os.path.exists(cand):
        cand = os.path.join(parent, f"{name} ({i})")
        i += 1
    return cand


def extract_archive(path: str, dest: Optional[str] = None, *, progress: Progress = None,
                    cancel: Cancel = None) -> str:
    """Extract any supported archive into dest (default: a new folder beside it). Returns dest."""
    fmt = detect_format(path)
    if fmt not in ("zip", "tar", "7z", "mcc"):
        raise ArchiveError(_not_archive_message(path, fmt))
    dest_p = Path(dest or default_extract_dir(path)).resolve()
    members = list_members(path)
    for m in members:                                           # validate every name first
        _safe_target(dest_p, m["name"])
    _space_check(dest_p, sum(int(m.get("size") or 0) for m in members if not m.get("is_dir")))
    dest_p.mkdir(parents=True, exist_ok=True)
    total = max(1, sum(1 for m in members if not m.get("is_dir")))
    done = 0
    if fmt == "zip":
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                _check(cancel)
                t = _safe_target(dest_p, info.filename)
                if t is None:
                    continue
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    continue                                    # never materialise links from zip
                if info.is_dir():
                    t.mkdir(parents=True, exist_ok=True)
                    continue
                t.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(t, "wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
                if mode & 0o111:
                    os.chmod(t, 0o755)
                done += 1
                progress and progress(done, total)
    elif fmt == "tar":
        with tarfile.open(path, "r:*") as tf:
            for m in tf.getmembers():
                _check(cancel)
                t = _safe_target(dest_p, m.name)
                if t is None:
                    continue
                if m.isdir():
                    t.mkdir(parents=True, exist_ok=True)
                    continue
                if m.issym() or m.islnk():
                    link = m.linkname
                    base = t.parent if m.issym() else dest_p
                    tgt = (base / link).resolve() if not os.path.isabs(link) else Path(link)
                    if tgt != dest_p and dest_p not in tgt.parents:
                        continue                                # link escaping the destination
                    t.parent.mkdir(parents=True, exist_ok=True)
                    if m.issym():
                        if t.exists() or t.is_symlink():
                            t.unlink()
                        os.symlink(link, t)
                    elif tgt.is_file():
                        shutil.copy2(tgt, t)
                    continue
                if not m.isfile():
                    continue                                    # devices / FIFOs skipped
                t.parent.mkdir(parents=True, exist_ok=True)
                src = tf.extractfile(m)
                if src is None:
                    continue
                with src, open(t, "wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
                os.chmod(t, (m.mode & 0o777) | 0o600)
                done += 1
                progress and progress(done, total)
    elif fmt == "mcc":
        import mcc_media
        mcc_media.unpack_tree(path, str(dest_p))               # verifies sha256 before writing
        progress and progress(total, total)
    else:
        lib = _py7zr()
        if lib is not None:
            with lib.SevenZipFile(path, "r") as z:
                z.extractall(path=str(dest_p))
        else:
            exe = seven_zip_program()
            if not exe:
                raise _no_7z()
            r = subprocess.run([exe, "x", "-y", "-snl-", "-bso0", "-bsp0", f"-o{dest_p}", "--", path],
                               capture_output=True, text=True, timeout=24 * 3600)
            if r.returncode != 0:
                raise ArchiveError(f"7-Zip failed: {(r.stderr or r.stdout).strip()[:300]}")
        for p in dest_p.rglob("*"):                           # post-check: no link escapes
            if p.is_symlink():
                tgt = p.resolve()
                if tgt != dest_p and dest_p not in tgt.parents:
                    p.unlink()
        progress and progress(total, total)
    return str(dest_p)


def self_test() -> dict:
    import tempfile
    errs = []
    with tempfile.TemporaryDirectory() as td:
        src = Path(td, "src", "Album")
        (src / "sub").mkdir(parents=True)
        (src / "a.txt").write_text("alpha")
        (src / "sub" / "b.bin").write_bytes(bytes(range(256)) * 8)
        for fmt in [f for f in CREATE_FORMATS if f != "7z" or seven_zip_available()]:
            out = create_archive([str(src)], os.path.join(td, "out", "pack"), fmt)
            got = extract_archive(out, os.path.join(td, "x-" + fmt))
            if Path(got, "Album", "sub", "b.bin").read_bytes() != (src / "sub" / "b.bin").read_bytes():
                errs.append(f"{fmt}: round trip mismatch")
            if Path(got, "Album", "a.txt").read_text() != "alpha":
                errs.append(f"{fmt}: text mismatch")
    return {"ok": not errs, "errors": errs, "capabilities": capabilities()}


if __name__ == "__main__":
    import json
    print(json.dumps(self_test(), indent=2))
