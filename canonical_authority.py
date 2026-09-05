"""Canonical single-source-of-truth authority for Groovebox v13.

The legacy Groovebox has many historical live attributes.  This module makes
one immutable-ish project document authoritative at engine boundaries while
keeping compatibility with those attributes.  Live UI state is synchronized
into the canonical document before a render/export/game operation; canonical
loads are applied back to the live surface after project restore.
"""
from __future__ import annotations
import copy, hashlib, json
from typing import Any, Mapping

VERSION = "canonical_authority_v13"


def _stable(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()[:16]


def _clean(value: Any):
    try:
        return copy.deepcopy(value)
    except Exception:
        try:
            return json.loads(json.dumps(value, default=str))
        except Exception:
            return None


class CanonicalAuthority:
    """Authoritative document + explicit read/write/sync API.

    The document is the source of truth at persistence and engine boundaries.
    Legacy app attributes remain compatibility mirrors, not independent
    serialized sources.
    """

    def __init__(self, app=None):
        self.app = app
        self.document = {}
        self.revision = 0
        self.last_write = ""

    @property
    def fingerprint(self) -> str:
        return _stable(self.document)

    def read(self, path=None, default=None):
        """Read canonical state.  Dotted paths are supported."""
        if path is None:
            return _clean(self.document)
        cur = self.document
        for part in str(path).split("."):
            if not isinstance(cur, Mapping) or part not in cur:
                return default
            cur = cur[part]
        return _clean(cur)

    def write(self, path, value):
        """Write canonical state and advance its revision."""
        parts = str(path).split(".")
        if not parts or not parts[0]:
            raise ValueError("canonical path must not be empty")
        cur = self.document
        for part in parts[:-1]:
            nxt = cur.get(part)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[part] = nxt
            cur = nxt
        cur[parts[-1]] = _clean(value)
        self.revision += 1
        self.last_write = str(path)
        return self.read(path)

    def replace(self, document, *, revision=True):
        self.document = _clean(document) if isinstance(document, dict) else {}
        if revision:
            self.revision += 1
        self.last_write = "<replace>"
        return self.read()

    def sync_from_live(self):
        """Capture the complete legacy project surface into canonical state."""
        if self.app is None:
            return self.read()
        setattr(self.app, "_canonical_syncing", True)
        try:
            legacy = self.app._legacy_project_snapshot()
        finally:
            setattr(self.app, "_canonical_syncing", False)
        self.document = _clean(legacy) or {}
        self.document.setdefault("canonical_authority", {})
        self.document["canonical_authority"].update({
            "version": VERSION,
            "revision": int(self.revision + 1),
            "fingerprint": _stable(self.document),
        })
        self.revision += 1
        return self.read()

    def sync_from_document(self, document):
        self.replace(document)
        return self.read()

    def apply_to_live(self, document=None):
        """Restore canonical state to legacy mirrors through the existing loader."""
        doc = self.read() if document is None else _clean(document)
        if self.app is None:
            self.replace(doc)
            return doc
        self.app._legacy_apply_project_snapshot(doc or {})
        self.document = _clean(doc) if isinstance(doc, dict) else {}
        self.revision += 1
        self.last_write = "<apply_to_live>"
        return self.read()

    def engine_document(self, *, waveform=None, sample_rate=48000):
        """Return the canonical document plus cross-media analysis.

        The cross-media module is intentionally called with the canonical
        document, never asked to rediscover independent engine state.
        """
        if not self.document:
            self.sync_from_live()
        try:
            import canonical_cross_media as cm
            cross = cm.build_cross_media_from_canonical(self.document, waveform, sample_rate)
        except Exception:
            cross = _clean(self.document.get("cross_media") or {})
        out = _clean(self.document) or {}
        out["cross_media"] = cross
        out["canonical_authority"] = {
            "version": VERSION,
            "revision": int(self.revision),
            "fingerprint": _stable(out),
        }
        return out

    def provenance(self):
        doc = self.read()
        return {
            "canonical_authority_version": VERSION,
            "canonical_revision": int(self.revision),
            "canonical_fingerprint": _stable(doc),
            "canonical_document": doc,
        }
