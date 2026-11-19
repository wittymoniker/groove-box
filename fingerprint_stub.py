"""fingerprint_stub.py — fprintd optional identity (lock + seed)."""
from __future__ import annotations

def available() -> bool:
    try:
        import shutil
        return __import__("sos_tools").which("fprintd-list") is not None or __import__("sos_tools").which("fprintd") is not None
    except Exception:
        return False

def verify_user(username: str = "") -> bool:
    """Best-effort; returns False if daemon missing."""
    if not available():
        return False
    return False  # real verify requires D-Bus session; wire later

def seed_from_template_id(template_id: str) -> str:
    import hashlib
    return hashlib.sha256(f"gb-fp:{template_id}".encode()).hexdigest()[:32]
