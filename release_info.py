"""RELEASE_INFO_R7 - the one place the software's version lives.

Everything that shows or records a version (startup screen, Help, game packages, the ISO's
/etc/groovebox-sos-release, CURRENT-RELEASE.txt, RELEASE-RUNTIME-MANIFEST.json, self-update) reads
it from here, so the toolchain always describes the code it is actually running:

    RELEASE / SERIES / DATE / TITLE   the human release, bumped once per archive
    live fingerprint                  SHA-256 over every top-level *.py (name + content), computed
                                      from the files on disk - it cannot go stale
    stamp (RELEASE-STAMP.json)        what scripts/stamp_release.py recorded at build/pack time

describe() reports "+local" when the live code no longer matches the stamp, so an edited tree
never claims to be the stamped release.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Optional

RELEASE = "R7v"
SERIES = "v35.22zz"
DATE = "2026-11-13"
TITLE = "SSSS · SUPERDIMENSIONAL SEED-DRIVEN SELF-COMPOSING SYNTHESIZER"
PRODUCT = "MATGROOVEBOX"
STAMP_FILE = "RELEASE-STAMP.json"

ROOT = Path(__file__).resolve().parent
_FP_CACHE: Dict[str, str] = {}


def fingerprint(root=None) -> str:
    """Order-independent identity of a code tree (same rule as self_update.fingerprint)."""
    root = Path(root or ROOT)
    h = hashlib.sha256()
    for p in sorted(root.glob("*.py")):
        try:
            h.update(p.name.encode()); h.update(hashlib.sha256(p.read_bytes()).digest())
        except OSError:
            pass
    return h.hexdigest()


def live_fingerprint(root=None) -> str:
    key = str(Path(root or ROOT))
    if key not in _FP_CACHE:
        _FP_CACHE[key] = fingerprint(key)
    return _FP_CACHE[key]


def stamped(root=None) -> Optional[dict]:
    try:
        d = __import__("safe_io").load_json(Path(root or ROOT) / STAMP_FILE, encoding="utf-8")
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def info(root=None) -> dict:
    st = stamped(root) or {}
    fp = live_fingerprint(root)
    return {"product": PRODUCT, "release": RELEASE, "series": SERIES, "date": DATE, "title": TITLE,
            "fingerprint": fp, "stamped_fingerprint": st.get("fingerprint"),
            "stamped_release": st.get("release"),
            "current": bool(st) and st.get("fingerprint") == fp and st.get("release") == RELEASE}


def version() -> str:
    return "%s-%s" % (SERIES, RELEASE)


def describe(short: bool = False, root=None) -> str:
    i = info(root)
    tag = "%s %s · %s · %s" % (PRODUCT, RELEASE, SERIES, i["fingerprint"][:12])
    if not i["current"]:
        tag += " +local"
    return tag if short else "%s — %s (%s)" % (tag, TITLE, DATE)


def header_line() -> str:
    """First line of CURRENT-RELEASE.txt (self_update.version_of_tree reads it)."""
    return "%s %s — %s" % (PRODUCT, RELEASE, TITLE)


def env_lines(root=None) -> str:
    i = info(root)
    return ("GROOVEBOX_APP_RELEASE=%s\nGROOVEBOX_APP_VERSION=%s\nGROOVEBOX_APP_DATE=%s\n"
            "GROOVEBOX_APP_FINGERPRINT=%s\n" % (RELEASE, version(), DATE, i["fingerprint"]))


if __name__ == "__main__":
    print(describe())
