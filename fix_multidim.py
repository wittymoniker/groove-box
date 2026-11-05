#!/usr/bin/env python3
"""One-shot repair for multidim_ui.py (main + BUILD_ISO overlay copy).

Fixes, each verified against the file contents before touching anything:
  1. wheelEvent on MD3DView: ignore (drag-only orbit) -> scroll area receives wheel.
  2. paintEvent on MD3DView: define w / h before the radial gradient (NameError).
  3. Overlay copy: collapse duplicated `w = ...` / `h = ...` lines from the sed output.
  4. paintEvent on MD3DView: wrap body in try/finally so qp.end() always runs;
     a non-Qt exception inside paint can no longer leave an active painter
     (that active-painter state is what turns into "UI gone" + segfault).
Refuses to run if the expected patterns are not found exactly once.
"""
from __future__ import annotations
import pathlib, re, sys

TARGETS = [
    "multidim_ui.py",
    "BUILD_ISO/app-overlay-v35.22zz/multidim_ui.py",
]

# --- 1. wheelEvent: drag-only ------------------------------------------------
OLD_WHEEL = (
    "    def wheelEvent(self, e):\n"
    "        # scroll = yaw (instead of zoom)\n"
    "        delta = e.angleDelta().y()\n"
    "        self.yaw += (delta / 120.0) * 0.08\n"
    "        self.update()\n"
)
NEW_WHEEL = (
    "    def wheelEvent(self, e):\n"
    "        # DRAG-ONLY_20261103: wheel scrolls the containing panel.\n"
    "        # Orbit is left-mouse drag only; no wheel yaw, no wheel zoom.\n"
    "        e.ignore()\n"
)

# --- 2 + 4. paintEvent: w/h before gradient, plus try/finally ---------------
# Matches whichever starting form the file currently has: the broken one
# (no w/h) or the fixed one (with w/h). Normalises to the guarded form.
PAINT_HEAD_OLD_BROKEN = (
    "    @_safe_paint\n"
    "    def paintEvent(self, _e):\n"
    "        qp = _safe_begin_painter(self)\n"
    "        if qp is None:\n"
    "            return\n"
    "        qp.setRenderHint(QPainter.RenderHint.Antialiasing)\n"
    "        g = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * 0.72)\n"
)
PAINT_HEAD_OLD_FIXED = (
    "    @_safe_paint\n"
    "    def paintEvent(self, _e):\n"
    "        qp = _safe_begin_painter(self)\n"
    "        w = float(self.width())\n"
    "        h = float(self.height())\n"
    "        if qp is None:\n"
    "            return\n"
    "        qp.setRenderHint(QPainter.RenderHint.Antialiasing)\n"
    "        g = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * 0.72)\n"
)
PAINT_HEAD_NEW = (
    "    @_safe_paint\n"
    "    def paintEvent(self, _e):\n"
    "        qp = _safe_begin_painter(self)\n"
    "        if qp is None:\n"
    "            return\n"
    "        try:\n"
    "            w = float(self.width())\n"
    "            h = float(self.height())\n"
    "            qp.setRenderHint(QPainter.RenderHint.Antialiasing)\n"
    "            g = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * 0.72)\n"
)

# Where MD3DView.paintEvent ends: the trailing hint text is the last statement.
# Indent it under the new try: block.
PAINT_TAIL_OLD = (
    "        qp.drawText(8, h - 8, \"drag = orbit · scroll = yaw · inertia on release\")\n"
)
PAINT_TAIL_NEW = (
    "            qp.drawText(8, h - 8, \"drag = orbit · wheel = scroll · inertia on release\")\n"
    "        finally:\n"
    "            if qp.isActive():\n"
    "                qp.end()\n"
)

def fix_paint_body(text: str) -> tuple[str, str]:
    """Re-indent the whole MD3DView.paintEvent body under the try: we added.

    Between the PAINT_HEAD_NEW marker and PAINT_TAIL_OLD there is the rest of
    the paintEvent body (currently at 8-space indent). We add 4 spaces to every
    non-empty line in that range so it sits inside the try: block.
    """
    head = text.find(PAINT_HEAD_NEW)
    if head < 0:
        return text, "paint head not inserted"
    body_start = head + len(PAINT_HEAD_NEW)
    tail = text.find(PAINT_TAIL_OLD, body_start)
    if tail < 0:
        return text, "paint tail not found"
    body = text[body_start:tail]
    reindented = "".join(
        ("    " + ln if ln.strip() else ln) for ln in body.splitlines(True)
    )
    return text[:body_start] + reindented + PAINT_TAIL_NEW + text[tail + len(PAINT_TAIL_OLD):], "ok"

def patch(path: pathlib.Path) -> None:
    src = path.read_text(encoding="utf-8")
    orig = src

    # 1. wheelEvent
    n = src.count(OLD_WHEEL)
    if n == 1:
        src = src.replace(OLD_WHEEL, NEW_WHEEL)
    elif n == 0 and NEW_WHEEL in src:
        pass  # already patched
    else:
        raise SystemExit(f"{path}: wheelEvent match count {n} (expected 0 or 1)")

    # 2 + 4. paintEvent head — accept broken or fixed, both become NEW
    if PAINT_HEAD_NEW in src:
        pass  # already fully patched
    elif PAINT_HEAD_OLD_FIXED in src:
        src = src.replace(PAINT_HEAD_OLD_FIXED, PAINT_HEAD_NEW, 1)
        src, status = fix_paint_body(src)
        if status != "ok":
            raise SystemExit(f"{path}: reindent failed: {status}")
    elif PAINT_HEAD_OLD_BROKEN in src:
        src = src.replace(PAINT_HEAD_OLD_BROKEN, PAINT_HEAD_NEW, 1)
        src, status = fix_paint_body(src)
        if status != "ok":
            raise SystemExit(f"{path}: reindent failed: {status}")
    else:
        raise SystemExit(f"{path}: paintEvent head not recognised (neither broken nor fixed form)")

    # 3. Collapse duplicated `w = ...` / `h = ...` lines inside the overlay copy.
    dup = (
        "            w = float(self.width())\n"
        "            h = float(self.height())\n"
        "            w = float(self.width())\n"
        "            h = float(self.height())\n"
    )
    if dup in src:
        src = src.replace(dup,
            "            w = float(self.width())\n"
            "            h = float(self.height())\n", 1)

    if src == orig:
        print(f"{path}: no changes needed")
        return
    path.write_text(src, encoding="utf-8")
    print(f"{path}: patched")

def main() -> int:
    root = pathlib.Path.cwd()
    any_hit = False
    for rel in TARGETS:
        p = root / rel
        if not p.is_file():
            print(f"{rel}: missing, skipping")
            continue
        patch(p)
        any_hit = True
    if not any_hit:
        print("no target files found in cwd; run from the project root")
        return 1
    # clear stale bytecode so the running process picks up the change
    for d in root.rglob("__pycache__"):
        for f in d.glob("*.pyc"):
            try: f.unlink()
            except OSError: pass
        try: d.rmdir()
        except OSError: pass
    for f in root.rglob("*.pyc"):
        try: f.unlink()
        except OSError: pass
    print("bytecode cache cleared")
    return 0

if __name__ == "__main__":
    sys.exit(main())