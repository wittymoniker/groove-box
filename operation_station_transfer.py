#!/usr/bin/env python3
"""Operation Station transfer/clone helpers.

Provides versioned, checksum-manifested bundles that can be copied to USB/mounted
storage or served over Wi-Fi/Ethernet. The receiver still chooses whether to run
or install the cloned code; this module never executes received content.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib, json, os, platform, shutil, socket, tempfile, threading, time, zipfile
from typing import Callable, Dict, List, Optional

FORMAT = "MathematiciansGrooveboxOperationStationClone"
VERSION = 3
DEFAULT_EXCLUDES = {"__pycache__", ".git", ".pytest_cache", "build", "dist", ".venv", "venv"}

@dataclass
class CloneManifest:
    format: str
    version: int
    created_utc: str
    machine: str
    python: str
    payload_kind: str
    app_version: str
    files: List[Dict]


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _wanted(rel: Path, include_source=True, include_executables=True, include_dependencies=True):
    parts=set(rel.parts)
    if parts & DEFAULT_EXCLUDES: return False
    s=str(rel).replace('\\','/')
    if s.startswith('exports/') or s.startswith('renders/'): return False
    if not include_source and rel.suffix.lower() in {'.py','.pyi','.cpp','.hpp','.h','.jl'}: return False
    if not include_executables and ('BUILD_KIT' in parts or 'dist' in parts): return False
    if not include_dependencies and ('wheelhouse' in parts or rel.name.lower().startswith(('ffmpeg','ffprobe'))): return False
    return True


def create_clone_bundle(root: str, out_path: str, *, include_source=True, include_executables=True,
                        include_dependencies=True, include_user_content=False, user_data_root: Optional[str]=None,
                        app_version='V3 Operation Station') -> str:
    rootp=Path(root).resolve(); out=Path(out_path).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
    files=[]
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(rootp.rglob('*')):
            if not p.is_file(): continue
            rel=p.relative_to(rootp)
            if not _wanted(rel,include_source,include_executables,include_dependencies): continue
            if not include_user_content and rel.parts and rel.parts[0] in {'projects','samples','modules'}:
                # preserve folder contracts through README/keep files only; don't clone private creative content by default
                continue
            if p.resolve()==out: continue
            z.write(p, arcname=str(Path('payload')/rel))
            files.append({'path':str(rel).replace('\\','/'),'size':p.stat().st_size,'sha256':sha256_file(p)})
        if include_user_content and user_data_root:
            udp=Path(user_data_root).expanduser().resolve()
            # User content is stored separately from executable source so an
            # appliance clone never confuses mutable projects with /opt code.
            for top in ('projects','samples','modules','games'):
                base=udp/top
                if not base.exists(): continue
                for p in sorted(base.rglob('*')):
                    if not p.is_file() or p.is_symlink(): continue
                    rel=Path('user_data')/p.relative_to(udp)
                    arc=Path('payload')/rel
                    z.write(p,arcname=str(arc))
                    files.append({'path':str(rel).replace('\\','/'),'size':p.stat().st_size,'sha256':sha256_file(p)})
        manifest=CloneManifest(FORMAT,VERSION,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
            platform.platform(),platform.python_version(),'operation-station-clone',app_version,files)
        z.writestr('manifest.json',json.dumps(asdict(manifest),indent=2))
    return str(out)


def verify_clone_bundle(path: str) -> Dict:
    p=Path(path)
    with zipfile.ZipFile(p,'r') as z:
        m=json.loads(z.read('manifest.json').decode('utf-8'))
        if m.get('format')!=FORMAT: raise ValueError('Not an Operation Station clone bundle')
        bad=[]
        for f in m.get('files',[]):
            arc='payload/'+f['path']
            try: data=z.read(arc)
            except KeyError: bad.append(f['path']+': missing'); continue
            if hashlib.sha256(data).hexdigest()!=f['sha256']: bad.append(f['path']+': checksum')
        return {'ok':not bad,'bad':bad,'manifest':m}


def detect_removable_mounts() -> List[str]:
    roots=[]
    user=os.environ.get('USER','')
    for base in ['/media/'+user if user else '', '/run/media/'+user if user else '', '/mnt', '/Volumes']:
        if base and os.path.isdir(base):
            for p in Path(base).iterdir():
                if p.is_dir() and os.access(p,os.W_OK): roots.append(str(p.resolve()))
    return sorted(set(roots))


def copy_bundle(bundle: str, destination: str) -> str:
    dst=Path(destination).expanduser().resolve(); dst.mkdir(parents=True,exist_ok=True)
    target=dst/Path(bundle).name
    shutil.copy2(bundle,target)
    shutil.copy2(bundle,str(target)+'.sha256.tmp') if False else None
    Path(str(target)+'.sha256').write_text(sha256_file(target)+'  '+target.name+'\n',encoding='utf-8')
    return str(target)


def _iso_candidates(roots) -> List[Path]:
    """Return real .iso files reachable from the supplied roots.

    The search is deliberately shallow.  The finished Groovebox image lives in
    ``BUILD_ISO/dist`` beside the source tree, or next to a packaged executable;
    it is never buried in a random project subdirectory.  Keeping the walk
    shallow also avoids touching a slow USB stick while the GUI is starting.
    """
    seen=set(); out=[]
    for root in roots:
        if not root: continue
        try: p=Path(root).expanduser()
        except Exception: continue
        try:
            if p.is_file():
                candidates=[p] if p.suffix.lower()=='.iso' else []
            elif p.is_dir():
                candidates=[]
                for pattern in ('*.iso','*/*.iso','*/*/*.iso'):
                    try: candidates.extend(p.glob(pattern))
                    except Exception: pass
            else:
                continue
        except OSError:
            continue
        for c in candidates:
            try:
                r=c.resolve()
                if r in seen or not r.is_file() or r.suffix.lower()!='.iso': continue
                seen.add(r); out.append(r)
            except OSError:
                pass
    return out


SELF_ISO_PATH = Path("/opt/groovebox/self.iso")

def ensure_self_iso(source: Optional[str] = None, *, force: bool = False) -> Optional[Path]:
    """Keep a copy of this system's ISO at a known path for Copy to Disk.

    Refuses if free space is under the image size plus 512 MiB. Rebuilds when
    the source is newer than the self-ISO (stale). Returns the self-ISO path,
    or None. Writes a .sha256 next to it.
    """
    import shutil, hashlib
    try:
        SELF_ISO_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    src = None
    if source and os.path.isfile(source):
        src = Path(source)
    else:
        found = find_finished_iso()
        if found and found != SELF_ISO_PATH:
            src = found
    if src is None:
        return SELF_ISO_PATH if SELF_ISO_PATH.is_file() else None
    if src.resolve() == SELF_ISO_PATH.resolve():
        return SELF_ISO_PATH
    # Stale: skip copy if self-ISO is newer, unless forced.
    try:
        if (not force) and SELF_ISO_PATH.is_file() and SELF_ISO_PATH.stat().st_mtime >= src.stat().st_mtime:
            return SELF_ISO_PATH
    except Exception:
        pass
    # Space: need image size + 512 MiB free on the target volume.
    try:
        need = src.stat().st_size + 512 * 1024 * 1024
        free = shutil.disk_usage(str(SELF_ISO_PATH.parent)).free
        if free < need:
            return None
    except Exception:
        pass
    try:
        shutil.copy2(src, SELF_ISO_PATH)
        h = hashlib.sha256()
        with open(SELF_ISO_PATH, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        (SELF_ISO_PATH.with_suffix(".iso.sha256")).write_text(h.hexdigest() + "\n")
        return SELF_ISO_PATH
    except Exception:
        return src


def find_finished_iso(*extra_roots, prefer_name: Optional[str]=None) -> Optional[Path]:
    """Locate the newest finished Groovebox ISO without prompting the user.

    Search order covers the source tree, the packaged executable, the installed
    appliance and the usual Downloads folder.  Set ``GROOVEBOX_ISO`` (or
    ``GROOVEBOX_ISO_PATH``) to point at a specific image when running from a
    read-only live medium.
    """
    roots=[]
    env=os.environ.get('GROOVEBOX_ISO') or os.environ.get('GROOVEBOX_ISO_PATH')
    if env: roots.append(env)
    roots.extend(extra_roots)
    here=Path(__file__).resolve().parent
    roots.extend([here, here/'BUILD_ISO'/'dist', here/'dist'])
    for parent in list(here.parents)[:4]:
        roots.extend([parent/'BUILD_ISO'/'dist', parent/'dist'])
    roots.extend([
        SELF_ISO_PATH,
        Path('/opt/groovebox/BUILD_ISO/dist'), Path('/opt/groovebox/dist'),
        Path.home()/'Downloads', Path.cwd(),
    ])
    candidates=_iso_candidates(roots)
    if prefer_name:
        named=[c for c in candidates if prefer_name.lower() in c.name.lower()]
        if named: candidates=named
    if not candidates: return None
    try: return max(candidates,key=lambda p:p.stat().st_mtime)
    except OSError: return candidates[0]


def copy_iso_to_mount(iso: str, destination: str, *, subdir: str='Groovebox/ISO',
                      progress: Optional[Callable[[int,int,str],None]]=None) -> Dict:
    """Copy a finished ISO into a mounted drive without disturbing its contents.

    This is the OS-update style path: the image is placed in a subdirectory,
    every existing file/folder beside it is preserved, and an existing image of
    the same name is replaced atomically through a ``.part`` file.  A SHA-256
    sidecar is written after the copy so the receiving machine can verify it.

    ``destination`` is a mounted directory (USB/SD/another disk), not a raw
    block device.  Raw ``dd`` writing is intentionally not used here because it
    would destroy the files the user asked us to preserve.
    """
    src=Path(iso).expanduser().resolve()
    if not src.is_file(): raise FileNotFoundError(f'ISO not found: {src}')
    if src.suffix.lower()!='.iso': raise ValueError(f'Not an ISO image: {src}')
    dst=Path(destination).expanduser().resolve()
    if not dst.is_dir(): raise NotADirectoryError(f'Destination is not a mounted directory: {dst}')
    if not os.access(dst,os.W_OK): raise PermissionError(f'Destination is not writable: {dst}')
    target_dir=dst/subdir
    target_dir.mkdir(parents=True,exist_ok=True)
    target=target_dir/src.name
    if target.resolve()==src:
        return {'path':str(target),'sha256':sha256_file(target),'bytes':target.stat().st_size,
                'source':str(src),'subdir':subdir,'skipped':True}
    total=src.stat().st_size
    try:
        free=shutil.disk_usage(dst).free
    except OSError:
        free=total
    if free < total:
        raise OSError(f'Not enough free space on {dst}: need {total} bytes, have {free}')
    part=target.with_name(target.name+'.part')
    try:
        with src.open('rb') as rf, part.open('wb') as wf:
            done=0
            if progress: progress(0,total,'copying')
            while True:
                chunk=rf.read(8*1024*1024)
                if not chunk: break
                wf.write(chunk); done+=len(chunk)
                if progress: progress(done,total,'copying')
            wf.flush(); os.fsync(wf.fileno())
        shutil.copystat(src,part)
        os.replace(part,target)
        digest=sha256_file(target)
        Path(str(target)+'.sha256').write_text(f'{digest}  {target.name}\n',encoding='utf-8')
    finally:
        try:
            if part.exists(): part.unlink()
        except OSError:
            pass
    if progress: progress(total,total,'verified')
    return {'path':str(target),'sha256':digest,'bytes':total,'source':str(src),
            'subdir':subdir,'skipped':False}


def local_addresses(port:int) -> List[str]:
    ips=set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET):
            ip=info[4][0]
            if not ip.startswith('127.'): ips.add(ip)
    except Exception: pass
    return [f'http://{ip}:{port}/' for ip in sorted(ips)] or [f'http://127.0.0.1:{port}/']

class CloneShareServer:
    def __init__(self, directory:str, port:int=8783):
        self.directory=str(Path(directory).resolve()); self.port=int(port); self.httpd=None; self.thread=None
    def start(self):
        directory=self.directory
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self,*a,**kw): super().__init__(*a,directory=directory,**kw)
            def log_message(self,fmt,*args): pass
        self.httpd=ThreadingHTTPServer(('0.0.0.0',self.port),Handler)
        self.thread=threading.Thread(target=self.httpd.serve_forever,daemon=True); self.thread.start(); return self.urls()
    def urls(self): return local_addresses(self.port)
    def stop(self):
        if self.httpd:
            self.httpd.shutdown(); self.httpd.server_close(); self.httpd=None


def write_bootable_installer(iso: str, device: str, *, progress=None) -> dict:
    """Write the ISO as a bootable image to a whole-disk USB device.

    BOOTABLE_20261107: this is the raw write path. It erases the device.
    Refuses the system disk and any mounted partition of the target.
    """
    import subprocess, shutil
    src = Path(iso).expanduser().resolve()
    if not src.is_file() or src.suffix.lower() != ".iso":
        raise ValueError(f"Not an ISO: {src}")
    table = iso_partition_table(str(src))
    if not table.get("ok"):
        raise ValueError("This ISO has no hybrid partition table (%s). Rebuild it; the builder must run --patch-hybrid-mbr." % table.get("message"))
    from drive_guard import assert_safe_target
    dev = assert_safe_target(device)
    # Refuse if any partition of the device is mounted.
    try:
        mounts = subprocess.check_output(["findmnt", "-n", "-o", "SOURCE"], text=True)
        if any(line.startswith(dev) for line in mounts.splitlines()):
            raise PermissionError(f"{dev} has a mounted partition. Unmount it first.")
    except FileNotFoundError:
        pass
    dd = shutil.which("dd")
    if not dd:
        raise RuntimeError("dd not found")
    total = src.stat().st_size
    if progress:
        progress(0, total, "writing")
    # bs=4M, conv=fsync so the stick is complete before we return.
    cmd = [dd, f"if={src}", f"of={dev}", "bs=4M", "conv=fsync", "status=progress"]
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"dd failed: {proc.returncode}")
    if progress:
        progress(total, total, "done")
    return {"device": dev, "iso": str(src), "bytes": total}


def reclaim_usb_space(device: str, *, label: str = "GROOVEBOX") -> dict:
    """Create a FAT32 data partition in the free space after a bootable ISO write.

    Uses parted if present, otherwise sfdisk. Refuses the system disk.
    Returns {"device", "partition", "message"}.
    """
    import subprocess, shutil
    from drive_guard import assert_safe_target
    dev = assert_safe_target(device)
    # Unmount any partitions of this device first.
    try:
        mounts = subprocess.check_output(["findmnt", "-n", "-o", "SOURCE,TARGET"], text=True)
        for line in mounts.splitlines():
            src, _, tgt = line.partition(" ")
            if src.startswith(dev):
                subprocess.run(["udisksctl", "unmount", "-b", src], capture_output=True, timeout=15)
    except Exception:
        pass
    parted = shutil.which("parted")
    mkfs = shutil.which("mkfs.vfat") or shutil.which("mkfs.fat")
    if parted:
        # Print free space, then make a primary FAT32 in the largest free region.
        subprocess.run([parted, "-s", dev, "print"], check=False, capture_output=True, timeout=20)
        # mkpart primary fat32 <start> 100%  — parted accepts 100% as the end.
        r = subprocess.run([parted, "-s", dev, "mkpart", "primary", "fat32", "0%", "100%"],
                           capture_output=True, text=True, timeout=30)
        # If the disk already has the ISO partition, the second mkpart uses the free tail.
        # Retry with an explicit free-space start if the first was rejected.
        if r.returncode != 0:
            r = subprocess.run([parted, "-s", dev, "mkpart", "primary", "fat32", "-1", "100%"],
                               capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            raise RuntimeError("parted could not add a data partition: " + (r.stderr or r.stdout or "").strip()[-200:])
    else:
        sfdisk = shutil.which("sfdisk")
        if not sfdisk:
            raise RuntimeError("Neither parted nor sfdisk is installed. Install parted to reclaim USB space.")
        # Append a partition that fills the rest of the disk.
        script = "write\n"
        r = subprocess.run([sfdisk, "--append", dev], input="size=+\n", text=True,
                           capture_output=True, timeout=30)
        if r.returncode != 0:
            raise RuntimeError("sfdisk failed: " + (r.stderr or "").strip()[-200:])
    # Find the newest partition and format it.
    part = None
    try:
        out = subprocess.check_output(["lsblk", "-n", "-o", "NAME,TYPE", dev], text=True, timeout=10)
        parts = [ln.split()[0] for ln in out.splitlines() if len(ln.split()) == 2 and ln.split()[1] == "part"]
        if parts:
            part = "/dev/" + parts[-1]
    except Exception:
        pass
    if part and mkfs:
        subprocess.run([mkfs, "-F", "32", "-n", label[:11], part], check=False, capture_output=True, timeout=60)
    return {"device": dev, "partition": part or "", "message": "Data partition created" + (f" at {part}" if part else "")}


def verify_iso_builder(root: Optional[str] = None) -> dict:
    """Check that the in-tree ISO builder and active overlay are present and consistent.

    Does not run the full build. Returns {"ok", "notes": [...], "script", "overlay"}.
    """
    from pathlib import Path as _P
    here = _P(root) if root else _P(__file__).resolve().parent
    notes = []
    script = here / "BUILD_ISO" / "RUN_ME_ZERO_STATE.sh"
    overlay = here / "BUILD_ISO" / "app-overlay-v35.22zz"
    ok = True
    if not script.is_file():
        ok = False
        notes.append("missing " + str(script))
    else:
        notes.append("builder script present")
    if not overlay.is_dir():
        ok = False
        notes.append("missing active overlay")
    else:
        must = ["groovebox.py", "live_player.py", "export_scheduler.py", "export_worker.py"]
        missing = [m for m in must if not (overlay / m).is_file()]
        if missing:
            ok = False
            notes.append("overlay missing: " + ", ".join(missing))
        else:
            notes.append("active overlay has core modules")
    iso = find_finished_iso(here)
    notes.append("finished ISO: " + (str(iso) if iso else "none found (build first)"))
    if iso:
        table = iso_partition_table(str(iso))
        notes.append("partition table: " + table.get("message", ""))
    return {"ok": ok, "notes": notes, "script": str(script), "overlay": str(overlay)}


def build_self_iso(root: Optional[str] = None, *, progress=None) -> dict:
    """Run the in-tree ISO builder from an installed app or a source checkout.

    Looks for BUILD_ISO/RUN_ME_ZERO_STATE.sh next to this module, under
    /opt/groovebox, and beside a frozen executable. Returns {"ok", "message", "iso"}.
    """
    import subprocess
    from pathlib import Path as _P
    candidates = []
    here = _P(__file__).resolve().parent
    candidates.append(here)
    candidates.append(_P("/opt/groovebox/app"))
    candidates.append(_P("/opt/groovebox"))
    if root:
        candidates.insert(0, _P(root))
    script = None
    for c in candidates:
        s = c / "BUILD_ISO" / "RUN_ME_ZERO_STATE.sh"
        if s.is_file():
            script = s
            break
    if script is None:
        return {"ok": False, "message": "ISO builder script not found. Install the BUILD_ISO tree or run from a source checkout.", "iso": ""}
    if progress:
        progress(0, 1, "starting builder")
    try:
        env = os.environ.copy()
        env["GROOVEBOX_SECURE_BOOT"] = "0"
        r = subprocess.run(["bash", str(script)], cwd=str(script.parent.parent),
                           capture_output=True, text=True, timeout=3600, env=env)
    except Exception as exc:
        return {"ok": False, "message": f"builder failed to start: {exc}", "iso": ""}
    if r.returncode != 0:
        tail = (r.stderr or r.stdout or "").strip()[-400:]
        return {"ok": False, "message": f"builder exited {r.returncode}: {tail}", "iso": ""}
    iso = find_finished_iso(script.parent.parent)
    return {"ok": True, "message": "ISO build finished", "iso": str(iso) if iso else ""}


def iso_partition_table(iso: str) -> dict:
    """Read the hybrid MBR of an ISO. A bootable Groovebox ISO must have a
    0x55AA signature and a type-0xEF EFI partition."""
    import struct
    pth = Path(iso)
    if not pth.is_file() or pth.stat().st_size < 512:
        return {"ok": False, "entries": [], "message": "not an ISO or too small"}
    with open(pth, "rb") as f:
        f.seek(446)
        raw = f.read(66)
    if raw[64:66] != b"\x55\xaa":
        return {"ok": False, "entries": [], "message": "no MBR signature — this ISO has no partition table"}
    entries = []
    for i in range(4):
        ent = raw[i * 16:(i + 1) * 16]
        if ent == b"\x00" * 16:
            continue
        typ = ent[4]
        start, count = struct.unpack_from("<II", ent, 8)
        entries.append({"type": typ, "start": start, "count": count})
    has_efi = any(e["type"] == 0xEF for e in entries)
    return {
        "ok": bool(entries) and has_efi,
        "entries": entries,
        "message": "hybrid MBR with EFI partition" if has_efi else "partition table present but no type-0xEF EFI partition",
    }
