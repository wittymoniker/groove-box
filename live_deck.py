"""live_deck.py — LIVE DECK panel for the empty space under GLOBAL SEED.

GROOVEBOX_R123_LIVE_DECK_20261119

* Performance pads: one pad per live-performance binding in live_keys (label + key), so every
  live shortcut is also a touch / mouse pad. Pads call exactly the same function as the key.
* Heavy commands: the Ctrl+Shift commands as buttons, sharing the 1.5 s debounce.
* Machine meters: CPU and RAM use, transport state and BPM (1 s refresh, only while visible).
* Hybrid sCode pool: which language each kernel uses now (C / Go / LuaJIT / Rust / C++ / Julia /
  NumPy). Probed on a background thread every 6 s so the UI never waits on a toolchain.
* Incoming routes of the selected instrument (patch cables, Patch Motion, sidechain).
"""
from __future__ import annotations

import os
import threading
import time

MARKER = "GROOVEBOX_R123_LIVE_DECK_20261119"


# ---------------------------------------------------------------- machine meters
class _Cpu:
    def __init__(self):
        self.prev = None

    def percent(self):
        try:
            import psutil
            return float(psutil.cpu_percent(interval=None))
        except Exception:
            pass
        try:
            with open("/proc/stat") as f:
                parts = [float(x) for x in f.readline().split()[1:]]
            idle, total = parts[3] + (parts[4] if len(parts) > 4 else 0.0), sum(parts)
            if self.prev is None:
                self.prev = (idle, total); return 0.0
            di, dt = idle - self.prev[0], total - self.prev[1]; self.prev = (idle, total)
            return max(0.0, min(100.0, 100.0 * (1.0 - di / dt))) if dt > 0 else 0.0
        except Exception:
            pass
        try:
            return min(100.0, 100.0 * os.getloadavg()[0] / max(1, os.cpu_count() or 1))
        except Exception:
            return 0.0


def ram_percent():
    try:
        import psutil
        return float(psutil.virtual_memory().percent)
    except Exception:
        pass
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1); info[k] = float(v.split()[0])
        return 100.0 * (1.0 - info.get("MemAvailable", info.get("MemFree", 0.0)) / max(1.0, info["MemTotal"]))
    except Exception:
        return 0.0


def hybrid_summary():
    """'kernel: backend' for every kernel's chosen language (falls back to the ready list)."""
    import hybrid_runtime as hr
    rows = []
    for n, row in hr.kernel_matrix().items():
        chosen = [b for b, v in row.items() if "chosen" in str(v)]
        ready = [b for b, v in row.items() if v == "ready"]
        rows.append(f"{n}: {', '.join(chosen) if chosen else 'numpy'}" + (f"  (ready: {', '.join(ready)})" if ready else ""))
    return "\n".join(rows) or "no kernels registered"


# ---------------------------------------------------------------- widget
def build(app):
    from PyQt6.QtCore import QTimer, Qt
    from PyQt6.QtWidgets import (QGroupBox, QGridLayout, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                                 QProgressBar, QSizePolicy)
    import live_keys

    box = QGroupBox("🎛 LIVE DECK · performance pads · heavy commands · machine · sCode pool · routes")
    box.setObjectName("liveDeck")
    box.setStyleSheet(
        "#liveDeck { color:#ffd98a; background:transparent; border:1px solid #6a5a2f; border-radius:7px; margin-top:6px;"
        " padding-top:10px; font-weight:900; } #liveDeck::title { subcontrol-origin:margin; left:8px; padding:0 5px; }"
        " #liveDeck QPushButton { background:#1a2430; color:#eaf2fa; border:1px solid #44607a; border-radius:7px;"
        " padding:4px; font-weight:800; font-size:8pt; min-height:40px; }"
        " #liveDeck QPushButton:pressed { background:#2c4a66; }"
        " #liveDeck QPushButton[heavy=\"true\"] { border-color:#a8743a; color:#ffd9a8; }"
        " #liveDeck QLabel { color:#cfdde9; font-size:8pt; }")
    box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    v = QVBoxLayout(box); v.setContentsMargins(8, 12, 8, 8); v.setSpacing(6)

    binds = live_keys.bindings(app)
    seen = set()
    pads = QGridLayout(); pads.setSpacing(4)
    i = 0
    for group, key, label, fn, heavy in binds:
        if heavy or label in seen:
            continue                      # one pad per action (alternate keys are listed in its tooltip)
        seen.add(label)
        alts = [k for g, k, lab, *_ in binds if lab == label]
        b = QPushButton(f"{label}\n{alts[0]}")
        b.setToolTip(f"{label} · keys: {' / '.join(alts)}")
        b.clicked.connect(lambda _c=False, f=fn: f())
        pads.addWidget(b, i // 6, i % 6); i += 1
    v.addWidget(QLabel("PERFORMANCE PADS (same as the Alt keys · Ctrl+/ lists every key)"))
    v.addLayout(pads)

    heavy_row = QGridLayout(); heavy_row.setSpacing(4)
    last = {"t": 0.0}

    def _heavy(f):
        now = time.monotonic()
        if now - last["t"] < 1.5:
            return
        last["t"] = now; f()

    j = 0
    for group, key, label, fn, heavy in binds:
        if not heavy:
            continue
        b = QPushButton(f"{label}\n{key}"); b.setProperty("heavy", True)
        b.setToolTip(f"{label} · {key} · heavy: debounced so a double tap never queues two renders")
        b.clicked.connect(lambda _c=False, f=fn: _heavy(f))
        heavy_row.addWidget(b, j // 5, j % 5); j += 1
    v.addWidget(QLabel("HEAVY COMMANDS (Ctrl+Shift)"))
    v.addLayout(heavy_row)

    meters = QHBoxLayout(); meters.setSpacing(8)
    cpu_bar, ram_bar = QProgressBar(), QProgressBar()
    for bar, name in ((cpu_bar, "CPU"), (ram_bar, "RAM")):
        bar.setRange(0, 100); bar.setFormat(name + " %p%"); bar.setTextVisible(True); bar.setMinimumHeight(22)
        meters.addWidget(bar, 1)
    state = QLabel("—"); state.setMinimumWidth(220); meters.addWidget(state, 1)
    v.addLayout(meters)

    cols = QHBoxLayout(); cols.setSpacing(8)
    pool = QLabel("sCode pool: probing…"); pool.setWordWrap(True); pool.setAlignment(Qt.AlignmentFlag.AlignTop)
    pool.setToolTip("Language each hybrid kernel runs in right now. Every language is parity-checked against "
                    "NumPy before it is used; a mismatch keeps NumPy.")
    routes = QLabel("—"); routes.setWordWrap(True); routes.setAlignment(Qt.AlignmentFlag.AlignTop)
    routes.setToolTip("Routes landing on the selected instrument: patch cables, Patch Motion and sidechain.")
    for w in (pool, routes):
        w.setStyleSheet("background:#0b131b; border:1px solid #26384a; border-radius:5px; padding:4px; font-family:monospace;")
        cols.addWidget(w, 1)
    v.addLayout(cols, 1)

    cpu = _Cpu()
    hyb = {"text": "sCode pool: probing…", "busy": False, "t": 0.0}

    def _probe():
        try:
            hyb["text"] = "sCode pool (kernel: language)\n" + hybrid_summary()
        except Exception as exc:
            hyb["text"] = f"sCode pool unavailable: {exc}"
        hyb["busy"] = False

    def tick():
        if not box.isVisible():
            return
        cpu_bar.setValue(int(cpu.percent())); ram_bar.setValue(int(ram_percent()))
        try:
            bpm = float(app.spin_bpm.value())
        except Exception:
            bpm = 0.0
        lbl = getattr(app, "lbl_perf_state", None)
        state.setText(f"BPM {bpm:g} · " + (lbl.text() if lbl is not None else "—"))
        now = time.monotonic()
        if not hyb["busy"] and now - hyb["t"] > 6.0:
            hyb["busy"] = True; hyb["t"] = now
            threading.Thread(target=_probe, name="live-deck-pool", daemon=True).start()
        pool.setText(hyb["text"])
        try:
            import route_handles
            dd = getattr(app, "instrument_selector_dropdown", None)
            name = dd.currentText() if dd is not None else ""
            inc = route_handles.incoming_routes(app, name) if name else []
            routes.setText(f"Routes into {name or '—'}: {len(inc)}\n" +
                           "\n".join(f"  ← {s}  {w:.2f}  {k}" for s, w, k in inc[:12]) +
                           ("\n  …" if len(inc) > 12 else ""))
        except Exception as exc:
            routes.setText(f"routes unavailable: {exc}")

    t = QTimer(box); t.setInterval(1000); t.timeout.connect(tick); t.start()
    QTimer.singleShot(300, tick)
    app.live_deck_group = box
    return box
