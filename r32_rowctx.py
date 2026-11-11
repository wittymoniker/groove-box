"""r32_rowctx.py — GROOVEBOX_R32_PLAYLIST_COLUMNS_20261110

The playlist row being rendered, per render thread, so module hooks can read the row's columns:
  section · row_level · fx_send · time_fx_send · unison · sample_layer · mod_depth · expression
Blank / missing cells mean "no override" (the panels' values apply unchanged).
"""
import threading

_TL = threading.local()


def set_row(entry):
    _TL.row = entry


def row():
    return getattr(_TL, "row", None)


def num(key, default=None, lo=None, hi=None):
    r = row()
    if not isinstance(r, dict):
        return default
    v = r.get(key)
    if v in (None, ""):
        return default
    try:
        v = float(v)
    except Exception:
        return default
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v
