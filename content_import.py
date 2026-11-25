"""Transactional, non-executing ZIP/TAR content import helpers.

All archive members are validated and staged before destination changes begin.
Existing files replaced with ``overwrite=True`` are backed up and restored if
any commit step fails. Archive paths never create links or escape the target.
"""
from __future__ import annotations
import os
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

MAX_FILES = 10000
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024


def _safe_member(name):
    raw = str(name).replace("\\", "/")
    p = PurePosixPath(raw)
    return bool(raw) and not p.is_absolute() and ".." not in p.parts and not (p.parts and ":" in p.parts[0]) and "\x00" not in raw


def _destination(root, name):
    if not _safe_member(name):
        raise ValueError(f"Unsafe archive path: {name}")
    base = Path(root).resolve()
    lexical = base.joinpath(*PurePosixPath(str(name).replace("\\", "/")).parts)
    # Refuse symlinked destination ancestors, including a symlink at the leaf.
    cursor = base
    for part in PurePosixPath(str(name).replace("\\", "/")).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"Refusing to write through a symbolic link: {name}")
    target = lexical.resolve(strict=False)
    if target != base and base not in target.parents:
        raise ValueError(f"Archive path escapes destination: {name}")
    return target


def _collect(src):
    entries = []
    total = 0
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_FILES:
                raise ValueError("Archive contains too many entries.")
            seen = set()
            for info in infos:
                if info.is_dir():
                    continue
                name = info.filename
                if not _safe_member(name):
                    raise ValueError(f"Unsafe archive path: {name}")
                normalized = str(PurePosixPath(name.replace("\\", "/")))
                if normalized in seen:
                    raise ValueError(f"Archive contains duplicate destination: {name}")
                seen.add(normalized)
                # ZIP symlink entries carry Unix file type bits in external_attr.
                mode = (info.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    raise ValueError(f"Symbolic links are not accepted: {name}")
                total += int(info.file_size)
                if total > MAX_TOTAL_BYTES:
                    raise ValueError("Archive expands beyond the 2 GiB safety limit.")
                entries.append((name, int(info.file_size), info))
        return "zip", entries, total
    if tarfile.is_tarfile(src):
        with tarfile.open(src, "r:*") as tf:
            members = tf.getmembers()
            if len(members) > MAX_FILES:
                raise ValueError("Archive contains too many entries.")
            seen = set()
            for member in members:
                if member.isdir():
                    continue
                if not member.isfile() or member.issym() or member.islnk():
                    raise ValueError(f"Only regular files and directories are accepted: {member.name}")
                name = member.name
                if not _safe_member(name):
                    raise ValueError(f"Unsafe archive path: {name}")
                normalized = str(PurePosixPath(name.replace("\\", "/")))
                if normalized in seen:
                    raise ValueError(f"Archive contains duplicate destination: {name}")
                seen.add(normalized)
                total += int(member.size)
                if total > MAX_TOTAL_BYTES:
                    raise ValueError("Archive expands beyond the 2 GiB safety limit.")
                entries.append((name, int(member.size), member))
        return "tar", entries, total
    raise ValueError("Unsupported archive. Choose ZIP or TAR/TAR.GZ.")


def import_archive(archive, destination, *, overwrite=False):
    """Validate, stage, then transactionally extract ZIP/TAR without execution."""
    src, dest = Path(archive), Path(destination)
    if not src.is_file():
        raise FileNotFoundError(str(src))
    dest.mkdir(parents=True, exist_ok=True)
    dest = dest.resolve()
    kind, entries, total = _collect(src)

    # Preflight all paths and conflicts before creating any destination files.
    targets = []
    for name, _size, _member in entries:
        target = _destination(dest, name)
        if target.exists() and not target.is_file():
            raise ValueError(f"Destination is not a regular file: {target}")
        if target.exists() and not overwrite:
            raise FileExistsError(str(target))
        targets.append((name, target))

    temp_root = Path(tempfile.mkdtemp(prefix=".groovebox-import-", dir=str(dest)))
    stage = temp_root / "stage"
    backup = temp_root / "backup"
    stage.mkdir(); backup.mkdir()
    committed = []
    backed_up = []
    created_dirs = []
    try:
        # Extract into a private staging tree. No destination data has changed.
        if kind == "zip":
            with zipfile.ZipFile(src) as zf:
                for name, _size, info in entries:
                    staged = stage.joinpath(*PurePosixPath(name.replace("\\", "/")).parts)
                    staged.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as inp, staged.open("xb") as out:
                        shutil.copyfileobj(inp, out)
        else:
            with tarfile.open(src, "r:*") as tf:
                for name, _size, member in entries:
                    inp = tf.extractfile(member)
                    if inp is None:
                        raise ValueError(f"Unable to read archive member: {name}")
                    staged = stage.joinpath(*PurePosixPath(name.replace("\\", "/")).parts)
                    staged.parent.mkdir(parents=True, exist_ok=True)
                    with inp, staged.open("xb") as out:
                        shutil.copyfileobj(inp, out)

        # Commit with same-filesystem atomic moves and reversible backups.
        for index, (name, target) in enumerate(targets):
            _destination(dest, name)  # revalidate immediately before commit
            parent = target.parent
            missing = []
            cursor = parent
            while cursor != dest and not cursor.exists():
                missing.append(cursor); cursor = cursor.parent
            for directory in reversed(missing):
                directory.mkdir(exist_ok=True)
                created_dirs.append(directory)
            if target.exists():
                if not overwrite:
                    raise FileExistsError(str(target))
                saved = backup / f"{index:08d}.bak"
                os.replace(target, saved)
                backed_up.append((saved, target))
            staged = stage.joinpath(*PurePosixPath(name.replace("\\", "/")).parts)
            os.replace(staged, target)
            committed.append(target)
    except Exception as exc:
        rollback_errors = []
        for target in reversed(committed):
            try:
                if target.exists() or target.is_symlink():
                    target.unlink()
            except OSError as rollback_exc:
                rollback_errors.append(f"could not remove {target}: {rollback_exc}")
        for saved, target in reversed(backed_up):
            try:
                if saved.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(saved, target)
            except OSError as rollback_exc:
                rollback_errors.append(f"could not restore {target}: {rollback_exc}")
        for directory in reversed(created_dirs):
            try: directory.rmdir()
            except OSError: pass
        if rollback_errors:
            raise RuntimeError("Import failed and rollback was incomplete; recovery data was preserved at "
                               + str(backup) + ". " + "; ".join(rollback_errors)) from exc
        shutil.rmtree(temp_root, ignore_errors=True)
        raise
    else:
        shutil.rmtree(temp_root, ignore_errors=True)

    return {"files": [str(target) for _name, target in targets],
            "count": len(targets), "bytes": total, "executed": False,
            "destination": str(dest)}
