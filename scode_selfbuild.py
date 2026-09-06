#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, tarfile, zipfile
from pathlib import Path

SKIP_DIRS={".git","__pycache__",".pytest_cache","release-out"}
SKIP_SUFFIXES={".pyc",".pyo"}

def files(root: Path):
    for p in sorted(root.rglob("*"), key=lambda x: x.as_posix()):
        rel=p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts): continue
        if not p.is_file() or p.suffix in SKIP_SUFFIXES: continue
        yield p, rel

def sha256(path: Path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def build(root: Path, out: Path, version: str):
    out.mkdir(parents=True,exist_ok=True)
    base=f"sCodeOS-{version}"
    zpath=out/f"{base}.zip"
    tpath=out/f"{base}.tar.gz"
    manifest=out/f"{base}.manifest.json"
    records=[]
    for p, rel in files(root):
        records.append({"path":rel.as_posix(),"sha256":sha256(p),"bytes":p.stat().st_size})
    payload={"format":"scode-release-manifest-v1","version":version,"files":records}
    manifest.write_text(json.dumps(payload,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8")
    # reproducible ZIP timestamps >= 1980
    with zipfile.ZipFile(zpath,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p, rel in files(root):
            info=zipfile.ZipInfo(rel.as_posix(),date_time=(2020,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o755 if os.access(p,os.X_OK) else 0o644)<<16
            z.writestr(info,p.read_bytes())
    with tarfile.open(tpath,"w:gz",format=tarfile.PAX_FORMAT) as t:
        for p, rel in files(root):
            ti=t.gettarinfo(str(p),arcname=rel.as_posix())
            ti.uid=ti.gid=0; ti.uname=ti.gname=""; ti.mtime=0
            with p.open("rb") as f: t.addfile(ti,f)
    sums=out/f"{base}.sha256"
    sums.write_text(
        f"{sha256(zpath)}  {zpath.name}\n"
        f"{sha256(tpath)}  {tpath.name}\n"
        f"{sha256(manifest)}  {manifest.name}\n",encoding="utf-8")
    return [zpath,tpath,manifest,sums]

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",default=str(Path(__file__).resolve().parent))
    ap.add_argument("--out",default="release-out")
    ap.add_argument("--version",required=True)
    a=ap.parse_args()
    for p in build(Path(a.root).resolve(),Path(a.out).resolve(),a.version): print(p)
