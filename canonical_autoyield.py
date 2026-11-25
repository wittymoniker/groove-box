"""canonical_autoyield.py — the time-sliced canonical transaction, generated from the real engine functions.

The cooperative (time-sliced) commit used hand-copied generator versions of the canonical functions
(canonical_cooperative_kernels.py). Those copies drifted from the real functions, so a sliced commit produced
different sequence banks than the normal one — which is why slicing could not be the default and engine toggles
froze the window for seconds.

This module builds the sliced versions *from the current source of the real methods* at startup, so they cannot
drift: each method is parsed, and its AST is changed in exactly two ways —

  1. a pause point (`yield`) at the top of every for / while loop body, and at the start of the function;
  2. a call `self.<canonical method>(…)` becomes `(yield from self._coop_<method>(…))`, so the callee is sliced too
     and its return value is passed through unchanged.

It never pauses inside a `with` block (a held lock must not be held across a pause), inside nested functions /
lambdas / classes (they keep their own semantics), or inside comprehensions and f-strings (where `yield` is not
allowed). Statement order and every computed value are identical to the synchronous path; only *when* the UI thread
gets control back changes. If anything cannot be transformed, the caller keeps the synchronous path.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

NAMES = (
    "_apply_active_engines_meum_composite", "_apply_engine_with_shared_context", "_apply_euclidean_deterministically",
    "_apply_goava_deterministically", "_apply_live_engine_once", "_apply_phase_lock_deterministically",
    "_apply_randomizer_deterministically", "_apply_seeded_deterministically", "_canonical_playlist_paint",
    "_canonical_sequence_reconcile", "_engine_resize_untouched_sequences", "_engine_write_sequence_panels",
    "_ensure_perfect_unison", "_establish_clean_baseline", "_final_unison_reconciliation",
    "_finish_canonical_sequence_projection", "_paint_operator_pattern_to_playlist",
    "_rebuild_active_canonical_playlist", "apply_euclidean_and_idealized_rhythms",
    "apply_seeded_harmonic_randomization",
)
PREFIX = "_coop_"
ENTRY = PREFIX + "_ensure_perfect_unison"


class _Yielder(ast.NodeTransformer):
    def __init__(self, names):
        self.names = set(names)

    # scopes and constructs where a pause is unsafe or not allowed: leave them exactly as written
    def _keep(self, node):
        return node
    visit_FunctionDef = visit_AsyncFunctionDef = visit_Lambda = visit_ClassDef = _keep
    visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = _keep
    visit_JoinedStr = _keep
    visit_With = visit_AsyncWith = _keep

    def _loop(self, node):
        self.generic_visit(node)
        node.body.insert(0, ast.Expr(value=ast.Yield(value=None)))
        return node
    visit_For = visit_While = _loop

    def visit_Call(self, node):
        self.generic_visit(node)
        f = node.func
        if (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "self"
                and f.attr in self.names):
            call = ast.Call(func=ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()), attr=PREFIX + f.attr,
                                               ctx=ast.Load()),
                            args=node.args, keywords=node.keywords)
            return ast.YieldFrom(value=call)
        return node


def build(app_cls, module_globals, names=NAMES):
    """Compile and attach `_coop_<name>` generator methods to app_cls. Returns the list of built names."""
    built = {}
    for name in names:
        fn = getattr(app_cls, name)
        src = textwrap.dedent(inspect.getsource(fn))
        tree = ast.parse(src)
        fdef = tree.body[0]
        if not isinstance(fdef, ast.FunctionDef):
            raise TypeError("%s is not a plain method" % name)
        fdef.name = PREFIX + name
        fdef.decorator_list = []
        y = _Yielder(names)
        fdef.body = [ast.Expr(value=ast.Yield(value=None))] + [y.visit(st) for st in fdef.body]
        ast.fix_missing_locations(tree)
        ast.increment_lineno(tree, fn.__code__.co_firstlineno - 1)
        code = compile(tree, inspect.getsourcefile(fn) or "<canonical>", "exec")
        ns = {}
        exec(code, module_globals, ns)
        built[PREFIX + name] = ns[PREFIX + name]
    for k, v in built.items():
        setattr(app_cls, k, v)
    return sorted(built)


def ensure_built(app):
    """Build once per class; True when the sliced entry point exists."""
    cls = type(app)
    if getattr(cls, "_coop_built_ok", None) is None:
        try:
            import sys
            mod = sys.modules[cls.__module__]
            build(cls, vars(mod))
            cls._coop_built_ok = True
        except Exception as exc:
            print("[Canonical] sliced commit unavailable (%s: %s); using the synchronous path" % (type(exc).__name__, exc))
            cls._coop_built_ok = False
    return bool(cls._coop_built_ok)
