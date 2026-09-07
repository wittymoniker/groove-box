"""Reversible author-number spelling for Mathematician's Groovebox.

The display grammar is base-16-first but is not a conventional hexadecimal font:

* 0..15 are ordinary base-16 count cells.
* 16 is a dedicated completed-cycle/full-cycle cell (a compact spelling of an
  integer magnitude of sixteen rather than a positional hex digit).
* A squiggle on the least-significant integer cell can carry the first
  fractional half-step, 2^-1, without allocating another cell.
* Extra fractional cells follow after that squiggle/no-squiggle decision and
  are weighted 16^-k = 2^(-4k), k=1,2,... .
* In an authored fractional slot a spaced straight/count is the full 1/1 slot
  value; an unspaced straight/count is 1/2 of that same slot value.
* Automatic Groovebox spelling uses spaced/full fractional cells so ordinary
  numeric values round-trip to the field's visible precision.  Unspaced half-
  slot cells remain available for explicitly authored notation.

This module is intentionally Qt-free.  It is the semantic boundary shared by
rendering, project/provenance metadata, scripting helpers and sCode parity
checks.  The numeric value is never replaced by the display approximation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
from functools import lru_cache
from typing import Iterable, Sequence, Tuple
import re

SCHEME = "base16-squiggle-crossbar-subscale-v7"
BASE = 16
FULL_CYCLE_VALUE = 16
HALF_WEIGHT = Decimal(1) / Decimal(2)
SUBSCALE_BITS = 4
MAX_SUBSCALE_CELLS = 16

# Divider semantics are part of the numeric face contract, not decoration.
DIVIDER_FULL_VALUE = Decimal(1)
DIVIDER_DOTTED_VALUE = Decimal(1) / Decimal(2)
FULL_CYCLE_DIVIDER_COUNT = 4
FULL_CYCLE_MAIN_STROKE_COUNT = 12
FULL_CYCLE_MAIN_STROKE_SOLID_COUNT = 12
FULL_CYCLE_SOLID_MASK = 0b1111
FULL_CYCLE_DOTTED_MASK = 0

_NUMERIC_RE = re.compile(r"^[+-]?(?:\d+(?:[\.,]\d*)?|[\.,]\d+)(?:[eE][+-]?\d+)?$")


@dataclass(frozen=True, slots=True)
class GlyphVariant:
    """Interned semantic face for one 0..16 symbol cell.

    Every cell owns four ordered cross-bar positions.  Each position is encoded
    by two disjoint masks: absent=0, dotted=0.5, solid=1.  Automatic 0..15
    spellings use absent bars; automatic 16/full-cycle uses four solid bars.
    """
    value: int
    squiggle: bool = False
    spaced: bool = True
    solid_mask: int = 0
    dotted_mask: int = 0

    def __post_init__(self):
        sm, dm = int(self.solid_mask), int(self.dotted_mask)
        if not (0 <= sm <= 15 and 0 <= dm <= 15):
            raise ValueError("cross-bar masks must be 0..15")
        if sm & dm:
            raise ValueError("solid and dotted cross-bar masks may not overlap")

    @property
    def full_cycle(self) -> bool:
        return int(self.value) == FULL_CYCLE_VALUE

    @property
    def crossbar_variant_index(self) -> int:
        idx = 0
        factor = 1
        for position in range(4):
            bit = 1 << position
            state = 2 if (int(self.solid_mask) & bit) else (1 if (int(self.dotted_mask) & bit) else 0)
            idx += state * factor
            factor *= 3
        return idx

    @property
    def variant_index(self) -> int:
        # Values 0..15 each admit 81 cross-bar states. Cell 16 is invariant:
        # all 12 main strokes solid and all four subdividers solid, so it has
        # only the four squiggle/spacing presentation variants.
        q = (2 if self.squiggle else 0) + (1 if self.spaced else 0)
        if int(self.value) == FULL_CYCLE_VALUE:
            return 16 * 324 + q
        return int(self.value) * 324 + self.crossbar_variant_index * 4 + q

    def crossbar_state(self, position: int) -> int:
        bit = 1 << int(position)
        if int(self.solid_mask) & bit:
            return 2
        if int(self.dotted_mask) & bit:
            return 1
        return 0

    def crossbar_value(self, position: int) -> Decimal:
        state = self.crossbar_state(position)
        return DIVIDER_FULL_VALUE if state == 2 else (DIVIDER_DOTTED_VALUE if state == 1 else Decimal(0))


def _default_crossbar_masks(value: int) -> tuple[int, int]:
    return (FULL_CYCLE_SOLID_MASK, FULL_CYCLE_DOTTED_MASK) if int(value) == FULL_CYCLE_VALUE else (0, 0)


def _valid_crossbar_masks():
    for solid_mask in range(16):
        for dotted_mask in range(16):
            if not (solid_mask & dotted_mask):
                yield solid_mask, dotted_mask


# Precompute all semantically legal faces once. Values 0..15 admit the full
# 3^4 cross-bar state space; semantic 16/full-cycle is invariant at 12 solid
# main strokes + four solid subdividers. Count: (16*81 + 1) * 2 * 2 = 5188.
GLYPH_VARIANTS = {
    (value, squiggle, spaced, solid_mask, dotted_mask): GlyphVariant(
        value, squiggle, spaced, solid_mask, dotted_mask
    )
    for value in range(FULL_CYCLE_VALUE + 1)
    for squiggle in (False, True)
    for spaced in (False, True)
    for solid_mask, dotted_mask in _valid_crossbar_masks()
    if value != FULL_CYCLE_VALUE or (solid_mask == FULL_CYCLE_SOLID_MASK and dotted_mask == FULL_CYCLE_DOTTED_MASK)
}
PRECOMPUTED_VARIANT_COUNT = len(GLYPH_VARIANTS)


def glyph_variant(
    value: int, squiggle: bool = False, spaced: bool = True,
    solid_mask: int | None = None, dotted_mask: int | None = None,
) -> GlyphVariant:
    iv = int(value)
    if not 0 <= iv <= FULL_CYCLE_VALUE:
        raise ValueError("author symbol cell must be 0..16")
    dsm, ddm = _default_crossbar_masks(iv)
    sm = dsm if solid_mask is None else int(solid_mask)
    dm = ddm if dotted_mask is None else int(dotted_mask)
    if not (0 <= sm <= 15 and 0 <= dm <= 15) or (sm & dm):
        raise ValueError("cross-bar masks must be disjoint 4-bit masks")
    if iv == FULL_CYCLE_VALUE and (sm != FULL_CYCLE_SOLID_MASK or dm != FULL_CYCLE_DOTTED_MASK):
        raise ValueError("cell 16 is invariant: 12 solid main strokes and four solid subdividers")
    return GLYPH_VARIANTS[(iv, bool(squiggle), bool(spaced), sm, dm)]


@dataclass(frozen=True, slots=True)
class FractionCell:
    """One post-squiggle subscale cell."""
    variant: GlyphVariant
    slot: int  # 1 => 2^-4, 2 => 2^-8, ...

    def __post_init__(self):
        if int(self.slot) < 1:
            raise ValueError("fractional slot must be >= 1")
        if self.variant.full_cycle:
            raise ValueError("16/full-cycle is not a positional fractional digit")

    @property
    def exponent(self) -> int:
        return SUBSCALE_BITS * int(self.slot)

    @property
    def weight(self) -> Decimal:
        base = Decimal(2) ** Decimal(-self.exponent)
        return base if self.variant.spaced else base * HALF_WEIGHT

    @property
    def contribution(self) -> Decimal:
        return Decimal(self.variant.value) * self.weight


@dataclass(frozen=True, slots=True)
class NumberSpelling:
    """Immutable display packet for one numeric value."""
    source_text: str
    negative: bool
    integer_values: Tuple[int, ...]
    half_squiggle: bool
    fractional_cells: Tuple[FractionCell, ...]
    visible_decimal_places: int
    represented: Decimal
    error: Decimal
    exact: bool
    integer_crossbars: Tuple[Tuple[int, int], ...] = ()
    scheme: str = SCHEME

    @property
    def packet_key(self) -> tuple:
        return (
            self.scheme,
            int(self.negative),
            tuple(int(v) for v in self.integer_values),
            tuple((int(sm), int(dm)) for sm, dm in self.integer_crossbars),
            int(self.half_squiggle),
            tuple((c.variant.value, int(c.variant.spaced), int(c.variant.squiggle),
                   int(c.variant.solid_mask), int(c.variant.dotted_mask), c.slot) for c in self.fractional_cells),
            int(self.visible_decimal_places),
        )

    @property
    def cell_count(self) -> int:
        return len(self.integer_values) + len(self.fractional_cells)

    @property
    def fractional_cell_count(self) -> int:
        return len(self.fractional_cells)

    def integer_variants(self) -> Tuple[GlyphVariant, ...]:
        out = []
        last = len(self.integer_values) - 1
        for i, value in enumerate(self.integer_values):
            if i < len(self.integer_crossbars):
                solid_mask, dotted_mask = self.integer_crossbars[i]
            else:
                solid_mask, dotted_mask = _default_crossbar_masks(value)
            out.append(glyph_variant(
                value, squiggle=(self.half_squiggle and i == last), spaced=True,
                solid_mask=solid_mask, dotted_mask=dotted_mask,
            ))
        return tuple(out)

    def all_variants(self) -> Tuple[GlyphVariant, ...]:
        return self.integer_variants() + tuple(c.variant for c in self.fractional_cells)

    def to_dict(self) -> dict:
        return {
            "scheme": self.scheme,
            "source_text": self.source_text,
            "negative": self.negative,
            "integer_cells": list(self.integer_values),
            "integer_crossbars": [
                {"solid_mask": int(sm), "dotted_mask": int(dm)}
                for sm, dm in (self.integer_crossbars or tuple(_default_crossbar_masks(v) for v in self.integer_values))
            ],
            "half_squiggle": self.half_squiggle,
            "fractional_cells": [
                {
                    "value": c.variant.value,
                    "slot": c.slot,
                    "spaced": c.variant.spaced,
                    "squiggle": c.variant.squiggle,
                    "solid_mask": int(c.variant.solid_mask),
                    "dotted_mask": int(c.variant.dotted_mask),
                    "crossbars": [float(c.variant.crossbar_value(i)) for i in range(4)],
                    "subscale_exponent": c.exponent,
                }
                for c in self.fractional_cells
            ],
            "visible_decimal_places": self.visible_decimal_places,
            "represented": str(self.represented),
            "error": str(self.error),
            "exact": self.exact,
        }


def normalize_numeric_text(text) -> str:
    raw = str(text if text is not None else "").strip().replace("\u2212", "-")
    if not raw:
        return "0"
    # UI prefixes/suffixes should normally be removed by QAbstractSpinBox.cleanText;
    # still accept surrounding whitespace and a locale comma decimal separator.
    candidate = raw.replace(",", ".")
    if _NUMERIC_RE.match(candidate):
        return candidate
    # Conservative salvage for rewrite()/legacy callers: retain one sign, digits,
    # one radix and an optional exponent.  If that still cannot parse, use zero.
    m = re.search(r"[+-]?(?:\d+(?:[\.,]\d*)?|[\.,]\d+)(?:[eE][+-]?\d+)?", raw)
    if m:
        candidate = m.group(0).replace(",", ".")
        if _NUMERIC_RE.match(candidate):
            return candidate
    return "0"


def _visible_decimal_places(text: str) -> int:
    s = normalize_numeric_text(text)
    mantissa = re.split(r"[eE]", s, maxsplit=1)[0]
    if "." not in mantissa:
        return 0
    return max(0, len(mantissa.split(".", 1)[1]))


def _source_decimal(text: str) -> Decimal:
    s = normalize_numeric_text(text)
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal(0)


def _integer_cells(integer_part: int) -> Tuple[int, ...]:
    n = max(0, int(integer_part))
    if n == FULL_CYCLE_VALUE:
        return (FULL_CYCLE_VALUE,)
    if n == 0:
        return (0,)
    digits = []
    while n:
        digits.append(n % BASE)
        n //= BASE
    return tuple(reversed(digits))


def _integer_value(cells: Sequence[int]) -> Decimal:
    vals = tuple(int(v) for v in cells)
    if vals == (FULL_CYCLE_VALUE,):
        return Decimal(FULL_CYCLE_VALUE)
    total = 0
    for value in vals:
        if not 0 <= value < BASE:
            raise ValueError("16/full-cycle may only be used as the sole compact integer cell")
        total = total * BASE + value
    return Decimal(total)


def subscale_exponent(slot: int) -> int:
    return SUBSCALE_BITS * max(1, int(slot))


def subscale_weight(slot: int, spaced: bool = True) -> Decimal:
    exp = subscale_exponent(slot)
    with localcontext() as ctx:
        ctx.prec = 80
        w = Decimal(2) ** Decimal(-exp)
        return w if bool(spaced) else w * HALF_WEIGHT


def fractional_cell_value(value: int, slot: int, spaced: bool = True) -> Decimal:
    iv = int(value)
    if not 0 <= iv < BASE:
        raise ValueError("fractional cell value must be 0..15")
    return Decimal(iv) * subscale_weight(slot, spaced=spaced)


def decode_spelling(spelling: NumberSpelling) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 100
        total = _integer_value(spelling.integer_values)
        if spelling.half_squiggle:
            total += HALF_WEIGHT
        for cell in spelling.fractional_cells:
            total += cell.contribution
        return -total if spelling.negative and total != 0 else total


def decode_authored(
    integer_values: Sequence[int],
    *,
    half_squiggle: bool = False,
    fractional_cells: Iterable[tuple[int, bool]] = (),
    negative: bool = False,
) -> Decimal:
    """Decode explicit authored cells.

    fractional_cells is an iterable of ``(value, spaced)`` pairs.  The first pair
    occupies slot 1 (2^-4), the next slot 2 (2^-8), and so on.  ``spaced=False``
    applies the user's half-slot 1/2 interpretation to that position.
    """
    with localcontext() as ctx:
        ctx.prec = 100
        total = _integer_value(integer_values)
        if half_squiggle:
            total += HALF_WEIGHT
        for slot, pair in enumerate(fractional_cells, start=1):
            value, spaced = pair
            total += fractional_cell_value(int(value), slot, bool(spaced))
        return -total if negative and total != 0 else total


def _tolerance_for_text(text: str) -> Decimal:
    places = _visible_decimal_places(text)
    if places <= 0:
        return Decimal(0)
    # One half of the least visible base-10 unit.  This allows the glyph spelling
    # to be as short as possible without changing the displayed numeric value.
    return (Decimal(10) ** Decimal(-places)) * HALF_WEIGHT


def _fraction_digits(residual: Decimal, tolerance: Decimal, max_cells: int) -> tuple[Tuple[int, ...], Decimal]:
    if residual == 0:
        return (), Decimal(0)
    with localcontext() as ctx:
        ctx.prec = 120
        max_cells = max(1, min(int(max_cells), MAX_SUBSCALE_CELLS))
        for cells in range(1, max_cells + 1):
            scale = Decimal(BASE) ** cells
            units = (residual * scale).to_integral_value(rounding=ROUND_HALF_EVEN)
            approx = units / scale
            err = abs(approx - residual)
            if err <= tolerance:
                iv = int(units)
                # Clamp a rare rounded carry into the legal residual range.  The
                # half-squiggle decision was already made before this stage.
                iv = max(0, min(iv, (BASE ** cells) - 1))
                digits = [0] * cells
                q = iv
                for i in range(cells - 1, -1, -1):
                    digits[i] = q % BASE
                    q //= BASE
                return tuple(digits), approx
        cells = max_cells
        scale = Decimal(BASE) ** cells
        units = (residual * scale).to_integral_value(rounding=ROUND_HALF_EVEN)
        iv = max(0, min(int(units), (BASE ** cells) - 1))
        digits = [0] * cells
        q = iv
        for i in range(cells - 1, -1, -1):
            digits[i] = q % BASE
            q //= BASE
        return tuple(digits), Decimal(iv) / scale


@lru_cache(maxsize=8192)
def _spell_cached(normalized_text: str, max_cells: int) -> NumberSpelling:
    source = _source_decimal(normalized_text)
    negative = source < 0
    magnitude = abs(source)
    integer_part = int(magnitude)  # Decimal->int truncates toward zero; magnitude >=0
    fraction = magnitude - Decimal(integer_part)
    places = _visible_decimal_places(normalized_text)
    tolerance = _tolerance_for_text(normalized_text)

    # First fractional binary subdivision lives in the integer cell itself.
    half_squiggle = fraction >= HALF_WEIGHT
    residual = fraction - HALF_WEIGHT if half_squiggle else fraction

    digits, _approx_residual = _fraction_digits(residual, tolerance, max_cells)
    frac_cells = tuple(
        FractionCell(glyph_variant(d, squiggle=False, spaced=True), slot)
        for slot, d in enumerate(digits, start=1)
    )
    packet0 = NumberSpelling(
        source_text=normalized_text,
        negative=negative,
        integer_values=_integer_cells(integer_part),
        half_squiggle=bool(half_squiggle),
        fractional_cells=frac_cells,
        visible_decimal_places=places,
        represented=Decimal(0),
        error=Decimal(0),
        exact=False,
    )
    represented = decode_spelling(packet0)
    error = abs(represented - source)
    return replace(packet0, represented=represented, error=error, exact=(represented == source))


def spell_number(text, *, max_subscale_cells: int = MAX_SUBSCALE_CELLS) -> NumberSpelling:
    """Return the shortest automatic spelling that preserves visible precision."""
    normalized = normalize_numeric_text(text)
    return _spell_cached(normalized, max(1, min(int(max_subscale_cells), MAX_SUBSCALE_CELLS)))


def set_fraction_spacing(spelling: NumberSpelling, slot: int, spaced: bool) -> NumberSpelling:
    """Return a new explicit-authored packet with one slot's spacing changed."""
    target = int(slot)
    cells = []
    found = False
    for cell in spelling.fractional_cells:
        if cell.slot == target:
            found = True
            cells.append(FractionCell(glyph_variant(cell.variant.value, cell.variant.squiggle, bool(spaced), cell.variant.solid_mask, cell.variant.dotted_mask), cell.slot))
        else:
            cells.append(cell)
    if not found:
        raise IndexError("fractional slot is not present in this spelling")
    provisional = replace(spelling, fractional_cells=tuple(cells), exact=False)
    represented = decode_spelling(provisional)
    source = _source_decimal(spelling.source_text)
    return replace(provisional, represented=represented, error=abs(represented-source), exact=(represented==source))


def set_integer_crossbars(spelling: NumberSpelling, cell_index: int, *, solid_mask: int, dotted_mask: int) -> NumberSpelling:
    """Rewrite one integer cell's four ordered cross-bar states."""
    idx = int(cell_index)
    if idx < 0:
        idx += len(spelling.integer_values)
    if idx < 0 or idx >= len(spelling.integer_values):
        raise IndexError("integer cell index out of range")
    sm, dm = int(solid_mask), int(dotted_mask)
    # Validate using the interned face constructor.
    glyph_variant(spelling.integer_values[idx], False, True, sm, dm)
    bars = list(spelling.integer_crossbars or tuple(_default_crossbar_masks(v) for v in spelling.integer_values))
    bars[idx] = (sm, dm)
    return replace(spelling, integer_crossbars=tuple(bars))


def set_cell_crossbars(variant: GlyphVariant, *, solid_mask: int, dotted_mask: int) -> GlyphVariant:
    """Return the same 0..16/squiggle/spacing face with explicit cross-bars."""
    return glyph_variant(variant.value, variant.squiggle, variant.spaced, solid_mask, dotted_mask)


def crossbar_values(variant: GlyphVariant) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
    return tuple(variant.crossbar_value(i) for i in range(4))


def spelling_from_dict(data: dict) -> NumberSpelling:
    """Reconstruct an explicit spelling packet from project/provenance metadata."""
    if not isinstance(data, dict):
        raise TypeError("spelling metadata must be a dict")
    source_text = normalize_numeric_text(data.get("source_text", "0"))
    integer_values = tuple(int(v) for v in (data.get("integer_cells") or [0]))
    bars_data = data.get("integer_crossbars") or []
    integer_crossbars = []
    for i, value in enumerate(integer_values):
        if i < len(bars_data) and isinstance(bars_data[i], dict):
            sm = int(bars_data[i].get("solid_mask", _default_crossbar_masks(value)[0]))
            dm = int(bars_data[i].get("dotted_mask", _default_crossbar_masks(value)[1]))
        else:
            sm, dm = _default_crossbar_masks(value)
        glyph_variant(value, False, True, sm, dm)
        integer_crossbars.append((sm, dm))
    cells = []
    for rec in (data.get("fractional_cells") or []):
        if not isinstance(rec, dict):
            continue
        slot = int(rec.get("slot", len(cells) + 1))
        value = int(rec.get("value", 0))
        spaced = bool(rec.get("spaced", True))
        squiggle = bool(rec.get("squiggle", False))
        solid_mask = int(rec.get("solid_mask", 0))
        dotted_mask = int(rec.get("dotted_mask", 0))
        cells.append(FractionCell(glyph_variant(value, squiggle=squiggle, spaced=spaced,
                                                solid_mask=solid_mask, dotted_mask=dotted_mask), slot))
    provisional = NumberSpelling(
        source_text=source_text,
        negative=bool(data.get("negative", False)),
        integer_values=integer_values,
        half_squiggle=bool(data.get("half_squiggle", False)),
        fractional_cells=tuple(cells),
        visible_decimal_places=int(data.get("visible_decimal_places", _visible_decimal_places(source_text))),
        represented=Decimal(0), error=Decimal(0), exact=False,
        integer_crossbars=tuple(integer_crossbars), scheme=SCHEME,
    )
    represented = decode_spelling(provisional)
    source = _source_decimal(source_text)
    return replace(provisional, represented=represented, error=abs(represented-source), exact=(represented==source))


def scheme_manifest() -> dict:
    return {
        "scheme": SCHEME,
        "base": BASE,
        "cell_values": [0, FULL_CYCLE_VALUE],
        "ordinary_cells": "0..15",
        "full_cycle_cell": FULL_CYCLE_VALUE,
        "squiggle_in_cell_weight": "2^-1",
        "subscale_bits_per_cell": SUBSCALE_BITS,
        "subscale_weights": "slot k => 2^(-4k)",
        "spacing_rule": {"spaced_straight": "1/1 slot", "unspaced_straight": "1/2 slot"},
        "automatic_fraction_cells": "spaced/full",
        "divider_semantics": {
            "crossbar_count_per_glyph": 4,
            "states": {"absent": 0, "dotted": "1/2", "solid": "1/1"},
            "solid": "1/1 counted divider",
            "dotted": "1/2 counted divider",
            "full_cycle_divider_count": FULL_CYCLE_DIVIDER_COUNT,
            "full_cycle_main_stroke_count": FULL_CYCLE_MAIN_STROKE_COUNT,
            "full_cycle_main_stroke_solid_count": FULL_CYCLE_MAIN_STROKE_SOLID_COUNT,
            "full_cycle_solid_mask": FULL_CYCLE_SOLID_MASK,
            "full_cycle_dotted_mask": FULL_CYCLE_DOTTED_MASK,
            "full_cycle_invariant": "12/12 solid main strokes + 4/4 solid subdividers",
        },
        "precomputed_variant_count": PRECOMPUTED_VARIANT_COUNT,
        "rewritable": True,
        "underlying_value_preserved": True,
    }
