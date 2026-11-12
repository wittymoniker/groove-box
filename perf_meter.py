"""PERF_METER_20261112: live CPU and memory for the session."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import QTimer
import os

def _read():
    cpu, mem = 0.0, 0.0
    try:
        with open("/proc/stat") as f:
            parts = f.readline().split()
            idle, total = int(parts[4]), sum(int(x) for x in parts[1:])
            cpu = 100.0 * (1.0 - idle / max(1, total))
    except Exception:
        pass
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":")
                info[k.strip()] = int(v.split()[0])
        mem = 100.0 * (1.0 - info.get("MemAvailable", 0) / max(1, info.get("MemTotal", 1)))
    except Exception:
        pass
    return cpu, mem

def open_window(app, parent=None):
    w = QWidget(parent)
    w.setWindowTitle("Performance")
    w.setMinimumSize(280, 140)
    lay = QVBoxLayout(w)
    cpu_bar, mem_bar = QProgressBar(), QProgressBar()
    cpu_lbl, mem_lbl = QLabel("CPU"), QLabel("Memory")
    for bar in (cpu_bar, mem_bar):
        bar.setRange(0, 100)
    lay.addWidget(cpu_lbl); lay.addWidget(cpu_bar)
    lay.addWidget(mem_lbl); lay.addWidget(mem_bar)
    def tick():
        c, m = _read()
        cpu_bar.setValue(int(c)); mem_bar.setValue(int(m))
        cpu_lbl.setText("CPU  %.0f%%" % c); mem_lbl.setText("Memory  %.0f%%" % m)
    t = QTimer(w); t.setInterval(1500); t.timeout.connect(tick); t.start(); tick()
    w.show(); w.raise_()
    return w
