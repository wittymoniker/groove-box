"""Math-grep: evidence-oriented mathematical semantics scanner.

This tool discovers numeric expressions and mathematical operations in Python source.
It deliberately distinguishes syntactic discovery from semantic proof. It does not
claim that a numeric expression describes physical reality unless units, intent,
and external evidence are supplied.

CLI: python math_grep.py PATH [--json report.json]
"""
from __future__ import annotations
import ast
import hashlib
import json
import math
import operator
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

VERSION = "math-grep-evidence-v1"

@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    column: int
    category: str
    expression: str
    exact_form: str | None
    semantic_status: str
    evidence_needed: tuple[str, ...]
    source_hash: str

class _Expression(ast.NodeVisitor):
    """Conservative exact simplifier for a small, safe arithmetic subset."""
    BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod}
    def evaluate(self, node: ast.AST) -> Fraction | None:
        try:
            if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
                return Fraction(node.value)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
                v = self.evaluate(node.operand)
                return (-v if isinstance(node.op, ast.USub) else v) if v is not None else None
            if isinstance(node, ast.BinOp) and type(node.op) in self.BIN:
                a, b = self.evaluate(node.left), self.evaluate(node.right)
                if a is None or b is None: return None
                if isinstance(node.op, ast.Div) and b == 0: return None
                if isinstance(node.op, ast.Pow):
                    if b.denominator != 1 or abs(b.numerator) > 64: return None
                    if a == 0 and b < 0: return None
                    return a ** b.numerator
                return self.BIN[type(node.op)](a, b)
        except (ArithmeticError, OverflowError, ValueError, TypeError):
            return None
        return None

class MathGrep:
    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self.errors: list[dict[str, str]] = []

    def scan_file(self, path: str | Path) -> list[Finding]:
        p = Path(path)
        try:
            raw = p.read_bytes(); source = raw.decode("utf-8")
            tree = ast.parse(source, filename=str(p))
        except (OSError, UnicodeError, SyntaxError) as exc:
            self.errors.append({"path": str(p), "error": str(exc)})
            return []
        digest = hashlib.sha256(raw).hexdigest()
        out: list[Finding] = []
        for node in ast.walk(tree):
            category = None
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                category = "numeric_literal"
            elif isinstance(node, ast.BinOp):
                category = "arithmetic_operation"
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {
                "sin", "cos", "tan", "sqrt", "log", "log10", "exp", "fabs", "floor", "ceil", "hypot"
            }:
                category = "math_function"
            elif isinstance(node, ast.Compare):
                category = "numeric_or_order_comparison"
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"clip", "clamp", "normalize", "rescale", "interpolate"}:
                category = "scale_or_bound_operation"
            if not category: continue
            expr = ast.get_source_segment(source, node) or ast.dump(node, include_attributes=False)
            exact = _Expression().evaluate(node)
            exact_form = str(exact) if exact is not None else None
            # Statuses are deliberately conservative; AST inspection alone cannot prove intent.
            status = "exact-syntax-only" if exact is not None else "discovered-not-proven"
            needs = ["declare intended meaning and domain", "check units and range", "validate behavior against a reference or invariant"]
            if category == "numeric_literal": needs = ["identify semantic role and units", "verify boundary/default behavior"]
            if category == "math_function": needs = ["verify function domain and angle/unit convention", "compare against expected behavior"]
            out.append(Finding(str(p), getattr(node, "lineno", 1), getattr(node, "col_offset", 0), category,
                               expr, exact_form, status, tuple(needs), digest))
        self.findings.extend(out)
        return out

    def scan(self, paths: Iterable[str | Path]) -> dict[str, Any]:
        for path in paths:
            p = Path(path)
            if p.is_dir():
                for child in sorted(p.rglob("*.py")):
                    if any(part in {".git", "__pycache__", ".venv", "venv"} for part in child.parts): continue
                    self.scan_file(child)
            else:
                self.scan_file(p)
        categories: dict[str, int] = {}
        for f in self.findings: categories[f.category] = categories.get(f.category, 0) + 1
        return {"schema": VERSION, "scope": "static Python AST discovery; not a semantic or physical-world proof",
                "files_with_errors": len(self.errors), "errors": self.errors,
                "finding_count": len(self.findings), "categories": dict(sorted(categories.items())),
                "findings": [asdict(f) for f in self.findings]}

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Python files or directories to scan")
    parser.add_argument("--json", dest="json_path", help="write full report as JSON")
    args = parser.parse_args()
    report = MathGrep().scan(args.paths)
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if args.json_path: Path(args.json_path).write_text(encoded + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("schema", "scope", "files_with_errors", "finding_count", "categories")}, indent=2))
    return 1 if report["files_with_errors"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
