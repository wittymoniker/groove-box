"""GROOVEBOX_R124_GAME_EXPORT_CHECK: headless smoke run of an exported game before it ships.

``check(game_dir, seconds=8)`` launches the exported entry point (main.py / game.py / run.py) with
SDL/Qt dummy video+audio drivers and GROOVEBOX_GAME_CHECK=1, waits ``seconds``, then reports:
    started, exit code / crash, stderr tail, frame-time stats (if the game prints "FRAME <ms>" lines or
    writes game_check.json), audio dropouts ("XRUN"/"underrun" lines), missing assets (files referenced
    in the sources that don't exist in the export).
Nothing is modified in the export.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ENTRY = ("main.py", "game.py", "run.py", "__main__.py")
ASSET_RE = re.compile(r"""['"]([\w./\\-]+\.(?:png|jpg|jpeg|gif|wav|ogg|mp3|flac|ttf|otf|json|obj|glsl|frag|vert))['"]""", re.I)


def find_entry(game_dir):
    d = Path(game_dir)
    for e in ENTRY:
        if (d / e).is_file():
            return d / e
    py = sorted(d.glob("*.py"))
    return py[0] if py else None


def missing_assets(game_dir):
    d = Path(game_dir); missing = set()
    for src in d.rglob("*.py"):
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in ASSET_RE.findall(text):
            rel = m.replace("\\", "/")
            if not ((src.parent / rel).exists() or (d / rel).exists()):
                missing.add(rel)
    return sorted(missing)


def check(game_dir, seconds=8.0, python=None):
    d = Path(game_dir)
    entry = find_entry(d)
    rep = {"game_dir": str(d), "entry": str(entry) if entry else None, "started": False, "crashed": False,
           "exit_code": None, "seconds": seconds, "frame_ms": None, "xruns": 0, "missing_assets": missing_assets(d),
           "stderr_tail": ""}
    if entry is None:
        rep["error"] = "no entry point (main.py / game.py / run.py)"
        return rep
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", QT_QPA_PLATFORM="offscreen",
               GROOVEBOX_GAME_CHECK="1", PYTHONDONTWRITEBYTECODE="1")
    t0 = time.time()
    try:
        p = subprocess.Popen([python or sys.executable, str(entry)], cwd=str(d), env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as exc:
        rep["error"] = f"launch failed: {exc}"
        return rep
    rep["started"] = True
    try:
        out, err = p.communicate(timeout=seconds)
    except subprocess.TimeoutExpired:
        p.terminate()
        try:
            out, err = p.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            p.kill(); out, err = p.communicate()
        rep["exit_code"] = None          # still running at the deadline = healthy
    else:
        rep["exit_code"] = p.returncode
        rep["crashed"] = p.returncode not in (0, None) and (time.time() - t0) < seconds
    text = (out or "") + "\n" + (err or "")
    frames = [float(x) for x in re.findall(r"FRAME\s+([0-9.]+)", text)]
    jf = d / "game_check.json"
    if jf.is_file():
        try:
            frames += [float(x) for x in json.loads(jf.read_text()).get("frame_ms", [])]
        except Exception:
            pass
    if frames:
        frames.sort()
        rep["frame_ms"] = {"n": len(frames), "median": frames[len(frames) // 2],
                           "p95": frames[min(len(frames) - 1, int(len(frames) * 0.95))], "max": frames[-1]}
    rep["xruns"] = len(re.findall(r"xrun|underrun|dropout", text, re.I))
    rep["stderr_tail"] = "\n".join((err or "").strip().splitlines()[-12:])
    rep["ok"] = rep["started"] and not rep["crashed"] and not rep["missing_assets"] and \
        "Traceback" not in (err or "")
    return rep
