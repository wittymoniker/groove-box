"""MCC integrity helpers."""
import hashlib, os
def sha256_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1048576),b""): h.update(b)
    return h.hexdigest()
def sidecar_path(path): return str(path)+".sha256"
def write_sidecar(path,digest=None):
    digest=digest or sha256_file(path); target=sidecar_path(path); tmp=target+f".{os.getpid()}.tmp"
    with open(tmp,"w",encoding="ascii",newline="\n") as f:
        f.write(digest+"  "+os.path.basename(path)+"\n"); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,target); return digest
def expected_digest(path):
    p=sidecar_path(path)
    if not os.path.isfile(p): return None
    try:
        t=open(p,"r",encoding="ascii").read().strip().split()[0].lower()
        return t if len(t)==64 and all(c in "0123456789abcdef" for c in t) else None
    except Exception: return None
def verify(path):
    e=expected_digest(path)
    if e is None: return True,None,None
    a=sha256_file(path); return a==e,e,a
def select_verified(path):
    ok,e,a=verify(path)
    if ok: return path,("verified" if e else "legacy-unverified")
    prev=str(path)+".prev"
    if os.path.isfile(prev):
        pok,_,_=verify(prev)
        if pok: return prev,"recovered-prev"
    raise IOError(f"MCC integrity check failed for {path}: expected {e}, got {a}")
