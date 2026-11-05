"""GROOVEBOX_R23R_OT_SCRIPT_DIVISION_20261103 — divide-by-zero in every script, by OT.

While Operator Theory is ON, every `/`, `//`, `%` (and `/=`, `//=`, `%=`) written in a
script — seed scripts, graph / global scripts, domain equations, media patterns, game
seed scripts — runs through the project's OT division instead of Python's, so a zero
divisor is a defined case rather than an error:

    a / b   b != 0 : the exact quotient (unchanged)
            0 / 0  : 1                      (ot_div: the ratio of a thing to itself)
            a / 0  : signed infinity        (ot_div → _division_zero_result(a, "inf"))
    a // b  b == 0 : the same value as a / 0 (floor of ±inf is ±inf; 0//0 = 1)
    a % b   b == 0 : a                      (nothing is divided out: the whole remains)

Non-zero divisions are bit-identical to Python's, so turning this on never retunes a
project. Works for scalars and numpy arrays (element-wise). With OT OFF, scripts keep
Python's own semantics.
"""
from __future__ import annotations

import ast
import math
import sys

try:
    import numpy as np
except Exception:          # pragma: no cover
    np = None


def ot_enabled() -> bool:
    gb = sys.modules.get("groovebox")
    return bool(getattr(gb, "OP_THEORY_ENABLED", True)) if gb is not None else True


def _is_array(x):
    return np is not None and isinstance(x, np.ndarray)


def _zero_div_scalar(a):
    a = float(a)
    if a == 0.0:
        return 1.0
    return math.copysign(math.inf, a)


def ot_truediv(a, b):
    if not ot_enabled():
        return a / b
    if _is_array(a) or _is_array(b):
        a_ = np.asarray(a, dtype=np.float64); b_ = np.asarray(b, dtype=np.float64)
        a_, b_ = np.broadcast_arrays(a_, b_)
        out = np.empty(a_.shape, dtype=np.float64)
        nz = b_ != 0.0
        np.divide(a_, b_, out=out, where=nz)
        z = ~nz
        if np.any(z):
            az = a_[z]
            out[z] = np.where(az == 0.0, 1.0, np.copysign(np.inf, az))
        return out
    try:
        bf = float(b)
    except (TypeError, ValueError):
        return a / b                     # not numbers (e.g. string formatting): Python's own
    if bf != 0.0:
        return a / b
    return _zero_div_scalar(a)


def ot_floordiv(a, b):
    if not ot_enabled():
        return a // b
    if _is_array(a) or _is_array(b):
        q = ot_truediv(a, b)
        return np.floor(q)
    try:
        bf = float(b)
    except (TypeError, ValueError):
        return a // b
    if bf != 0.0:
        return a // b
    return _zero_div_scalar(a)


def ot_mod(a, b):
    if not ot_enabled():
        return a % b
    if _is_array(a) or _is_array(b):
        a_ = np.asarray(a, dtype=np.float64); b_ = np.asarray(b, dtype=np.float64)
        a_, b_ = np.broadcast_arrays(a_, b_)
        out = np.array(a_, dtype=np.float64, copy=True)          # b == 0: the whole remains
        nz = b_ != 0.0
        np.mod(a_, b_, out=out, where=nz)
        return out
    try:
        bf = float(b)
    except (TypeError, ValueError):
        return a % b                     # "%s" % x formatting stays Python's
    if bf != 0.0:
        return a % b
    return a


HELPERS = {"__ot_truediv__": ot_truediv, "__ot_floordiv__": ot_floordiv, "__ot_mod__": ot_mod}
_FN = {ast.Div: "__ot_truediv__", ast.FloorDiv: "__ot_floordiv__", ast.Mod: "__ot_mod__"}


class _Rewrite(ast.NodeTransformer):
    def visit_BinOp(self, node):
        self.generic_visit(node)
        fn = _FN.get(type(node.op))
        if fn is None:
            return node
        return ast.copy_location(ast.Call(func=ast.Name(id=fn, ctx=ast.Load()), args=[node.left, node.right],
                                          keywords=[]), node)

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        fn = _FN.get(type(node.op))
        if fn is None or not isinstance(node.target, (ast.Name, ast.Attribute, ast.Subscript)):
            return node
        import copy as _copy
        load = _copy.deepcopy(node.target)
        load.ctx = ast.Load()
        for n in ast.walk(load):
            if hasattr(n, "ctx") and n is not load:
                n.ctx = ast.Load()
        call = ast.Call(func=ast.Name(id=fn, ctx=ast.Load()), args=[load, node.value], keywords=[])
        return ast.copy_location(ast.Assign(targets=[node.target], value=call), node)


def rewrite(tree):
    """Route the script's divisions through OT (always rewritten; the helpers check the OT
    switch at run time, so toggling OT never needs a recompile)."""
    tree = _Rewrite().visit(tree)
    return ast.fix_missing_locations(tree)


def install(scope):
    """Put the helpers into an eval / exec namespace."""
    scope.update(HELPERS)
    return scope


def compile_script(source, filename, mode, scope=None):
    """ast.parse + rewrite + compile in one call (scope gets the helpers)."""
    tree = rewrite(ast.parse(source, mode=mode))
    if scope is not None:
        install(scope)
    return compile(tree, filename, mode)
