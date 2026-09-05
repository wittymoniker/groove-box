"""Canonical high-precision Meum constants for Mathematician's Groovebox.

The mathematical Meum constant is defined by the project as the unique root M in
(1, 2) of 2**M = M**4 + M**2 - M.  Runtime DSP uses IEEE-754 binary64, so this
module hardcodes the correctly-rounded binary64 value (hex form) and the major
derived constants once.  A long decimal reference is retained for documentation,
verification, serialization metadata, and higher-precision offline calculations.

Using one central source prevents small drift caused by independently truncating
1.1975807343... in different modules.  It does not make binary64 arithmetic exact;
it makes every Groovebox subsystem start from the same best binary64 value.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
import math
from functools import lru_cache

# 100+ digit reference for the project-defined root.
MEUM_DECIMAL = (
    "1.197580734338526518831326189268352139462000770610620512690713161173612434527857961133371127128476968476"
)

# Correctly-rounded IEEE-754 binary64 representation of the reference above.
# Hexadecimal literals are exact and stable across Python/C/C++ implementations.
MEUM = float.fromhex("0x1.3294a6a84dbb1p+0")
M = MEUM

# Derived binary64 values are hardcoded from high-precision evaluation so every
# subsystem uses the same rounded result rather than re-deriving from truncated M.
MEUM_MINUS_1 = float.fromhex("0x1.94a535426dd88p-3")
MEUM_INV = float.fromhex("0x1.ab875185e6289p-1")
MEUM_TWO_MINUS = float.fromhex("0x1.9ad6b2af6489ep-1")
MEUM_NORM = float.fromhex("0x1.51e2b9e8675dap-3")  # (M-1)/M
MEUM_SQ = float.fromhex("0x1.6f27b4bb78ebcp+0")
MEUM_CUBE = float.fromhex("0x1.b7b2a801b3a72p+0")
MEUM_FOURTH = float.fromhex("0x1.07496f2d0ab58p+1")
MEUM_TWO_POW = float.fromhex("0x1.2592f636a04dep+1")
MEUM_LOG2 = float.fromhex("0x1.0a5da9844f8b0p-2")

# Correctly-rounded high-precision powers used by the bounded 12-step Meum lattice.
_MEUM_POWERS_BY_EXP = {
    -6: float.fromhex("0x1.5b1cfbd881660p-2"),
    -5: float.fromhex("0x1.9fb233c3638fcp-2"),
    -4: float.fromhex("0x1.f1d4638452b27p-2"),
    -3: float.fromhex("0x1.2a1878ea5b357p-1"),
    -2: float.fromhex("0x1.64fe58bde17d1p-1"),
    -1: MEUM_INV,
     0: 1.0,
     1: MEUM,
     2: MEUM_SQ,
     3: MEUM_CUBE,
     4: MEUM_FOURTH,
     5: float.fromhex("0x1.3b4ea8bed310dp+1"),
}
MEUM_POWERS_12 = tuple(_MEUM_POWERS_BY_EXP[e] for e in range(-6, 6))
MEUM_POWERS_36 = tuple(_MEUM_POWERS_BY_EXP[(i % 12) - 6] for i in range(36))

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_INV = PHI - 1.0
SQRT2 = math.sqrt(2.0)
SQRT3 = math.sqrt(3.0)
SILVER = 1.0 + SQRT2
E_IRR = math.e
PI_IRR = math.pi

# High-precision decimal references for offline checks / documentation.
with localcontext() as _ctx:
    _ctx.prec = 110
    MEUM_D = Decimal(MEUM_DECIMAL)
    MEUM_MINUS_1_D = MEUM_D - Decimal(1)
    MEUM_INV_D = Decimal(1) / MEUM_D
    MEUM_TWO_MINUS_D = Decimal(2) - MEUM_D
    MEUM_NORM_D = MEUM_MINUS_1_D / MEUM_D
    MEUM_SQ_D = MEUM_D * MEUM_D
    MEUM_CUBE_D = MEUM_SQ_D * MEUM_D
    MEUM_FOURTH_D = MEUM_SQ_D * MEUM_SQ_D

# Authoritative traversal vocabulary: rational anchors remain structural; these
# irrational-family quantities are used for traversal, phase, indexing, etc.
MEUM_BASIS = {
    "M": MEUM,
    "M-1": MEUM_MINUS_1,
    "1/M": MEUM_INV,
    "2-M": MEUM_TWO_MINUS,
    "(M-1)/M": MEUM_NORM,
    "e-2": E_IRR - 2.0,
    "phi-1": PHI_INV,
    "sqrt2-1": SQRT2 - 1.0,
    "pi-3": PI_IRR - 3.0,
}

@lru_cache(maxsize=128)
def meum_power(exponent: int) -> float:
    """Return M**exponent with exact cached values for the hot bounded lattice.

    Outside -6..5, Python's correctly-rounded binary64 power is cached so repeated
    calls do not redo exponentiation.  Integer exponents only are accepted here;
    continuous powers remain caller-owned transforms.
    """
    e = int(exponent)
    if e in _MEUM_POWERS_BY_EXP:
        return _MEUM_POWERS_BY_EXP[e]
    return MEUM ** e


def meum_equation_residual(x: float = MEUM) -> float:
    """Binary64 residual of 2**x - x**4 - x**2 + x."""
    x = float(x)
    return (2.0 ** x) - (x*x*x*x + x*x - x)


def meum_precision_report() -> dict:
    """Small deterministic precision/provenance report for diagnostics/help."""
    return {
        "definition": "unique root M in (1,2) of 2^M = M^4 + M^2 - M",
        "decimal_reference": MEUM_DECIMAL,
        "binary64": MEUM,
        "binary64_hex": MEUM.hex(),
        "residual_binary64": meum_equation_residual(),
        "M-1": MEUM_MINUS_1,
        "1/M": MEUM_INV,
        "2-M": MEUM_TWO_MINUS,
        "(M-1)/M": MEUM_NORM,
    }
