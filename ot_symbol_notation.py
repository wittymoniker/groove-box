"""Contextual Operator-Theory symbol notation for Mathematician's Groovebox.

This module implements the author's documented symbol grammar conservatively:
- numbers use four groups of three directional strokes (12 strokes total),
- four separators encode up to sixteen counted states,
- variables may be boxed,
- direction is four-way (up/right/down/left) rather than a single +/- bit,
- operation-frame styles and continued-series enclosure are metadata, not digit value.

Where the book does not provide a unique machine encoding, the mapping here is an
explicit Groovebox convention.  It is reversible and kept separate from the numeric
backend so ordinary base-10 remains available as a secondary view.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence

class Direction(str, Enum):
    UP='up'; RIGHT='right'; DOWN='down'; LEFT='left'

class Role(str, Enum):
    INDEPENDENT_VARIABLE='independent_variable'
    INDEPENDENT_CONSTANT='independent_constant'
    RESULT='result'
    DEPENDENT_CONSTANT='dependent_constant'
    DEPENDENT_VARIABLE='dependent_variable'

ROLE_COLORS = {
    # High-contrast palette tuned for dark appliance UIs while remaining
    # distinct under both light and dark host themes.  Dependent-constant
    # uses near-black with a guaranteed light cell fill in the painter so
    # strokes stay readable; dependent-variable uses off-white with a
    # dark cell fill for the same reason.
    Role.INDEPENDENT_VARIABLE: '#ff4d4d',  # vivid red
    Role.INDEPENDENT_CONSTANT: '#30d158',  # vivid green
    Role.RESULT: '#5ac8fa',                # bright sky blue (was #2f80ff)
    Role.DEPENDENT_CONSTANT: '#1c1c1e',    # near-black
    Role.DEPENDENT_VARIABLE: '#f2f2f7',    # off-white
}

class Border(str, Enum):
    MISSING='missing'
    DOTTED='dotted'
    SOLID='solid'
    OPEN='open'

class Operation(str, Enum):
    NONE='none'
    ADD='add'; SUB='sub'; MUL='mul'; DIV='div'; POWER='power'; ROOT='root'

@dataclass(frozen=True)
class Glyph:
    value: int                  # 0..15 separator state
    direction: Direction
    squiggly_mask: int = 0      # 12-bit context-modifier field: imaginary/decimal/half/doubling
    presence_mask: int = 0xFFF   # 12-bit stroke presence; missing = skipped count
    operation: Operation = Operation.NONE
    continued: bool = False     # dotted enclosing square = ordinary continued expansion
    multiplicity: int = 1      # line-connected solid square event multiplicity
    role: Role = Role.RESULT
    variable_letter: str = ''

    @property
    def separator_mask(self) -> int:
        return self.value & 0xF

    @property
    def operation_border(self) -> Border:
        if self.operation is Operation.MUL:
            return Border.OPEN
        if self.operation in (Operation.ADD, Operation.SUB):
            return Border.DOTTED
        if self.operation is Operation.DIV:
            return Border.SOLID
        return Border.MISSING


def direction_for(value: float, context_index: int = 0) -> Direction:
    """Four-way sign pathway. Two of four directions carry negative orientation.

    Positive/zero values select UP or RIGHT; negative values select DOWN or LEFT.
    This gives a 2-of-4 (50%) negative-oriented pathway space while retaining a
    deterministic second direction within each polarity.
    """
    parity = int(context_index) & 1
    if float(value) < 0.0:
        return Direction.DOWN if parity == 0 else Direction.LEFT
    return Direction.UP if parity == 0 else Direction.RIGHT


def encode_nibble(n: int, *, direction: Direction = Direction.UP,
                  operation: Operation = Operation.NONE, continued: bool = False,
                  multiplicity: int = 1, role: Role = Role.RESULT,
                  variable_letter: str = '') -> Glyph:
    n = int(n)
    if not 0 <= n <= 15:
        raise ValueError('nibble must be 0..15')
    # The four separator presences carry the 0..15 value.  The twelve line
    # straight/squiggly states are a deterministic secondary texture derived from
    # the value and direction, leaving separator decoding unambiguous.
    dcode = list(Direction).index(direction)
    squig = ((n * 0x249) ^ (dcode * 0x155)) & 0xFFF
    return Glyph(n, direction, squig, 0xFFF, operation, bool(continued), max(1,int(multiplicity)), role, variable_letter[:1])


def decode_nibble(glyph: Glyph) -> int:
    return int(glyph.separator_mask)


def encode_decimal(value: int | float, *, role: Role = Role.RESULT,
                   operation: Operation = Operation.NONE, continued: bool = False,
                   multiplicity: int = 1, variable_letter: str = '') -> list[Glyph]:
    """Encode the base-10 textual digits into reversible 0..15 author glyph cells.

    Decimal digits remain digits 0..9; the 10..15 symbol states are reserved for
    compact non-decimal/event use.  This makes Math Symbols OFF a direct base-10 view.
    """
    iv = int(round(float(value)))
    digits = str(abs(iv))
    out=[]
    for i,ch in enumerate(digits):
        out.append(encode_nibble(int(ch), direction=direction_for(iv, i),
                                 operation=operation, continued=continued,
                                 multiplicity=multiplicity, role=role,
                                 variable_letter=variable_letter if i == 0 else ''))
    return out


def decode_decimal(glyphs: Sequence[Glyph]) -> int:
    if not glyphs:
        return 0
    digits=[]
    for g in glyphs:
        n=decode_nibble(g)
        if n>9:
            raise ValueError('glyph sequence contains non-decimal nibble')
        digits.append(str(n))
    magnitude=int(''.join(digits))
    neg = glyphs[0].direction in (Direction.DOWN, Direction.LEFT)
    return -magnitude if neg else magnitude


def stroke_semantics(glyph: Glyph, stroke_index: int, context: str = "count") -> str:
    """Decode one of the twelve strokes conservatively.

    Missing means skipped count. Straight means an ordinary/full counted stroke.
    A squiggle is a contextual modifier; author clarification permits imaginary,
    decimal/fractional, half-count, or symbolic doubling meanings.  The enclosing
    operation/context selects the interpretation instead of assigning one universal
    scalar value to every squiggle.
    """
    i = int(stroke_index)
    if not 0 <= i < 12:
        raise IndexError('stroke index must be 0..11')
    if not (glyph.presence_mask & (1 << i)):
        return 'skip'
    if not (glyph.squiggly_mask & (1 << i)):
        return 'count:1'
    c = str(context).lower()
    if c in ('imaginary','complex','i'): return 'imaginary'
    if c in ('decimal','fraction','fractional'): return 'decimal'
    if c in ('half','half-count','counted'): return 'count:0.5'
    if c in ('double','doubling','times2','x2'): return 'symbolic:x2'
    return 'modified'  # deliberately unresolved until its enclosing context is known


def ascii_glyph(glyph: Glyph, context: str = 'count') -> str:
    """Portable ASCII analogy for documentation/logging, not a replacement glyph."""
    arrows={Direction.UP:'U',Direction.RIGHT:'R',Direction.DOWN:'D',Direction.LEFT:'L'}
    strokes=[]
    for i in range(12):
        sem=stroke_semantics(glyph,i,context)
        strokes.append('.' if sem=='skip' else ('~' if sem!='count:1' else '|'))
    border={Border.MISSING:' ',Border.OPEN:'[>',Border.DOTTED:':',Border.SOLID:'[]'}[glyph.operation_border]
    var=f"<{glyph.variable_letter}>" if glyph.variable_letter else ''
    cont='::' if glyph.continued else ''
    mult=f"-[x{glyph.multiplicity}]" if glyph.multiplicity>1 else ''
    return f"{cont}{border}{arrows[glyph.direction]}:{''.join(strokes)}:{glyph.separator_mask:X}{var}{mult}"


def base10(value) -> str:
    return str(value)
