"""seed_gen.py — GROOVEBOX_R32_SEED_GENERATOR_20261109

Grammar-driven random seed programs.  Every press of 🎲 builds a *different program*
from a probabilistic grammar over the whole seed language (statements, control flow,
helpers, loops, comprehensions, dict tables, coordinate DSL, the isn/ics family, the
Equation-of-Reality tensors P/E/D, OT arithmetic, workspace variables, free syntax), then
checks it with the real evaluator (``seed_lang``) at several instants.  The only hard
limits are the editor's: 256 lines and 32 768 characters.  "Any working logic can do":
a candidate is accepted when it compiles, yields finite numbers at every probe instant
and is not constant in ``t``.  Otherwise it is regenerated — never collapsed to a
one-liner.

The vocabulary is read from the live seed environment, so a function or workspace
variable added to ``_seed_script_env`` is picked up here with no edit.
"""
from __future__ import annotations

import math
import random

import seed_lang

MAX_LINES = seed_lang.MAX_LINES
MAX_CHARS = seed_lang.MAX_CHARS

# Functions of one argument that are safe on any real input.
UNARY_SAFE = ("sin", "cos", "tanh", "isn", "ics", "isx", "isy", "abs", "floor", "ceil", "fabs",
              "ot_equiv_sin", "ot_equiv_cos", "ot_equiv_tanh", "sinh_s", "frac", "sign", "saturate")
# Functions that want a bounded argument (we wrap with clamp or tanh).
UNARY_BOUNDED = ("asin", "acos", "arcisn", "arcics", "sqrt", "log", "log2", "log10", "exp")
BINARY = ("atan2", "hypot", "min", "max", "pow_s", "math_mul", "math_add", "ot_equiv_add", "ot_equiv_mul",
          "mod", "wrap", "mix", "P", "E", "D", "tensor_z", "tensor_rel", "ot_equiv_atan2", "ot_equiv_hypot")
CONSTS = ("MEUM", "PHI", "pi", "tau", "SILVER", "SQRT2", "SQRT3", "MEUM_INV", "MEUM_NORM", "e")
SUGAR_CONSTS = ("π", "τ", "φ")
PREFERRED_WS = ("bpm", "step_index", "sequence_index", "graph_x", "graph_y", "graph_z", "graph_energy",
                "graph_phase", "graph_radius", "graph_angle", "graph_curvature", "graph_u", "graph_v",
                "graph_w", "domain_value", "domain_weight", "seed", "t_norm", "sample_rate", "ball_gravity",
                "cell_rule", "eq_low_hz", "eq_high_hz", "carrier_rms", "vector_drive", "wavetable_phase")


class _Gen:
    def __init__(self, rng, env, workspace):
        self.r = rng
        self.env = env
        self.fns = {k for k, v in env.items() if callable(v) and not k.startswith("_")}
        self.ws = [w for w in workspace if w in env] or ["graph_x", "bpm", "step_index"]
        pref = [w for w in PREFERRED_WS if w in env]
        self.ws_pref = pref or self.ws
        self.vars = []            # names the program has defined so far (top level)
        self.funcs = []           # (name, arity)
        self.lists = []
        self.dicts = []
        self.lines = []
        self.coord_used = False
        self.free_syntax = rng.random() < 0.55
        self.indent = 0

    # ---- helpers ---------------------------------------------------------
    def u(self, lo, hi, nd=3):
        return round(self.r.uniform(lo, hi), nd)

    def num(self):
        k = self.r.random()
        if k < 0.35:
            return str(self.u(0.1, 4.0))
        if k < 0.6:
            return str(self.r.randint(1, 16))
        if k < 0.8:
            return str(self.r.choice((32, 48, 64, 96, 110, 128, 220, 256, 432, 440, 512, 880)))
        return self.const()

    def const(self):
        if self.free_syntax and self.r.random() < 0.3:
            return self.r.choice(SUGAR_CONSTS)
        return self.r.choice(CONSTS)

    def fn(self, pool):
        cands = [f for f in pool if f in self.fns]
        return self.r.choice(cands) if cands else "sin"

    def wsvar(self):
        return self.r.choice(self.ws_pref if self.r.random() < 0.7 else self.ws)

    def var(self):
        if self.vars and self.r.random() < 0.75:
            return self.r.choice(self.vars[-6:] if self.r.random() < 0.6 else self.vars)
        return self.wsvar()

    def tvar(self):
        return self.r.choice(("t", "t", "t", "t_norm", "phase", "beat")) if "phase" in self.vars else self.r.choice(("t", "t", "t_norm"))

    def atom(self):
        k = self.r.random()
        if k < 0.3:
            return self.tvar()
        if k < 0.55:
            return self.var()
        if k < 0.8:
            return self.num()
        if k < 0.9 and self.lists:
            name, n = self.r.choice(self.lists)
            return "%s[int(abs(%s)) %% %d]" % (name, self.tvar(), n)
        if self.dicts:
            name, n = self.r.choice(self.dicts)
            return "%s[int(abs(%s * %s)) %% %d]" % (name, self.tvar(), self.num(), n)
        return self.wsvar()

    def expr(self, depth=0):
        """A numeric expression; deeper levels get simpler."""
        if depth >= 3:
            return self.atom()
        k = self.r.random()
        d = depth + 1
        if k < 0.22:
            f = self.fn(UNARY_SAFE)
            return "%s(%s)" % (f, self.expr(d))
        if k < 0.32:
            f = self.fn(UNARY_BOUNDED)
            inner = self.expr(d)
            if f in ("asin", "acos", "arcisn", "arcics"):
                return "%s(clamp(%s, -1, 1))" % (f, inner)
            if f in ("sqrt", "log", "log2", "log10"):
                return "%s(1 + abs(%s))" % (f, inner)
            return "%s(tanh(%s))" % (f, inner)
        if k < 0.45:
            f = self.fn(BINARY)
            if f in ("P", "E", "D"):
                return "%s(%s, %s)" % (f, self.expr(d), self.expr(d))
            if f == "mod":
                return "mod(%s, %s)" % (self.expr(d), self.num())
            if f == "mix":
                return "mix(%s, %s, 0.5 + 0.5 * isn(%s))" % (self.expr(d), self.expr(d), self.tvar())
            if f == "wrap":
                return "wrap(%s, %s)" % (self.expr(d), self.num())
            if f in ("min", "max"):
                return "%s(%s, %s, %s)" % (f, self.expr(d), self.expr(d), self.num())
            return "%s(%s, %s)" % (f, self.expr(d), self.expr(d))
        if k < 0.6:
            op = self.r.choice(("+", "-", "*", "*", "/"))
            rhs = self.expr(d)
            if op == "/":
                rhs = "(1 + abs(%s))" % rhs
            return "%s %s %s" % (self.expr(d), op, rhs)
        if k < 0.68:
            base = self.expr(d)
            p = self.r.choice(("2", "3", "0.5", "MEUM_INV"))
            if self.free_syntax and p in ("2", "3"):
                return "abs(%s)%s" % (base, {"2": "²", "3": "³"}[p])
            return "abs(%s) ** %s" % (base, p) if p == "0.5" else "(%s) ** %s" % (base, p)
        if k < 0.74:
            return "(%s if %s %s %s else %s)" % (self.expr(d), self.atom(), self.r.choice(("<", ">", "<=", ">=")),
                                                  self.num(), self.expr(d))
        if k < 0.8:
            return "clamp(%s, %s, %s)" % (self.expr(d), -self.r.randint(1, 8), self.r.randint(1, 8))
        if k < 0.86:
            return "lerp(%s, %s, 0.5 + 0.5 * %s(%s))" % (self.expr(d), self.expr(d), self.fn(("isn", "sin", "ics")), self.tvar())
        if k < 0.9:
            return "choose(%s, %s, %s, %s, floor(abs(%s) * %s))" % (self.num(), self.num(), self.num(), self.num(), self.tvar(), self.num())
        if k < 0.94 and self.funcs:
            name, arity = self.r.choice(self.funcs)
            return "%s(%s)" % (name, ", ".join(self.expr(d) for _ in range(arity)))
        if k < 0.97 and self.free_syntax:
            return "%s%s(%s)" % (self.r.randint(2, 9), self.fn(("sin", "isn", "cos", "ics")), self.tvar())
        return "tanh(%s) * %s" % (self.expr(d), self.num())

    def cond(self):
        k = self.r.random()
        a, b = self.expr(2), self.num()
        if k < 0.6:
            return "%s %s %s" % (a, self.r.choice(("<", ">", "<=", ">=")), b)
        if k < 0.8:
            j = self.r.choice((" and ", " or ")) if not self.free_syntax else self.r.choice((" && ", " || ", " and "))
            return "(%s > %s)%s(%s < %s)" % (a, b, j, self.expr(2), self.num())
        return "int(abs(%s)) %% %d == 0" % (a, self.r.randint(2, 5))

    def name(self, prefix):
        i = 0
        while True:
            n = "%s%d" % (prefix, i) if i else prefix
            if n not in self.vars and n not in self.env and n not in [f for f, _ in self.funcs]:
                return n
            i += 1

    def emit(self, line):
        self.lines.append("    " * self.indent + line)

    # ---- statements ------------------------------------------------------
    def stmt_assign(self):
        n = self.name(self.r.choice(("v", "w", "a", "b", "k", "amp", "freq", "mod", "env", "depth", "wob", "lfo", "ratio", "gain")))
        if self.free_syntax and self.r.random() < 0.25:
            self.emit("let %s = %s" % (n, self.expr()))
        else:
            self.emit("%s = %s" % (n, self.expr()))
        self.vars.append(n)

    def stmt_aug(self):
        if not self.vars:
            return self.stmt_assign()
        n = self.r.choice(self.vars)
        self.emit("%s %s %s" % (n, self.r.choice(("+=", "-=", "*=")), self.expr(1)))

    def stmt_if(self):
        n = self.name("sel")
        self.emit("if %s:" % self.cond())
        self.indent += 1
        self.emit("%s = %s" % (n, self.expr()))
        if self.r.random() < 0.3:
            self.stmt_assign()
        self.indent -= 1
        for _ in range(self.r.randint(0, 2)):
            self.emit("elif %s:" % self.cond())
            self.indent += 1
            self.emit("%s = %s" % (n, self.expr()))
            self.indent -= 1
        self.emit("else:")
        self.indent += 1
        self.emit("%s = %s" % (n, self.expr()))
        self.indent -= 1
        self.vars.append(n)

    def stmt_shorthand(self):
        n = self.name("pick")
        self.emit("%s = if(%s) %s elif(%s) %s elif %s" % (n, self.cond(), self.num(), self.cond(), self.num(), self.num()))
        self.vars.append(n)

    def stmt_for(self):
        acc = self.name("acc")
        k = self.r.choice(("k", "i", "n", "h"))
        hi = self.r.randint(3, 12)
        self.emit("%s = 0.0" % acc)
        self.emit("for %s in range(1, %d):" % (k, hi))
        self.indent += 1
        self.vars.append(k)
        body = self.r.random()
        if body < 0.5:
            self.emit("%s += %s(%s * %s) / %s" % (acc, self.fn(("isn", "sin", "ics", "cos")), self.tvar(), k, k))
        elif body < 0.75:
            self.emit("%s += %s * %s ** -%s" % (acc, self.expr(1), self.r.choice(("MEUM", "PHI", "2")), k))
        else:
            self.emit("if %s %% 2 == 0:" % k)
            self.indent += 1
            self.emit("%s += %s" % (acc, self.expr(1)))
            self.indent -= 1
            self.emit("else:")
            self.indent += 1
            self.emit("%s -= %s" % (acc, self.expr(2)))
            self.indent -= 1
        self.indent -= 1
        self.vars.remove(k)
        self.vars.append(acc)

    def stmt_while(self):
        n = self.name("iter")
        x = self.name("xw")
        self.emit("%s = 0" % n)
        self.emit("%s = %s" % (x, self.expr(1)))
        self.emit("while %s < %d and abs(%s) > 1e-9:" % (n, self.r.randint(2, 9), x))
        self.indent += 1
        self.emit("%s = %s(%s) * %s" % (x, self.fn(("tanh", "isn", "ics")), x, self.u(0.5, 1.5)))
        self.emit("%s += 1" % n)
        self.indent -= 1
        self.vars.extend((n, x))

    def stmt_def(self):
        fname = self.name(self.r.choice(("shape", "fold", "warp", "voice", "bend", "drive", "f", "g", "h")))
        arity = self.r.randint(1, 3)
        args = ["x", "y", "z"][:arity]
        if self.r.random() < 0.4 and arity > 1:
            self.emit("def %s(%s, %s=%s):" % (fname, ", ".join(args[:-1]), args[-1], self.num()))
        else:
            self.emit("def %s(%s):" % (fname, ", ".join(args)))
        self.indent += 1
        saved = self.vars
        self.vars = list(args)
        if self.r.random() < 0.5:
            self.emit("if abs(x) > %s:" % self.num())
            self.indent += 1
            self.emit("return %s" % self.expr(1))
            self.indent -= 1
        if self.r.random() < 0.4:
            self.emit("x = %s" % self.expr(1))
        self.emit("return %s" % self.expr())
        self.vars = saved
        self.indent -= 1
        self.funcs.append((fname, arity))
        n = self.name("y")
        self.emit("%s = %s(%s)" % (n, fname, ", ".join(self.expr(1) for _ in range(arity))))
        self.vars.append(n)

    def stmt_lambda(self):
        fname = self.name("lam")
        self.emit("%s = lambda x: %s" % (fname, self.expr(1).replace(self.tvar(), "x", 1)))
        self.funcs.append((fname, 1))

    def stmt_list(self):
        n = self.name(self.r.choice(("table", "ratios", "scale", "steps", "harm")))
        if self.r.random() < 0.5:
            cnt = self.r.randint(3, 8)
            self.emit("%s = [%s]" % (n, ", ".join(self.num() for _ in range(cnt))))
        else:
            cnt = self.r.randint(4, 12)
            self.emit("%s = [%s for k in range(%d)]" % (n, self.expr(1).replace("t", "k", 1) if "t" in self.expr(2) else "%s * k" % self.num(), cnt))
        self.lists.append((n, cnt))
        v = self.name("pickl")
        self.emit("%s = %s[int(abs(%s * %s)) %% len(%s)]" % (v, n, self.tvar(), self.num(), n))
        self.vars.append(v)

    def stmt_dict(self):
        n = self.name(self.r.choice(("bank", "mode", "preset", "lut")))
        cnt = self.r.randint(3, 7)
        self.emit("%s = {%s}" % (n, ", ".join("%d: %s" % (i, self.num()) for i in range(cnt))))
        self.dicts.append((n, cnt))
        v = self.name("sel")
        self.emit("%s = %s.get(int(abs(%s)) %% %d, %s)" % (v, n, self.tvar(), cnt, self.num()))
        self.vars.append(v)

    def stmt_sum(self):
        n = self.name("series")
        hi = self.r.randint(3, 9)
        self.emit("%s = sum(%s(%s * k * %s) / k for k in range(1, %d))" % (n, self.fn(("isn", "sin", "ics")), self.tvar(), self.num(), hi))
        self.vars.append(n)

    def stmt_walrus(self):
        n = self.name("g")
        self.emit("%s = (%s := %s) + %s * %s" % (self.name("ww"), n, self.expr(1), n, self.num()))
        self.vars.append(n)

    def stmt_tuple(self):
        a, b = self.name("p"), self.name("q")
        f = self.r.choice(("polar", "cartesian"))
        if f == "polar" and "polar" in self.fns:
            self.emit("%s, %s = polar(%s, %s * %s)" % (a, b, self.expr(1), self.const(), self.tvar()))
        else:
            self.emit("%s, %s = %s, %s" % (a, b, self.expr(1), self.expr(1)))
        self.vars.extend((a, b))

    def stmt_coord(self):
        if self.coord_used:
            return self.stmt_assign()
        self.coord_used = True
        fam = self.r.choice(("xy", "xyz", "polar", "spherical"))
        if fam in ("xy", "xyz"):
            self.emit("x(t) = %s" % self.expr(1))
            self.emit("y(t) = %s" % self.expr(1))
            if fam == "xyz":
                self.emit("z(t) = %s" % self.expr(1))
        else:
            self.emit("r(t) = %s" % self.expr(1))
            self.emit("theta(t) = %s * t * %s" % (self.const(), self.num()))
            if fam == "spherical":
                self.emit("phi(t) = 0.5 * pi + 0.25 * isn(t)")
        self.vars.append("x" if fam in ("xy", "xyz") else "r")

    def stmt_comment(self):
        self.emit("# " + self.r.choice((
            "modulation stage", "harmonic series", "tempo-locked selector", "shape the envelope",
            "workspace-bound term", "fold back into range", "early-out guard", "tensor coupling",
            "OT arithmetic", "coordinate projection", "lookup table", "wobble", "drive stage",
        )))

    def stmt_free(self):
        n = self.name("fz")
        forms = ("%s = 2%s + 3%s(%s)", "%s = %s^2 + %s(%s)", "%s = √(1 + %s²) * %s(%s)")
        f = self.r.choice(forms)
        self.emit(f % (n, self.tvar(), self.fn(("sin", "isn", "cos")), self.expr(2)) if f.count("%s") == 4 else f % (n, self.tvar(), self.fn(("sin", "isn")), self.expr(2)))
        self.vars.append(n)

    def stmt_graph(self):
        """A parametric graph on the graph_* workspace, not a single scalar."""
        forms = (
            "graph_r = hypot(graph_x, graph_y) + %s",
            "graph_a = atan2(graph_y, graph_x + %s)",
            "curve = graph_radius * isn(graph_angle + t * %s)",
            "knot = graph_x * ics(graph_phase) + graph_y * isn(graph_phase + %s)",
            "sheet = graph_u * graph_v + graph_w * tanh(t_norm * %s)",
        )
        self.emit(self.r.choice(forms) % self.const())
        self.emit("g = mix(graph_energy, graph_curvature, %s)" % self.u(0.2, 0.8))
        self.vars += ["g"]

    def stmt_lsystem(self):
        """A numeric L-system: a short rewrite iterated into a value."""
        axiom = self.r.choice(("A", "F", "X"))
        self.emit("ls = '%s'" % axiom)
        self.emit("rules = {'A': 'AB', 'B': 'A', 'F': 'F+F-F', 'X': 'X+Y', 'Y': 'F'}")
        self.emit("for _ in range(%d):" % self.r.randint(2, 5))
        self.indent += 1
        self.emit("ls = ''.join(rules.get(ch, ch) for ch in ls)[:48]")
        self.indent -= 1
        self.emit("ls_val = sum((i + 1) * (1 if ch in 'AFXY' else -1) for i, ch in enumerate(ls))")
        self.emit("ls_phase = isn(ls_val * %s + t)" % self.const())
        self.vars += ["ls_val", "ls_phase"]

    def stmt_map(self):
        """An iterative map (logistic / Meum / complex step) instead of one number."""
        kind = self.r.choice(("logistic", "meum", "ikeda"))
        if kind == "logistic":
            self.emit("xmap = %s" % self.u(0.1, 0.9))
            self.emit("r = %s" % self.u(3.2, 3.9))
            self.emit("for _ in range(%d):" % self.r.randint(4, 12))
            self.indent += 1
            self.emit("xmap = r * xmap * (1 - xmap)")
            self.indent -= 1
            self.emit("map_out = xmap * isn(t)")
        elif kind == "meum":
            self.emit("m = MEUM")
            self.emit("acc = %s" % self.u(0.2, 1.2))
            self.emit("for k in range(1, %d):" % self.r.randint(4, 9))
            self.indent += 1
            self.emit("acc = acc * m + isn(t * k) / k")
            self.indent -= 1
            self.emit("map_out = acc")
        else:
            self.emit("zx, zy = %s, %s" % (self.u(-0.5, 0.5), self.u(-0.5, 0.5)))
            self.emit("for _ in range(%d):" % self.r.randint(3, 8))
            self.indent += 1
            self.emit("zx, zy = isn(zx) + %s, ics(zy) + t_norm" % self.u(0.1, 0.4))
            self.indent -= 1
            self.emit("map_out = hypot(zx, zy)")
        self.vars.append("map_out")

    def stmt_tensor(self):
        """Equation-of-Reality tensors used as functions, not decoration."""
        self.emit("p = P(%s, t_norm)" % self.wsvar())
        self.emit("e = E(p, %s)" % self.const())
        self.emit("d = D(e, graph_energy if 'graph_energy' in dir() else %s)" % self.u(0.1, 0.8))
        self.emit("tensor = mix(p, e, %s) + d * isn(t)" % self.u(0.3, 0.7))
        self.vars += ["p", "e", "d", "tensor"]

    def stmt_early_return(self):
        self.emit("if %s:" % self.cond())
        self.indent += 1
        self.emit("return %s" % self.expr())
        self.indent -= 1

    STATEMENTS = (
        ("stmt_assign", 6), ("stmt_aug", 4), ("stmt_if", 6), ("stmt_shorthand", 4), ("stmt_for", 6),
        ("stmt_while", 3), ("stmt_def", 8), ("stmt_lambda", 6), ("stmt_list", 5), ("stmt_dict", 5),
        ("stmt_sum", 5), ("stmt_walrus", 3), ("stmt_tuple", 4), ("stmt_coord", 8), ("stmt_comment", 2),
        ("stmt_free", 5), ("stmt_early_return", 2), ("stmt_graph", 10), ("stmt_lsystem", 10),
        ("stmt_map", 8), ("stmt_tensor", 8),
    )

    def statement(self):
        names, weights = zip(*self.STATEMENTS)
        pick = self.r.choices(names, weights)[0]
        if pick == "stmt_free" and not self.free_syntax:
            pick = "stmt_assign"
        getattr(self, pick)()

    def final(self):
        """A time-varying combination of what the program computed."""
        terms = []
        pool = [v for v in self.vars if v not in ("x", "r")][-10:]
        self.r.shuffle(pool)
        for v in pool[: self.r.randint(2, 5)]:
            terms.append("%s * %s" % (self.u(0.1, 1.5), v))
        terms.append("%s(%s * %s)" % (self.fn(("isn", "sin", "ics", "cos")), self.tvar(), self.const()))
        if self.r.random() < 0.5:
            terms.append("%s * tanh(%s)" % (self.u(0.05, 0.5), self.wsvar()))
        body = " + ".join(terms)
        k = self.r.random()
        if k < 0.5:
            self.emit("result = %s" % body)
            self.emit("return result")
        elif k < 0.7:
            self.emit("return %s" % body)
        elif k < 0.85:
            self.emit("result = %s" % body)
            self.emit("result, %s" % (" , ".join(self.var() for _ in range(self.r.randint(1, 3)))))
        else:
            self.emit("return clamp(%s, %s, %s)" % (body, -self.r.randint(2, 64), self.r.randint(2, 512)))

    def build(self, target_lines):
        self.lines = []
        family = self.r.choice(("graph", "lsystem", "map", "tensor", "coord", "grammar"))
        self.emit("# seed program · %s · %d-line target" % (family, target_lines))
        self.emit("t_norm = t / (1 + abs(t))")
        if family == "graph":
            self.stmt_graph()
        elif family == "lsystem":
            self.stmt_lsystem()
        elif family == "map":
            self.stmt_map()
        elif family == "tensor":
            self.stmt_tensor()
        elif family == "coord":
            self.stmt_coord()
        self.vars.append("t_norm")
        if self.r.random() < 0.7:
            self.emit("phase = t * %s" % self.const())
            self.vars.append("phase")
        if self.r.random() < 0.5:
            self.emit("beat = t * bpm / 60")
            self.vars.append("beat")
        guard = 0
        while len(self.lines) < target_lines - 3 and guard < 4000:
            guard += 1
            before = len(self.lines)
            self.statement()
            if sum(len(l) + 1 for l in self.lines) > MAX_CHARS - 600:
                del self.lines[before:]
                break
        self.final()
        text = "\n".join(self.lines)
        if len(text.split("\n")) > MAX_LINES or len(text) > MAX_CHARS:
            return None
        return text


def _varies(vals_by_t):
    flat = [tuple(round(v, 9) for v in vs[:4]) for vs in vals_by_t]
    return len(set(flat)) > 1


def generate(env_fn, workspace, rng=None, target_lines=None, probes=(0.0, 0.5, 1.25, 2.75, 7.5), max_tries=40):
    """Return a validated random seed program.

    env_fn(t) -> seed namespace at time t (groovebox._seed_script_env bound to the live context).
    workspace -> iterable of readable workspace variable names.
    target_lines: None → random in [1, 256] biased long; else the exact aim.
    """
    rng = rng or random.Random()
    ws = list(workspace or ())
    env0 = env_fn(0.0)
    last_err = None
    for attempt in range(max_tries):
        if target_lines is None:
            k = rng.random()
            n = rng.randint(1, 12) if k < 0.08 else (rng.randint(12, 64) if k < 0.3 else rng.randint(64, MAX_LINES))
        else:
            n = int(target_lines)
        g = _Gen(rng, env0, ws)
        text = g.build(max(1, min(MAX_LINES, n)))
        if not text:
            continue
        ok = True
        series = []
        for tt in probes:
            ev = seed_lang.evaluate(text, env_fn(tt))
            if not ev.values or not all(math.isfinite(v) for v in ev.values):
                ok = False
                last_err = ev.error
                break
            series.append(ev.values)
        if ok and not _varies(series):
            ok = False
            last_err = "constant in t"
        if ok:
            return text
    # Extremely unlikely after 40 attempts; a tiny but still structured program.
    return ("t_norm = t / (1 + abs(t))\nphase = t * MEUM\nacc = 0.0\nfor k in range(1, 6):\n"
            "    acc += isn(phase * k) / k\nreturn 220 * (1 + 0.25 * tanh(acc)) + 40 * ics(t_norm * PHI)"
            + ("\n# last generator error: %s" % last_err if last_err else ""))
