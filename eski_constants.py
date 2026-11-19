"""eski_constants.py: the self-referential constants from "Scientific Theories and Inventions" (Noah G. King),
solved to double precision from their defining equations, plus the classical set.

    M  Metta    1.1975807343385265     (the Meum constant used across the engines)
    Q  Quetta   1.6396050363836068     Q^Q - 1/Q = Q
    B  Betta    1.3185175049703410     1 - (B - 1/B) = B^B - 1   (same as B^B - (1 - (B - 1)) = 1/B)
    pi, phi, e

Note on B: the book's table prints 1.38152…, but that value does not satisfy B's equation; the root of the
equation is 1.31852… (the printed digits look transposed). The engine uses the equation's root.

Master Multidim defaults interlock neutrally: chaos stays 0 (variation is the seed's job), and the shaping
macros take values tied to each other through the constants:
    QBM     morph = Q - 1 = 0.63961   fold = M = 1.19758   lattice = B - 1 = 0.31852
    pi·phi·e morph = 1/phi = 0.61803  fold = e/phi² ≈ 1.03829  lattice = 1/pi = 0.31831
The two sets sit next to each other (Q-1 ≈ 1/phi, B-1 ≈ 1/pi), so switching between them never jolts a sound.
"""
from __future__ import annotations
import math


def _bisect(f, a, b, n=200):
    fa = f(a)
    for _ in range(n):
        m = (a + b) / 2.0; fm = f(m)
        if (fa < 0) == (fm < 0):
            a, fa = m, fm
        else:
            b = m
    return (a + b) / 2.0


M = 1.1975807343385265
Q = _bisect(lambda x: x ** x - 1.0 / x - x, 1.5, 1.8)          # 1.6396050363836068
B = _bisect(lambda x: x ** x - (2.0 - x + 1.0 / x), 1.2, 1.5)    # 1.318517504970341
S = _bisect(lambda x: x ** x - (x + 1), 1.5, 2.0)                       # S + 1 = S^S
J = 1.7569   # Jetta, table value: the printed equation J^J = (J-1)^(1-(J-1)) has no root near it (needs the author's check)
O = _bisect(lambda x: x ** x - (x - 1) ** (1 / x) - x, 1.6, 1.9)          # O^O - (O-1)^(1/O) = O
o = _bisect(lambda x: x / (x - 1) - x ** x, 1.55, 1.9)                    # o/(o-1) = o^o
N = _bisect(lambda x: x ** x - (x - 1) / x - x, 1.3, 1.7)                 # N^N - ((N-1)/N) = N
A = 1.0 / (3 ** 0.5 - 1)                                                  # Atta: perfect scaling rectangular tessellation
PI = math.pi
PHI = (1 + 5 ** 0.5) / 2
E = math.e

SETS = {
    "QBM (Eski)": {"morph": Q - 1, "harmonic_freq": None, "chaos": 0.0, "fold_depth": M, "harmonic_lattice": B - 1},
    "π · φ · e": {"morph": 1 / PHI, "harmonic_freq": None, "chaos": 0.0, "fold_depth": E / PHI ** 2, "harmonic_lattice": 1 / PI},
    "legacy": {"morph": 0.75, "harmonic_freq": None, "chaos": 0.0, "fold_depth": 1.0, "harmonic_lattice": 0.35},
}
DEFAULT_SET = "QBM (Eski)"


def active_set():
    try:
        import compat_settings
        name = compat_settings.load().get("md_constant_set") or DEFAULT_SET
    except Exception:
        name = DEFAULT_SET
    return name if name in SETS else DEFAULT_SET


def defaults(name=None):
    """Master Multidim macro defaults (None = keep the project's base frequency)."""
    return dict(SETS.get(name or active_set(), SETS[DEFAULT_SET]))


def summative(n):
    """Summative branching sequence 0, 1, 2, 6, 24, 120, 720 … (n+1 multiplicative branchings per stem)."""
    return 0 if n <= 0 else math.factorial(n)


def residuals():
    """How exactly each constant satisfies its own equation (for the Help / Constants report)."""
    return {"Q": Q ** Q - 1 / Q - Q, "B": (1 - (B - 1 / B)) - (B ** B - 1), "B (second form)": B ** B - (1 - (B - 1)) - 1 / B}
