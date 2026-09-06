#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, tempfile, urllib.request
from pathlib import Path

def sha256(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def fetch_json(url):
    with urllib.request.urlopen(url,timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def download(url,dst):
    with urllib.request.urlopen(url,timeout=60) as r, open(dst,"wb") as f:
        shutil.copyfileobj(r,f)

def main():
    ap=argparse.ArgumentParser(description="Explicit sCodeOS release updater; never scans or spreads.")
    ap.add_argument("--channel-url",required=True)
    ap.add_argument("--install-root",required=True)
    ap.add_argument("--check-only",action="store_true")
    a=ap.parse_args()
    meta=fetch_json(a.channel_url)
    for k in ("version","artifact_url","sha256"): 
        if k not in meta: raise SystemExit(f"bad channel metadata: missing {k}")
    print("available:",meta["version"])
    if a.check_only: return 0
    root=Path(a.install_root).resolve()
    releases=root/"releases"; releases.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        pkg=Path(td)/"release.zip"; download(meta["artifact_url"],pkg)
        actual=sha256(pkg)
        if actual.lower()!=str(meta["sha256"]).lower():
            raise SystemExit("SHA-256 verification failed")
        target=releases/meta["version"]
        if target.exists(): shutil.rmtree(target)
        shutil.unpack_archive(str(pkg),str(target),"zip")
        current=root/"current"
        previous=root/"previous"
        if current.exists() or current.is_symlink():
            try:
                if previous.exists() or previous.is_symlink(): previous.unlink()
                previous.symlink_to(current.resolve(),target_is_directory=True)
            except Exception: pass
        tmp=root/"current.new"
        if tmp.exists() or tmp.is_symlink(): tmp.unlink()
        tmp.symlink_to(target,target_is_directory=True)
        tmp.replace(current)
    print("activated:",meta["version"])
    return 0

if __name__=="__main__": raise SystemExit(main())
