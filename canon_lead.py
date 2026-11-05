# GROOVEBOX_R23R_CANON_LEAD_20261103
"""Canon Lead system — designates one instrument as the master wave carrier.

When a Canon Lead is active the canonical engine routes every voice so the
lead synth's wavetable becomes the primary carrier for the composition.

Public API
----------
get_lead(host)              -> str | None
set_lead(host, name)        -> None
clear_lead(host)            -> None
is_lead(host, name)         -> bool

install_on_combo(combo, host)  register a QComboBox in the auto-refresh registry
refresh_all(host)              repaint all registered combos (called after set/clear)

LeadItemDelegate            QStyledItemDelegate — orange text, yellow border, [lead] tag
"""
from __future__ import annotations

import weakref
from typing import Optional

from PyQt6.QtCore import QModelIndex, QRect, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QComboBox, QStyledItemDelegate, QStyleOptionViewItem

_CANON_LEAD_ATTR = "_canon_lead_instrument"

# module-level WeakRef registry of every combo that shows instruments
_REGISTERED_COMBOS: list[weakref.ref] = []


# ---------------------------------------------------------------------------
# Core state helpers
# ---------------------------------------------------------------------------

def get_lead(host) -> Optional[str]:
    try:
        import compat_settings as _cs
        v = _cs.load().get("canon_lead_instrument")
        if v:
            return str(v)
    except Exception:
        pass
    return getattr(host, _CANON_LEAD_ATTR, None) or None


def set_lead(host, name: str) -> None:
    setattr(host, _CANON_LEAD_ATTR, str(name))
    try:
        import compat_settings as _cs
        d = _cs.load(); d["canon_lead_instrument"] = str(name); _cs.save(d)
    except Exception:
        pass
    refresh_all(host)
    _notify_canonical_engine(host)


def clear_lead(host) -> None:
    setattr(host, _CANON_LEAD_ATTR, None)
    try:
        import compat_settings as _cs
        d = _cs.load(); d.pop("canon_lead_instrument", None); _cs.save(d)
    except Exception:
        pass
    refresh_all(host)
    _notify_canonical_engine(host)


def is_lead(host, name: str) -> bool:
    lead = get_lead(host)
    return bool(lead and lead == name)


def _notify_canonical_engine(host):
    try:
        opt = getattr(host, "_scode_optimizer", None)
        if opt is not None:
            opt.invalidate_work("canonical")
    except Exception:
        pass
    # Propagate lead synth name into the canonical engine meta-store so the
    # canonical carrier mix picks it up on the next reconciliation.
    try:
        store = getattr(host, "_canonical_macro_user_store", None)
        lead = get_lead(host)
        if isinstance(store, dict) and lead:
            store.setdefault("__meta__", {})["canon_lead"] = lead
    except Exception:
        pass
    # Ensure the lead synth's params exist so randomizers always hit it.
    try:
        lead = get_lead(host)
        if lead:
            ps = getattr(host, "instrument_param_state", None)
            if isinstance(ps, dict):
                ps.setdefault(lead, {})
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Combo registry
# ---------------------------------------------------------------------------

def install_on_combo(combo: QComboBox, host) -> None:
    """Register a combo so it gets LeadItemDelegate and is refreshed on lead changes."""
    delegate = LeadItemDelegate(combo, host)
    combo.setItemDelegate(delegate)
    _REGISTERED_COMBOS.append(weakref.ref(combo))
    _REGISTERED_COMBOS[:] = [r for r in _REGISTERED_COMBOS if r() is not None]
    _apply_combo_style(combo, host)


def refresh_all(host) -> None:
    """Update stylesheet/delegate on all registered combos."""
    _REGISTERED_COMBOS[:] = [r for r in _REGISTERED_COMBOS if r() is not None]
    for ref in _REGISTERED_COMBOS:
        combo = ref()
        if combo is not None:
            try:
                _apply_combo_style(combo, host)
                combo.update()
            except Exception:
                pass


def _apply_combo_style(combo: QComboBox, host) -> None:
    """Tint the combo's closed state if the currently-selected item is the lead."""
    try:
        cur = combo.currentText()
        if is_lead(host, cur):
            combo.setStyleSheet(combo.styleSheet().split("/*lead-override*/")[0] +
                                "/*lead-override*/ QComboBox { color:#ff8c00; border:2px solid #ffd700; }")
        else:
            combo.setStyleSheet(combo.styleSheet().split("/*lead-override*/")[0])
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Item delegate — decorates every row in every instrument dropdown
# ---------------------------------------------------------------------------

_LEAD_BG   = QColor(50, 24, 0, 220)
_LEAD_FG   = QColor(255, 140, 0)
_LEAD_BORD = QColor(255, 215, 0)
_TAG_FG    = QColor(200, 230, 0)
_TAG_FONT_SCALE = 0.78


class LeadItemDelegate(QStyledItemDelegate):
    def __init__(self, combo: QComboBox, host):
        super().__init__(combo)
        self._combo = weakref.ref(combo)
        self._host  = weakref.ref(host)

    def _lead(self) -> Optional[str]:
        h = self._host()
        return get_lead(h) if h is not None else None

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        name = index.data(Qt.ItemDataRole.DisplayRole) or ""
        lead = self._lead()
        if not lead or lead != name:
            super().paint(painter, option, index)
            return

        painter.save()
        # background
        painter.fillRect(option.rect, _LEAD_BG)
        # yellow border
        painter.setPen(QPen(_LEAD_BORD, 2))
        painter.drawRect(option.rect.adjusted(1, 1, -1, -1))
        # orange text (name)
        font = QFont(option.font)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(_LEAD_FG)
        text_rect = QRect(option.rect.left() + 6, option.rect.top(),
                          option.rect.width() - 60, option.rect.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)
        # [lead] tag on the right
        tag_font = QFont(font)
        tag_font.setPointSizeF(max(6.0, font.pointSizeF() * _TAG_FONT_SCALE))
        painter.setFont(tag_font)
        painter.setPen(_TAG_FG)
        tag_rect = QRect(option.rect.right() - 54, option.rect.top(),
                         52, option.rect.height())
        painter.drawText(tag_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "[lead]")
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):
        sh = super().sizeHint(option, index)
        return sh
