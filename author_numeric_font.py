"""Cached code-defined author-number font for Mathematician's Groovebox.

The semantic spelling lives in :mod:`author_number_codec`; this module is only
responsible for turning immutable 0..16/squiggle/subscale packets into cached Qt
pixmaps.  Numeric editors keep their real QSpinBox/QDoubleSpinBox values and
ordinary editable text.  When unfocused, a child QLabel presents the cached
author glyph packet inside the field.

Performance contract:
- no Paint-event interception;
- no application-wide widget rescans;
- value spelling is dirty-gated per field;
- semantic packets are memoized in the required sCode-selected symbol pool;
- individual glyph faces are cached separately from complete number pixmaps;
- identical fields therefore share both spelling packets and rendered faces.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QPointF, QRectF, QEvent
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QPalette, QFont
from PyQt6.QtWidgets import QLabel, QDoubleSpinBox

from ot_symbol_notation import (
    Role as OTRole,
    Operation as OTOperation,
    ROLE_COLORS as OT_ROLE_COLORS,
    encode_nibble as ot_encode_nibble,
    direction_for as ot_direction_for,
)
from author_number_codec import (
    SCHEME as AUTHOR_NUMBER_SCHEME,
    FULL_CYCLE_VALUE,
    PRECOMPUTED_VARIANT_COUNT,
    NumberSpelling,
    GlyphVariant,
    normalize_numeric_text,
    spell_number,
    set_fraction_spacing,
    scheme_manifest,
)

PREFERRED_CELL_PX = 42.0
MAX_INWARD_CYCLES = 4
DEFAULT_CACHE_LIMIT = 4096
DEFAULT_FACE_CACHE_LIMIT = 1536


def _role_key(role):
    return getattr(role, "value", str(role))


def _operation_key(operation):
    return getattr(operation, "value", str(operation))


def _role_color(role) -> str:
    return OT_ROLE_COLORS.get(role, OT_ROLE_COLORS.get(OTRole.RESULT, "#2f80ff"))


def quarter_cycle_state(index: int, negative: bool = False, cell: float = PREFERRED_CELL_PX):
    """Relative placement: quarter-cell walk, then inward after each cycle."""
    i = max(0, int(index))
    phase = i & 3
    cycle = min(i // 4, MAX_INWARD_CYCLES)
    q = max(2.0, float(cell) * 0.25)
    inward_step = max(0.5, float(cell) / 16.0)
    cw = ((0.0, -q), (q, 0.0), (0.0, q), (-q, 0.0))
    ccw = ((0.0, -q), (-q, 0.0), (0.0, q), (q, 0.0))
    dx, dy = (ccw if negative else cw)[phase]
    inward = cycle * inward_step
    if dx > 0:
        dx -= inward
    elif dx < 0:
        dx += inward
    if dy > 0:
        dy -= inward
    elif dy < 0:
        dy += inward
    return dx, dy, inward, phase


class AuthorNumericFontLibrary:
    """Shared glyph-face + complete-number pixmap atlas."""

    def __init__(self, cache_limit: int = DEFAULT_CACHE_LIMIT, face_cache_limit: int = DEFAULT_FACE_CACHE_LIMIT):
        self.cache_limit = max(128, int(cache_limit))
        self.face_cache_limit = max(128, int(face_cache_limit))
        self._cache: OrderedDict[tuple, QPixmap] = OrderedDict()
        self._face_cache: OrderedDict[tuple, QPixmap] = OrderedDict()
        self._optimizer = None
        self._stats = {
            "number_hits": 0, "number_misses": 0,
            "face_hits": 0, "face_misses": 0,
            "spelling_requests": 0,
        }

    def bind_optimizer(self, optimizer) -> None:
        """Bind the already-verified required sCode optimizer singleton."""
        self._optimizer = optimizer

    def clear(self):
        self._cache.clear()
        self._face_cache.clear()

    def stats(self) -> dict:
        return dict(self._stats)

    @staticmethod
    def normalize_display_text(text: str) -> str:
        return normalize_numeric_text(text)

    def spell(self, text: str) -> NumberSpelling:
        normalized = normalize_numeric_text(text)
        self._stats["spelling_requests"] += 1
        opt = self._optimizer
        if opt is not None and hasattr(opt, "memoized_symbol_spelling"):
            return opt.memoized_symbol_spelling(
                (AUTHOR_NUMBER_SCHEME, normalized),
                lambda: spell_number(normalized),
            )
        return spell_number(normalized)

    @staticmethod
    def _pen(color, width=2.25, dotted=False):
        pen = QPen(QColor(color), float(width))
        if dotted:
            pen.setStyle(Qt.PenStyle.DotLine)
        return pen

    def _draw_stroke(self, painter, cx, cy, dx, dy, squiggly, color):
        if not squiggly:
            painter.setPen(self._pen(color, 2.55))
            painter.drawLine(QPointF(cx, cy), QPointF(cx + dx, cy + dy))
            return
        path = QPainterPath(QPointF(cx, cy))
        px, py = -dy, dx
        length = max((dx * dx + dy * dy) ** 0.5, 1.0)
        px, py = px / length * 1.7, py / length * 1.7
        path.cubicTo(
            QPointF(cx + dx * .30 + px, cy + dy * .30 + py),
            QPointF(cx + dx * .70 - px, cy + dy * .70 - py),
            QPointF(cx + dx, cy + dy),
        )
        painter.setPen(self._pen(color, 2.45))
        painter.drawPath(path)

    def _draw_incell_squiggle(self, painter, x, y, size, color):
        """2^-1 fractional modifier drawn *inside* its integer/count cell."""
        painter.save()
        painter.setPen(QPen(QColor(color), max(1.25, size * 0.036)))
        path = QPainterPath()
        x0, x1 = x + size * 0.22, x + size * 0.78
        cy = y + size * 0.84
        amp = size * 0.055
        path.moveTo(x0, cy)
        path.cubicTo(x0+(x1-x0)*.22, cy-amp, x0+(x1-x0)*.44, cy+amp, x0+(x1-x0)*.66, cy-amp)
        path.cubicTo(x0+(x1-x0)*.80, cy+amp, x0+(x1-x0)*.92, cy-amp, x1, cy)
        painter.drawPath(path)
        painter.restore()

    def _draw_glyph(self, painter, glyph, x, y, size):
        color = OT_ROLE_COLORS.get(glyph.role, "#2f80ff")
        if color == "#000000":
            painter.fillRect(QRectF(x, y, size, size), QColor("#b8b8b8"))
        painter.setPen(self._pen(color, 2.55))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(x + 1.5, y + 1.5, size - 3.0, size - 3.0))
        cx, cy = x + size / 2.0, y + size / 2.0
        empty_zero = int(getattr(glyph, "value", 0)) == 0
        if not empty_zero:
            painter.setPen(self._pen(color, 1.15, dotted=True))
            painter.drawLine(QPointF(cx, y + 3), QPointF(cx, y + size - 3))
            painter.drawLine(QPointF(x + 3, cy), QPointF(x + size - 3, cy))
            painter.setPen(self._pen(color, 1.75))
            painter.drawEllipse(QRectF(cx-size*.055, cy-size*.055, size*.11, size*.11))

        groups = [
            [(0.28,0.27,0.28,0.42),(0.37,0.27,0.37,0.42),(0.46,0.27,0.46,0.42)],
            [(0.61,0.27,0.61,0.42),(0.70,0.27,0.70,0.42),(0.79,0.27,0.79,0.42)],
            [(0.28,0.60,0.28,0.79),(0.37,0.60,0.37,0.79),(0.46,0.60,0.46,0.79)],
            [(0.61,0.62,0.79,0.62),(0.61,0.70,0.79,0.70),(0.61,0.78,0.79,0.78)],
        ]
        mask = int(getattr(glyph, "separator_mask", 0))
        if not empty_zero:
            for q, strokes in enumerate(groups):
                if not (mask & (1 << q)):
                    continue
                for j, (ax, ay, bx, by) in enumerate(strokes):
                    i = q * 3 + j
                    if not (int(getattr(glyph, "presence_mask", 0)) & (1 << i)):
                        continue
                    x1, y1 = x + size*ax, y + size*ay
                    x2, y2 = x + size*bx, y + size*by
                    self._draw_stroke(
                        painter, x1, y1, x2-x1, y2-y1,
                        bool(int(getattr(glyph, "squiggly_mask", 0)) & (1 << i)), color,
                    )

        operation = getattr(glyph, "operation", OTOperation.NONE)
        if operation == OTOperation.MUL:
            painter.setPen(self._pen(color, 1.4))
            painter.drawLine(QPointF(x,y), QPointF(x+size*.72,y))
            painter.drawLine(QPointF(x,y), QPointF(x,y+size))
            painter.drawLine(QPointF(x,y+size), QPointF(x+size*.72,y+size))
        elif operation in (OTOperation.ADD, OTOperation.SUB):
            painter.setPen(self._pen(color, 1.3, dotted=True))
            painter.drawRect(QRectF(x-1,y-1,size+2,size+2))
        elif operation == OTOperation.DIV:
            painter.setPen(self._pen(color, 1.6))
            painter.drawRect(QRectF(x-1,y-1,size+2,size+2))
        if bool(getattr(glyph, "continued", False)):
            painter.setPen(self._pen(color, 1.0, dotted=True))
            painter.drawRect(QRectF(x-3,y-3,size+6,size+6))
        variable_letter = str(getattr(glyph, "variable_letter", "") or "")
        if variable_letter:
            painter.setPen(self._pen(color, 1.1))
            painter.setFont(QFont("Sans Serif", max(6, int(size*.15)), QFont.Weight.Bold))
            painter.drawText(QRectF(x+2,y+2,size*.22,size*.20), Qt.AlignmentFlag.AlignCenter, variable_letter[:1])
        if int(getattr(glyph, "multiplicity", 1) or 1) > 1:
            painter.setPen(self._pen(color, 1.2))
            painter.drawRect(QRectF(x+size*.82,y+size*.05,size*.12,size*.12))

    def _draw_full_cycle(self, painter, x, y, size, color, operation, continued, multiplicity, variable_letter):
        """Distinct Groovebox rendering convention for semantic cell 16.

        0..15 exhaust the four separator states, so cell 16 cannot be encoded as
        another nibble.  The full-cycle face deliberately shows the completed
        outer cycle plus an inner cycle ring.  Its *numeric* meaning comes from
        author_number_codec, not from the drawing convention.
        """
        if color == "#000000":
            painter.fillRect(QRectF(x, y, size, size), QColor("#b8b8b8"))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(self._pen(color, 2.7))
        painter.drawRect(QRectF(x+1.5, y+1.5, size-3, size-3))
        inset = size * .20
        painter.setPen(self._pen(color, 1.8))
        painter.drawRoundedRect(QRectF(x+inset, y+inset, size-2*inset, size-2*inset), size*.10, size*.10)
        cx, cy = x+size*.5, y+size*.5
        painter.drawEllipse(QRectF(cx-size*.075, cy-size*.075, size*.15, size*.15))
        # Four completed-quarter ticks make this visually different from 0 and F.
        q0, q1 = size*.08, size*.22
        painter.drawLine(QPointF(cx, y+q0), QPointF(cx, y+q1))
        painter.drawLine(QPointF(x+size-q0, cy), QPointF(x+size-q1, cy))
        painter.drawLine(QPointF(cx, y+size-q0), QPointF(cx, y+size-q1))
        painter.drawLine(QPointF(x+q0, cy), QPointF(x+q1, cy))
        if operation == OTOperation.MUL:
            painter.setPen(self._pen(color, 1.4)); painter.drawRect(QRectF(x-1,y-1,size+2,size+2))
        elif operation in (OTOperation.ADD, OTOperation.SUB):
            painter.setPen(self._pen(color, 1.3, dotted=True)); painter.drawRect(QRectF(x-1,y-1,size+2,size+2))
        elif operation == OTOperation.DIV:
            painter.setPen(self._pen(color, 1.7)); painter.drawRect(QRectF(x-2,y-2,size+4,size+4))
        if continued:
            painter.setPen(self._pen(color, 1.0, dotted=True)); painter.drawRect(QRectF(x-3,y-3,size+6,size+6))
        if variable_letter:
            painter.setFont(QFont("Sans Serif", max(6,int(size*.15)), QFont.Weight.Bold))
            painter.drawText(QRectF(x+2,y+2,size*.22,size*.20), Qt.AlignmentFlag.AlignCenter, str(variable_letter)[:1])
        if int(multiplicity) > 1:
            painter.drawRect(QRectF(x+size*.82,y+size*.05,size*.12,size*.12))

    def _face_pixmap(
        self, variant: GlyphVariant, *, role, operation, continued, multiplicity,
        variable_letter, size: float, direction_index: int, negative: bool, dpr: float,
    ) -> QPixmap:
        size_px = max(12, int(round(size)))
        key = (
            variant.variant_index, _role_key(role), _operation_key(operation), bool(continued),
            int(multiplicity), str(variable_letter)[:1], size_px, int(direction_index)&1,
            bool(negative), round(float(dpr),3),
        )
        cached = self._face_cache.get(key)
        if cached is not None:
            self._stats["face_hits"] += 1
            self._face_cache.move_to_end(key)
            return QPixmap(cached)
        self._stats["face_misses"] += 1
        pix = QPixmap(max(1,int(round(size_px*dpr))), max(1,int(round(size_px*dpr))))
        pix.setDevicePixelRatio(dpr)
        pix.fill(QColor(0,0,0,0))
        p = QPainter(pix); p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = _role_color(role)
        if variant.value == FULL_CYCLE_VALUE:
            self._draw_full_cycle(p, 0, 0, size_px, color, operation, continued, multiplicity, variable_letter)
        else:
            direction = ot_direction_for(-1.0 if negative else 1.0, int(direction_index))
            glyph = ot_encode_nibble(
                int(variant.value), direction=direction, operation=operation,
                continued=continued, multiplicity=multiplicity, role=role,
                variable_letter=str(variable_letter)[:1],
            )
            self._draw_glyph(p, glyph, 0, 0, size_px)
        if variant.squiggle:
            self._draw_incell_squiggle(p, 0, 0, size_px, color)
        p.end()
        self._face_cache[key] = QPixmap(pix); self._face_cache.move_to_end(key)
        while len(self._face_cache) > self.face_cache_limit:
            self._face_cache.popitem(last=False)
        return pix

    def render_number(
        self,
        text: str,
        role=OTRole.RESULT,
        width: int = 140,
        height: int = 42,
        *,
        background=None,
        operation=OTOperation.NONE,
        continued: bool = False,
        multiplicity: int = 1,
        variable_letter: str = "",
        preferred_cell: float = PREFERRED_CELL_PX,
        device_pixel_ratio: float = 1.0,
        spelling: Optional[NumberSpelling] = None,
    ) -> QPixmap:
        spelling = spelling or self.spell(text)
        width = max(1, int(width)); height = max(1, int(height))
        bg = QColor(background) if background is not None else QColor(0,0,0,0)
        dpr = max(1.0, float(device_pixel_ratio or 1.0))
        key = (
            spelling.packet_key, _role_key(role), width, height, bg.rgba(),
            _operation_key(operation), bool(continued), int(multiplicity), str(variable_letter)[:1],
            round(float(preferred_cell),3), round(dpr,3),
        )
        cached = self._cache.get(key)
        if cached is not None:
            self._stats["number_hits"] += 1
            self._cache.move_to_end(key)
            return QPixmap(cached)
        self._stats["number_misses"] += 1

        variants = spelling.all_variants()
        frac_start = len(spelling.integer_values)
        n = max(1, len(variants))
        integer_gutter = 2.0
        # Spacing is semantic in fractional slots.  Full/spaced automatic cells
        # receive a visible gap; explicitly-authored unspaced half-slots tuck in.
        gaps = []
        for i in range(1, n):
            if i >= frac_start:
                v = variants[i]
                gaps.append(max(2.0, preferred_cell*.12) if v.spaced else max(0.5, preferred_cell*.025))
            else:
                gaps.append(integer_gutter)
        gap_total = sum(gaps)
        max_by_width = (max(10.0,float(width)-4.0)-gap_total) / (n+0.5)
        max_by_height = max(12.0,float(height)-2.0)
        cell = max(12.0,min(float(preferred_cell),max_by_width,max_by_height))
        # Recompute semantic gaps from fitted cell.
        gaps=[]
        for i in range(1,n):
            if i >= frac_start:
                v=variants[i]; gaps.append(max(2.0,cell*.12) if v.spaced else max(0.5,cell*.025))
            else: gaps.append(integer_gutter)
        total = n*cell + sum(gaps)
        motion_margin = cell*.25
        x = max(1.0+motion_margin,(width-total)/2.0)
        y = max(motion_margin,(height-cell)/2.0)

        pix = QPixmap(max(1,int(round(width*dpr))),max(1,int(round(height*dpr))))
        pix.setDevicePixelRatio(dpr); pix.fill(bg)
        p=QPainter(pix); p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for i, variant in enumerate(variants):
            dx,dy,_inward,_phase = quarter_cycle_state(i,negative=spelling.negative,cell=cell)
            face = self._face_pixmap(
                variant, role=role, operation=operation, continued=continued,
                multiplicity=multiplicity, variable_letter=(variable_letter if i==0 else ""),
                size=cell, direction_index=i, negative=spelling.negative, dpr=dpr,
            )
            p.drawPixmap(QPointF(x+dx,y+dy),face)
            if i+1 < n:
                x += cell + gaps[i]
        p.end()
        self._cache[key]=QPixmap(pix); self._cache.move_to_end(key)
        while len(self._cache)>self.cache_limit:
            self._cache.popitem(last=False)
        return pix

    def project_manifest(self) -> dict:
        out = scheme_manifest()
        out.update({
            "font": "cached-code-glyph-atlas-v4",
            "face_cache": True,
            "number_cache": True,
            "sCode_symbol_pool": self._optimizer is not None,
            "precomputed_faces": PRECOMPUTED_VARIANT_COUNT,
        })
        return out


AUTHOR_NUMERIC_FONT = AuthorNumericFontLibrary()


class AuthorNumericFieldAdapter(QLabel):
    """Stable, rewritable, dirty-gated presentation for a numeric Qt field."""

    def __init__(self, owner, *, role_provider: Optional[Callable]=None,
                 enabled_provider: Optional[Callable[[],bool]]=None,
                 font_library: AuthorNumericFontLibrary=AUTHOR_NUMERIC_FONT):
        self.owner=owner
        self._editor=owner.lineEdit() if hasattr(owner,"lineEdit") else None
        super().__init__(self._editor if self._editor is not None else owner)
        self._font_library=font_library; self._role_provider=role_provider; self._enabled_provider=enabled_provider
        self._role=OTRole.RESULT; self._operation=OTOperation.NONE; self._continued=False
        self._multiplicity=1; self._variable_letter=""; self._override_text=None
        self._last_source_key=None; self._last_render_key=None; self._spelling=None; self._packet_override=None; self._syncing=False
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus); self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setScaledContents(False); self.setMargin(0); self.setStyleSheet("border:none;padding:0;margin:0;")
        try:
            owner.installEventFilter(self); owner.valueChanged.connect(self._value_changed); owner.destroyed.connect(self.deleteLater)
        except Exception: pass
        if self._editor is not None:
            try: self._editor.installEventFilter(self)
            except Exception: pass
        self._sync(force=True)

    def _enabled(self):
        try: return bool(self._enabled_provider()) if self._enabled_provider else True
        except Exception: return True

    def _is_editing(self):
        try: return bool((self._editor is not None and self._editor.hasFocus()) or self.owner.hasFocus())
        except Exception: return False

    def _display_numeric_text(self):
        if self._override_text is not None:
            return normalize_numeric_text(self._override_text)
        try:
            txt=str(self.owner.cleanText())
            try:
                dec=str(self.owner.locale().decimalPoint())
                if dec and dec != ".": txt=txt.replace(dec,".")
            except Exception: pass
            return normalize_numeric_text(txt)
        except Exception:
            try:
                if isinstance(self.owner,QDoubleSpinBox):
                    return f"{float(self.owner.value()):.{max(0,int(self.owner.decimals()))}f}"
                return str(int(self.owner.value()))
            except Exception: return "0"

    def setNotation(self,operation=None,continued=None,multiplicity=None,variable_letter=None):
        changed=False
        if operation is not None and operation != self._operation: self._operation=operation; changed=True
        if continued is not None and bool(continued) != self._continued: self._continued=bool(continued); changed=True
        if multiplicity is not None and max(1,int(multiplicity)) != self._multiplicity: self._multiplicity=max(1,int(multiplicity)); changed=True
        if variable_letter is not None and str(variable_letter)[:1] != self._variable_letter: self._variable_letter=str(variable_letter)[:1]; changed=True
        if changed: self._sync(force=True)

    def rewrite(self,text=None,role=None,*,operation=None,continued=None,multiplicity=None,variable_letter=None):
        """Rewrite only this field's symbol presentation; never its real value."""
        new_override=None if text is None else str(text)
        changed=(new_override != self._override_text) or self._packet_override is not None
        self._packet_override=None
        self._override_text=new_override
        if role is not None and role != self._role: self._role=role; changed=True
        # Avoid nested forced syncs; apply notation directly.
        if operation is not None and operation != self._operation: self._operation=operation; changed=True
        if continued is not None and bool(continued) != self._continued: self._continued=bool(continued); changed=True
        if multiplicity is not None and max(1,int(multiplicity)) != self._multiplicity: self._multiplicity=max(1,int(multiplicity)); changed=True
        if variable_letter is not None and str(variable_letter)[:1] != self._variable_letter: self._variable_letter=str(variable_letter)[:1]; changed=True
        if changed: self._last_source_key=None; self._sync(force=False)

    def rewriteSpelling(self, spelling: NumberSpelling, role=None):
        """Use an explicit immutable spelling packet for this one field.

        This is the authored path for spacing-sensitive fractional cells. It never
        writes the QSpinBox/QDoubleSpinBox's numeric value.
        """
        if not isinstance(spelling, NumberSpelling):
            raise TypeError("rewriteSpelling expects NumberSpelling")
        self._packet_override=spelling
        self._override_text=spelling.source_text
        self._spelling=spelling
        self._last_source_key=("packet", spelling.packet_key)
        if role is not None: self._role=role
        self._last_render_key=None
        self._sync(force=False)

    def setFractionSpacing(self, slot: int, spaced: bool):
        """Rewrite one existing fractional slot as spaced 1/1 or unspaced 1/2."""
        packet=self._packet_override or self._spelling or self._font_library.spell(self._display_numeric_text())
        self.rewriteSpelling(set_fraction_spacing(packet, int(slot), bool(spaced)))

    def _value_changed(self,*_):
        self._packet_override=None; self._override_text=None; self._last_source_key=None; self._sync(force=False)

    def _set_owner_number_text_visible(self,visible):
        if bool(visible): self.hide()
        else: self._sync(force=False)

    def _fit(self):
        try:
            target=self._editor.rect() if self._editor is not None else self.owner.rect()
            if self.geometry()!=target: self.setGeometry(target)
        except Exception: pass

    def _sync(self,force=False):
        if self._syncing: return
        self._syncing=True
        try:
            self._fit()
            show=bool(self._enabled() and not self._is_editing())
            if not show: self.hide(); return
            text=self._display_numeric_text()
            try: role=self._role_provider(self.owner,text) if self._role_provider else self._role
            except Exception: role=self._role
            self._role=role
            if self._packet_override is not None:
                source_key=("packet", self._packet_override.packet_key)
                self._spelling=self._packet_override
                self._last_source_key=source_key
            else:
                source_key=(text,AUTHOR_NUMBER_SCHEME)
                # This is the main semantic dirty gate: unchanged values do not even
                # enter the formatter/codec again.
                if self._spelling is None or source_key != self._last_source_key:
                    self._last_source_key=source_key
                    self._spelling=self._font_library.spell(text)
            try: bg=self._editor.palette().color(QPalette.ColorRole.Base) if self._editor is not None else self.owner.palette().color(QPalette.ColorRole.Base)
            except Exception: bg=QColor("#27272a")
            try: dpr=self.devicePixelRatioF()
            except Exception: dpr=1.0
            key=(self._spelling.packet_key,_role_key(role),self.width(),self.height(),bg.rgba(),_operation_key(self._operation),self._continued,self._multiplicity,self._variable_letter,round(float(dpr),3))
            if force or key != self._last_render_key:
                self._last_render_key=key
                self.setPixmap(self._font_library.render_number(
                    text,role=role,width=max(1,self.width()),height=max(1,self.height()),background=bg,
                    operation=self._operation,continued=self._continued,multiplicity=self._multiplicity,
                    variable_letter=self._variable_letter,preferred_cell=PREFERRED_CELL_PX,
                    device_pixel_ratio=dpr,spelling=self._spelling,
                ))
            self.show(); self.raise_()
        finally: self._syncing=False

    def eventFilter(self,obj,event):
        t=event.type()
        if t in (QEvent.Type.Resize,QEvent.Type.Show,QEvent.Type.FontChange,QEvent.Type.PaletteChange):
            # Geometry/palette can change the pixmap, but never invalidate the
            # semantic spelling packet.
            self._sync(force=True)
        elif t==QEvent.Type.FocusIn: self.hide()
        elif t==QEvent.Type.FocusOut: self._sync(force=False)
        return False
