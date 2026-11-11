"""seed_lang.py — GROOVEBOX_R32_SEED_LANGUAGE_20261109

One principled pipeline for every seed script, replacing the four "first strategy that
returns something wins" fallbacks that let a 60-line program be valued by one stray line.

    text ──► normalize ──► desugar (token level, line-preserving) ──► compile (cached)
         ──► run as a function body ──► result policy ──► finite floats

Why a function body: a seed program is *one computation*, so it is compiled as the body
of a function.  That makes a top-level ``return`` legal (also an early ``return`` inside
an ``if``), gives the variables fast locals, and lets the whole program be cached as one
code object keyed by its text — re-evaluation at a new ``t`` is a dict lookup plus a call,
not a re-parse of 256 lines.

Result policy (first that applies):
    1. an explicit ``return`` value;
    2. every bare top-level expression, in order (``440`` / ``880`` on two lines → [440, 880];
       ``a, b, c`` → [a, b, c]);
    3. coordinate variables (x/y[/z], r/theta[/phi]) assigned by the program → the tuple;
    4. the variable assigned last at top level.
Non-finite numbers are dropped by the coercion step, so a program never needs its own
``isfinite`` guard (and ``math`` need not exist in the namespace).

Free syntax accepted on top of numeric Python:
    2t  3(t+1)  2sin(t)          implicit multiplication (number followed by name / paren)
    a ^ b                        power (there is no bitwise use in a seed)
    π τ φ ² ³ √ × ÷ − ≤ ≥ ≠      unicode maths
    && || !  true false null     C-style logic / literals
    else if                      → elif
    let / var / const x = …      → x = …
    x(t) = …   r(t) = …          coordinate DSL inside any program
    if(c) a elif(c2) b elif c    Groovebox's if/elif shorthand (one line)

Safety: a per-evaluation budget bounds every loop iteration and function call, so a
``while`` that never ends or a runaway recursion raises instead of freezing the UI.

Pure Python, no Qt; importable from worker threads.
"""
from __future__ import annotations

import ast
import hashlib
import io
import math
import re
import textwrap
import threading
import tokenize
from collections import OrderedDict

MAX_LINES = 256           # the editor's documented maximum program length
MAX_CHARS = 32768         # and its maximum size
LOOP_BUDGET = 50000       # loop iterations + function calls per evaluation
CACHE_SIZE = 192

# Groovebox's own parsers can be plugged in without importing groovebox here.
HOOKS = {
    "if_elif_shorthand": None,   # fn(text) -> ternary str | None
}

COORD_NAMES = ("x", "y", "z", "r", "theta", "phi", "rho")

# Names the highlighter / help text may show as "language words" (not exhaustive).
LANGUAGE_WORDS = (
    "if", "elif", "else", "for", "while", "in", "def", "return", "lambda", "and", "or", "not",
    "is", "break", "continue", "pass", "True", "False", "None", "let", "var", "const",
)


class SeedBudgetExceeded(RuntimeError):
    """Raised when a program spends more loop iterations / calls than LOOP_BUDGET."""


class _ReturnSentinel:
    __slots__ = ()

    def __repr__(self):
        return "<no return>"


_NO_RETURN = _ReturnSentinel()


# ---------------------------------------------------------------------------
# 1. normalize
# ---------------------------------------------------------------------------
def normalize(text):
    """CRLF → LF, tabs → 4 spaces, BOM gone, common indentation removed, trailing blank lines cut."""
    s = str(text or "")
    if s.startswith("﻿"):
        s = s[1:]
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
    lines = [ln.rstrip() for ln in s.split("\n")]
    while lines and not lines[-1].strip():
        lines.pop()
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return ""
    return textwrap.dedent("\n".join(lines))


# ---------------------------------------------------------------------------
# 2. desugar (line-preserving)
# ---------------------------------------------------------------------------
_UNICODE = [
    ("π", "pi"), ("τ", "tau"), ("φ", "PHI"), ("Φ", "PHI"), ("ϕ", "PHI"),
    ("×", "*"), ("·", "*"), ("÷", "/"), ("−", "-"), ("–", "-"),
    ("²", "**2"), ("³", "**3"), ("⁴", "**4"),
    ("≤", "<="), ("≥", ">="), ("≠", "!="), ("≈", "=="),
    ("∧", " and "), ("∨", " or "), ("¬", " not "),
    ("∞", "inf"),
]
_SQRT_RE = re.compile(r"√\s*(\(|[A-Za-z_]\w*|\d+(?:\.\d+)?)")
_ELSE_IF_RE = re.compile(r"^(\s*)else\s+if\b", re.I)
_LET_RE = re.compile(r"^(\s*)(?:let|var|const)\s+([A-Za-z_]\w*)\s*(=|:=)", re.I)
_COORD_RE = re.compile(r"^(\s*)(x|y|z|r|theta|phi|rho)\s*\(\s*t\s*\)\s*=(?!=)", re.I)
_CLOGIC = [(re.compile(r"&&"), " and "), (re.compile(r"\|\|"), " or "),
           (re.compile(r"(?<![=!<>])!(?!=)"), " not ")]
_LITERALS = {"true": "True", "false": "False", "null": "None", "none": "None", "nil": "None"}
_SHORTHAND_RE = re.compile(r"^\s*if\s*\(.*\belif\b", re.I)


def _line_level_desugar(line):
    """Rewrites that are easier on the raw line than on tokens (all keep the line count)."""
    s = line
    for a, b in _UNICODE:
        if a in s:
            s = s.replace(a, b)
    if "√" in s:
        s = _SQRT_RE.sub(lambda m: "sqrt(" if m.group(1) == "(" else "sqrt(%s)" % m.group(1), s)
    s = _ELSE_IF_RE.sub(r"\1elif", s)
    s = _LET_RE.sub(r"\1\2 \3", s)
    s = _COORD_RE.sub(lambda m: "%s%s =" % (m.group(1), m.group(2).lower()), s)
    code, sep, comment = s.partition("#")
    if code and not _has_string(code):
        for rx, rep in _CLOGIC:
            code = rx.sub(rep, code)
    s = code + sep + comment
    if _SHORTHAND_RE.match(s) and not s.rstrip().endswith(":"):
        fn = HOOKS.get("if_elif_shorthand")
        if fn is not None:
            try:
                sh = fn(s.strip())
                if sh:
                    s = (len(s) - len(s.lstrip())) * " " + sh
            except Exception:
                pass
    return s


def _has_string(code):
    return "'" in code or '"' in code


def _token_desugar(src):
    """Implicit multiplication, ``^`` → ``**``, C literals.  Column-exact edits per line."""
    edits = []          # (row, col0, col1, replacement)
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return src
    prev = None
    for tok in toks:
        ttype, tstr, (r0, c0), (r1, c1), _ = tok
        if ttype == tokenize.OP and tstr == "^":
            edits.append((r0, c0, c1, "**"))
        elif ttype == tokenize.OP and tstr == "^=":
            edits.append((r0, c0, c1, "**="))
        elif ttype == tokenize.NAME and tstr in _LITERALS:
            edits.append((r0, c0, c1, _LITERALS[tstr]))
        if prev is not None:
            ptype, pstr, _, (pr1, pc1), _ = prev
            adjacent = (pr1 == r0 and pc1 == c0)
            if adjacent and ptype == tokenize.NUMBER and (
                    (ttype == tokenize.NAME and tstr not in ("and", "or", "not", "if", "else", "in", "is", "for"))
                    or (ttype == tokenize.OP and tstr == "(")):
                if not pstr.lower().endswith(("e", "j")):
                    edits.append((r0, c0, c0, "*"))
        if ttype not in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT):
            prev = tok
    if not edits:
        return src
    lines = src.split("\n")
    for r, c0, c1, rep in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        i = r - 1
        if 0 <= i < len(lines):
            ln = lines[i]
            lines[i] = ln[:c0] + rep + ln[c1:]
    return "\n".join(lines)


def desugar(text):
    """Free seed syntax → plain Python.  Line count is preserved so diagnostics map 1:1."""
    s = normalize(text)
    if not s:
        return ""
    s = "\n".join(_line_level_desugar(ln) for ln in s.split("\n"))
    return _token_desugar(s)


# ---------------------------------------------------------------------------
# 3. compile (AST transform + cache)
# ---------------------------------------------------------------------------
class _Transform(ast.NodeTransformer):
    """Collect bare expressions as outputs; inject the budget tick into loops and defs."""

    def __init__(self):
        self.depth_fn = 0
        self.assigned = []          # top-level assigned names in source order
        self.has_return = False
        self.output_count = 0

    def _tick(self, node):
        call = ast.Expr(value=ast.Call(func=ast.Name(id="__tick__", ctx=ast.Load()), args=[], keywords=[]))
        return ast.copy_location(call, node)

    def visit_FunctionDef(self, node):
        self.depth_fn += 1
        self.generic_visit(node)
        self.depth_fn -= 1
        node.body.insert(0, self._tick(node))
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        self.depth_fn += 1
        self.generic_visit(node)
        self.depth_fn -= 1
        return node

    def visit_For(self, node):
        self.generic_visit(node)
        node.body.insert(0, self._tick(node))
        return node

    visit_AsyncFor = visit_For

    def visit_While(self, node):
        self.generic_visit(node)
        node.body.insert(0, self._tick(node))
        return node

    def visit_Return(self, node):
        if self.depth_fn == 0:
            self.has_return = True
        self.generic_visit(node)
        return node

    def visit_Assign(self, node):
        if self.depth_fn == 0:
            for tgt in node.targets:
                for n in ast.walk(tgt):
                    if isinstance(n, ast.Name):
                        self.assigned.append(n.id)
        self.generic_visit(node)
        return node

    def visit_AnnAssign(self, node):
        if self.depth_fn == 0 and isinstance(node.target, ast.Name):
            self.assigned.append(node.target.id)
        self.generic_visit(node)
        return node

    def visit_AugAssign(self, node):
        if self.depth_fn == 0 and isinstance(node.target, ast.Name):
            self.assigned.append(node.target.id)
        self.generic_visit(node)
        return node

    def visit_NamedExpr(self, node):
        if self.depth_fn == 0 and isinstance(node.target, ast.Name):
            self.assigned.append(node.target.id)
        self.generic_visit(node)
        return node

    def visit_Expr(self, node):
        self.generic_visit(node)
        if self.depth_fn > 0:
            return node
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node        # docstring-like comment; not a value
        self.output_count += 1
        call = ast.Expr(value=ast.Call(func=ast.Name(id="__emit__", ctx=ast.Load()),
                                       args=[node.value], keywords=[]))
        return ast.copy_location(call, node)

    # Forbidden in a seed: imports and attribute writes on the environment.
    def visit_Import(self, node):
        raise SyntaxError("import is not part of the seed language", ("<seed>", node.lineno, node.col_offset + 1, ""))

    visit_ImportFrom = visit_Import

    def visit_Global(self, node):
        raise SyntaxError("global is not part of the seed language", ("<seed>", node.lineno, node.col_offset + 1, ""))


class Program:
    __slots__ = ("code", "source", "assigned", "has_return", "output_count", "coord_keys", "line_count", "key")

    def __init__(self, code, source, tr, key):
        self.code = code
        self.source = source
        self.assigned = tuple(tr.assigned)
        self.has_return = tr.has_return
        self.output_count = tr.output_count
        self.coord_keys = tuple(k for k in COORD_NAMES if k in tr.assigned)
        self.line_count = source.count("\n") + 1 if source else 0
        self.key = key


_CACHE = OrderedDict()
_CACHE_LOCK = threading.Lock()
_STATS = {"hits": 0, "misses": 0}


def _cache_key(text):
    return hashlib.blake2b(str(text or "").encode("utf-8", "replace"), digest_size=16).hexdigest()


def compile_program(text):
    """Parse + transform + compile a seed program.  Cached by text.  Raises SyntaxError."""
    key = _cache_key(text)
    with _CACHE_LOCK:
        prog = _CACHE.get(key)
        if prog is not None:
            _CACHE.move_to_end(key)
            _STATS["hits"] += 1
            return prog
    _STATS["misses"] += 1
    src = desugar(text)
    if not src:
        raise SyntaxError("empty seed", ("<seed>", 1, 1, ""))
    if src.count("\n") + 1 > MAX_LINES:
        raise SyntaxError("seed program is longer than %d lines" % MAX_LINES, ("<seed>", MAX_LINES + 1, 1, ""))
    if len(src) > MAX_CHARS:
        raise SyntaxError("seed program is larger than %d characters" % MAX_CHARS, ("<seed>", 1, 1, ""))
    tree = parse_body(src)
    tr = _Transform()
    body = [tr.visit(stmt) for stmt in tree.body]
    body = [b for b in body if b is not None]
    # def __seed__(): <body>; return (__NO_RETURN__, locals())
    tail = ast.Return(value=ast.Tuple(elts=[ast.Name(id="__NO_RETURN__", ctx=ast.Load()),
                                            ast.Call(func=ast.Name(id="__locals__", ctx=ast.Load()), args=[], keywords=[])],
                                      ctx=ast.Load()))
    fn = ast.FunctionDef(name="__seed__", args=ast.arguments(posonlyargs=[], args=[], vararg=None, kwonlyargs=[],
                                                              kw_defaults=[], kwarg=None, defaults=[]),
                         body=body + [tail], decorator_list=[], returns=None)
    if hasattr(ast.FunctionDef, "type_params"):
        fn.type_params = []
    mod = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(mod)
    try:
        import ot_script_math
        mod = ot_script_math.rewrite(mod)
    except Exception:
        pass
    code = compile(mod, "<groovebox-seed>", "exec")
    prog = Program(code, src, tr, key)
    with _CACHE_LOCK:
        _CACHE[key] = prog
        while len(_CACHE) > CACHE_SIZE:
            _CACHE.popitem(last=False)
    return prog


def parse_body(src):
    """ast.parse of a desugared program as a *function body* (top-level return legal).

    Line numbers are kept 1:1 with the editor text.
    """
    indented = "\n".join("    " + ln if ln.strip() else ln for ln in src.split("\n"))
    wrapped = "def __seed__():\n" + indented
    try:
        tree = ast.parse(wrapped, mode="exec")
    except SyntaxError as exc:
        lineno = max(1, int(exc.lineno or 2) - 1)
        offset = max(1, int(exc.offset or 5) - 4)
        raise SyntaxError(exc.msg, ("<seed>", lineno, offset, exc.text or "")) from None
    fn = tree.body[0]
    for node in ast.walk(fn):
        if hasattr(node, "lineno"):
            node.lineno = max(1, node.lineno - 1)
        if getattr(node, "end_lineno", None) is not None:
            node.end_lineno = max(1, node.end_lineno - 1)
        if hasattr(node, "col_offset"):
            node.col_offset = max(0, node.col_offset - 4)
        if getattr(node, "end_col_offset", None) is not None:
            node.end_col_offset = max(0, node.end_col_offset - 4)
    return ast.Module(body=fn.body, type_ignores=[])


# ---------------------------------------------------------------------------
# 4. run
# ---------------------------------------------------------------------------
def coerce_numbers(obj, limit=4096):
    """Attributable finite numbers out of any result (bool → 0/1; nested up to 4 deep)."""
    out = []

    def walk(x, depth):
        if len(out) >= limit or x is None:
            return
        if isinstance(x, bool):
            out.append(1.0 if x else 0.0)
        elif isinstance(x, (int, float)):
            v = float(x)
            if math.isfinite(v):
                out.append(v)
        elif isinstance(x, complex):
            if math.isfinite(x.real):
                out.append(float(x.real))
        elif isinstance(x, (list, tuple, set, frozenset, range)) and depth < 4:
            for item in x:
                walk(item, depth + 1)
        elif isinstance(x, dict) and depth < 4:
            for item in x.values():
                walk(item, depth + 1)
        else:
            try:
                import numpy as _np
                if isinstance(x, _np.generic):
                    walk(float(x), depth)
                    return
                if isinstance(x, _np.ndarray):
                    for item in x.ravel()[:limit].tolist():
                        walk(item, depth + 1)
                    return
            except Exception:
                pass
            try:
                if hasattr(x, "__float__"):
                    walk(float(x), depth)
            except Exception:
                pass

    walk(obj, 0)
    return out


def coordinate_values(local_ns):
    """Cartesian / polar / spherical projection of coordinate variables, like the pure DSL."""
    g = {k: local_ns.get(k) for k in COORD_NAMES if k in local_ns}
    num = {}
    for k, v in g.items():
        n = coerce_numbers(v)
        if n:
            num[k] = n[0]
    if "x" in num and "y" in num:
        vals = [num["x"], num["y"]]
        if "z" in num:
            vals.append(num["z"])
        return vals, "cartesian"
    if ("r" in num or "rho" in num) and "theta" in num:
        r = num.get("r", num.get("rho"))
        th = num["theta"]
        if "phi" in num:
            ph = num["phi"]
            return [r * math.sin(ph) * math.cos(th), r * math.sin(ph) * math.sin(th), r * math.cos(ph)], "spherical"
        return [r * math.cos(th), r * math.sin(th)], "polar"
    if "x" in num and len(num) == 1:
        return [num["x"]], "cartesian"
    return None


class Evaluation:
    """Result of one run: values (finite floats), how they were chosen, and any error.

    ``locals`` is the program's variable snapshot at the end of the run (dissectable:
    every stage of a 256-line program can be read back), ``outputs`` the bare
    expressions it emitted in order.
    """
    __slots__ = ("values", "source", "error", "line", "program", "raw", "locals", "outputs")

    def __init__(self, values, source, error=None, line=0, program=None, raw=None, locals_=None, outputs=None):
        self.values = values
        self.source = source      # "return" | "outputs" | "coordinate" | "assigned" | "none" | "error"
        self.error = error
        self.line = line
        self.program = program
        self.raw = raw
        self.locals = locals_ or {}
        self.outputs = outputs or []

    def __bool__(self):
        return bool(self.values)

    def dissect(self, limit=64):
        """[(name, numbers)] for every numeric variable, in the program's assignment order."""
        out = []
        order = list(self.program.assigned) if self.program is not None else []
        seen = set()
        for name in order + sorted(self.locals):
            if name in seen or name.startswith("_") or name not in self.locals:
                continue
            seen.add(name)
            nums = coerce_numbers(self.locals[name], limit=8)
            if nums:
                out.append((name, nums))
            if len(out) >= limit:
                break
        return out


def run(program, env, budget=LOOP_BUDGET):
    """Run a compiled Program in ``env`` (a seed namespace dict; not mutated)."""
    ns = dict(env)
    outputs = []
    counter = [int(budget)]

    def __tick__():
        counter[0] -= 1
        if counter[0] < 0:
            raise SeedBudgetExceeded("seed program exceeded its loop / call budget (%d)" % budget)

    def __emit__(v):
        outputs.append(v)
        return v

    ns["__tick__"] = __tick__
    ns["__emit__"] = __emit__
    ns["__locals__"] = locals
    ns["__NO_RETURN__"] = _NO_RETURN
    try:
        import ot_script_math
        ot_script_math.install(ns)
    except Exception:
        pass
    ns.setdefault("__builtins__", {})
    exec(program.code, ns)
    fn = ns["__seed__"]
    rv = fn()
    local_ns = {}
    if isinstance(rv, tuple) and len(rv) == 2 and rv[0] is _NO_RETURN and isinstance(rv[1], dict):
        local_ns = rv[1]
        rv = _NO_RETURN
    # --- result policy -------------------------------------------------------
    kw = dict(program=program, locals_=local_ns, outputs=outputs)
    if rv is not _NO_RETURN:
        vals = coerce_numbers(rv)
        if vals:
            return Evaluation(vals, "return", raw=rv, **kw)
    if outputs:
        vals = []
        for o in outputs:
            vals.extend(coerce_numbers(o))
        if vals:
            return Evaluation(vals, "outputs", raw=outputs, **kw)
    coord = coordinate_values(local_ns) if program.coord_keys else None
    if coord:
        return Evaluation(list(coord[0]), "coordinate", raw=coord, **kw)
    for name in reversed(program.assigned):
        if name in local_ns and not name.startswith("_"):
            vals = coerce_numbers(local_ns[name])
            if vals:
                return Evaluation(vals, "assigned", raw=local_ns[name], **kw)
    return Evaluation([], "none", **kw)


def evaluate(text, env, budget=LOOP_BUDGET):
    """Compile (cached) + run.  Never raises: errors come back in Evaluation.error."""
    try:
        prog = compile_program(text)
    except SyntaxError as exc:
        return Evaluation([], "error", error="%s" % exc.msg, line=int(exc.lineno or 1))
    except Exception as exc:
        return Evaluation([], "error", error=repr(exc))
    try:
        return run(prog, env, budget)
    except SeedBudgetExceeded as exc:
        return Evaluation([], "error", error=str(exc), program=prog)
    except Exception as exc:
        line = 0
        tb = exc.__traceback__
        while tb is not None:
            if tb.tb_frame.f_code.co_filename == "<groovebox-seed>":
                line = tb.tb_lineno
            tb = tb.tb_next
        return Evaluation([], "error", error="%s: %s" % (type(exc).__name__, exc), line=line, program=prog)


def values(text, env, budget=LOOP_BUDGET):
    """Just the finite floats (empty list on any error)."""
    return evaluate(text, env, budget).values


# ---------------------------------------------------------------------------
# 5. static analysis for the editor (no execution)
# ---------------------------------------------------------------------------
def analyze(text, allowed_names):
    """Return None, or (message, line, col, length, severity) for a confident static problem.

    Runs on the desugared source so free syntax is never marked red.  Unknown loaded
    names (outside everything the program binds and ``allowed_names``) are errors;
    a later re-assignment of a seed variable is a warning (it changes every later use).
    """
    src = desugar(text)
    if not src.strip():
        return None
    if src.count("\n") + 1 > MAX_LINES:
        return ("SEED SCRIPT ERROR · program is longer than %d lines" % MAX_LINES, MAX_LINES + 1, 0, 1, "error")
    if len(src) > MAX_CHARS:
        return ("SEED SCRIPT ERROR · program is larger than %d characters" % MAX_CHARS, 1, 0, 1, "error")
    try:
        tree = parse_body(src)
        _Transform().visit(tree)          # rejects import / global; harmless otherwise
    except SyntaxError as exc:
        line = max(1, int(exc.lineno or 1))
        col = max(0, int(exc.offset or 1) - 1)
        return ("SEED SCRIPT ERROR · %s · line %d" % (exc.msg or "invalid syntax", line), line, col, 1, "error")
    except Exception:
        return None
    allowed = set(allowed_names or ()) | {"__tick__", "__emit__", "True", "False", "None"}
    bound = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                a = node.args
                for arg in list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs):
                    bound.add(arg.arg)
                if a.vararg:
                    bound.add(a.vararg.arg)
                if a.kwarg:
                    bound.add(a.kwarg.arg)
        elif isinstance(node, ast.Lambda):
            a = node.args
            for arg in list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs):
                bound.add(arg.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.comprehension,)):
            for n in ast.walk(node.target):
                if isinstance(n, ast.Name):
                    bound.add(n.id)
    unresolved = [n for n in ast.walk(tree)
                  if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                  and n.id not in allowed and n.id not in bound]
    if unresolved:
        n = min(unresolved, key=lambda q: (getattr(q, "lineno", 1), getattr(q, "col_offset", 0)))
        line = max(1, int(getattr(n, "lineno", 1) or 1))
        col = max(0, int(getattr(n, "col_offset", 0) or 0))
        return ("SEED SCRIPT ERROR · unknown variable/preset '%s' · line %d" % (n.id, line), line, col, max(1, len(n.id)), "error")
    writes = []

    class _W(ast.NodeVisitor):
        def visit_FunctionDef(self, node):      # locals of a helper are its own business
            return None
        visit_AsyncFunctionDef = visit_FunctionDef
        visit_Lambda = visit_FunctionDef

        def visit_Assign(self, node):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    writes.append((tgt.id, tgt))
            self.generic_visit(node.value)

        def visit_AugAssign(self, node):
            if isinstance(node.target, ast.Name):
                writes.append((node.target.id, node.target))
            self.visit(node.value)

        def visit_For(self, node):               # loop accumulators are expected to be re-written
            for stmt in node.body + node.orelse:
                if not isinstance(stmt, (ast.Assign, ast.AugAssign)):
                    self.visit(stmt)
            self.visit(node.iter)

        visit_While = visit_For

    _W().visit(tree)
    first = {}
    for name, node in sorted(writes, key=lambda it: (getattr(it[1], "lineno", 1), getattr(it[1], "col_offset", 0))):
        if name in first:
            prev = first[name]
            line = max(1, int(getattr(node, "lineno", 1) or 1))
            col = max(0, int(getattr(node, "col_offset", 0) or 0))
            prev_line = max(1, int(getattr(prev, "lineno", 1) or 1))
            return ("SEED SCRIPT WARNING · redefining variable '%s' · line %d writes over the value first assigned on line %d; later seed expressions use the new value" % (name, line, prev_line),
                    line, col, max(1, len(name)), "warning")
        first[name] = node
    return None


def cache_stats():
    with _CACHE_LOCK:
        return dict(_STATS, size=len(_CACHE))


def clear_cache():
    with _CACHE_LOCK:
        _CACHE.clear()


def help_text():
    return __doc__.split("Free syntax accepted", 1)[1].split("Safety:", 1)[0].strip()


# ---------------------------------------------------------------------------
# 6. program signature (GROOVEBOX_R32_SEED_SIGNATURE_20261109)
# ---------------------------------------------------------------------------
SIGNATURE_PROBES = tuple(i * 0.25 for i in range(16)) + (6.0, 8.0, 12.0, 16.0)
_SIG_CACHE = OrderedDict()


def signature(text, env_fn, probes=SIGNATURE_PROBES):
    """31-bit fingerprint of what the *whole program computes* over time.

    The old integer seed came from one scalar at t = 0, so two very different 256-line
    programs that happened to agree there (or whose first value differed only after the
    3rd decimal) seeded every engine identically.  The signature hashes the evaluated
    value vectors at 20 probe instants (beats 0 … 16), rounded to 12 significant digits so
    it is stable across platforms.  Cached by text; ``env_fn(t)`` gives the namespace.
    """
    key = _cache_key(text)
    with _CACHE_LOCK:
        hit = _SIG_CACHE.get(key)
        if hit is not None:
            return hit
    h = hashlib.blake2b(digest_size=8)
    for tt in probes:
        try:
            vals = evaluate(text, env_fn(tt)).values[:32]
        except Exception:
            vals = []
        h.update(("|%d:" % len(vals)).encode())
        for v in vals:
            h.update(("%.12g," % v).encode())
    sig = int.from_bytes(h.digest(), "little") & 0x7FFFFFFF
    sig = sig or 1
    with _CACHE_LOCK:
        _SIG_CACHE[key] = sig
        while len(_SIG_CACHE) > CACHE_SIZE:
            _SIG_CACHE.popitem(last=False)
    return sig
