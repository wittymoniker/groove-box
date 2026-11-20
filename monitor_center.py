"""R122 Monitoring & Diagnostics Center.

Read-only system/application telemetry with a few deliberately conservative controls.
Sampling is timer-driven and bounded; it never runs in an audio callback and never
changes the audio engine's scheduling or device state.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import time
from datetime import datetime

from PyQt6.QtCore import QSettings, QTimer
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)


def _fmt_bytes(value):
    try:
        n = float(value)
    except Exception:
        return "—"
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    for unit in units:
        if abs(n) < 1024 or unit == units[-1]:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TiB"


def _read_cpu_stat():
    try:
        with open("/proc/stat", "r", encoding="ascii") as fh:
            vals = [int(x) for x in fh.readline().split()[1:]]
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        return sum(vals), idle
    except Exception:
        return None


def _cpu_percent(previous):
    current = _read_cpu_stat()
    if current is None or previous is None:
        return None, current
    total = current[0] - previous[0]
    idle = current[1] - previous[1]
    if total <= 0:
        return None, current
    return max(0.0, min(100.0, 100.0 * (1.0 - idle / total))), current


def _temperatures():
    found = []
    root = "/sys/class/thermal"
    try:
        names = sorted(n for n in os.listdir(root) if n.startswith("thermal_zone"))
    except Exception:
        names = []
    for name in names[:12]:
        base = os.path.join(root, name)
        try:
            raw = int(open(os.path.join(base, "temp"), "r", encoding="ascii").read().strip())
            value = raw / 1000.0 if abs(raw) > 1000 else float(raw)
            label = open(os.path.join(base, "type"), "r", encoding="utf-8", errors="replace").read().strip()
            found.append((label or name, f"{value:.1f} °C"))
        except Exception:
            continue
    return found


def _system_uptime():
    try:
        seconds = float(open("/proc/uptime", "r", encoding="ascii").read().split()[0])
        days, rem = divmod(int(seconds), 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        return f"{days}d {hours}h {minutes}m"
    except Exception:
        return "Unavailable"


def _process_threads():
    try:
        return len(os.listdir("/proc/self/task"))
    except Exception:
        return None


def _network_counters():
    rows = []
    root = "/sys/class/net"
    try:
        names = sorted(os.listdir(root))
    except Exception:
        names = []
    for name in names:
        if name == "lo":
            continue
        base = os.path.join(root, name, "statistics")
        try:
            rx = int(open(os.path.join(base, "rx_bytes"), "r", encoding="ascii").read().strip())
            tx = int(open(os.path.join(base, "tx_bytes"), "r", encoding="ascii").read().strip())
            rows.append({"interface": name, "rx_bytes": rx, "tx_bytes": tx})
        except Exception:
            continue
    return rows


def _battery_status():
    root = "/sys/class/power_supply"
    try:
        names = os.listdir(root)
    except Exception:
        return []
    out = []
    for name in names:
        base = os.path.join(root, name)
        try:
            typ = open(os.path.join(base, "type"), "r", encoding="ascii").read().strip()
            if typ != "Battery":
                continue
            def read(field):
                try:
                    return open(os.path.join(base, field), "r", encoding="utf-8", errors="replace").read().strip()
                except Exception:
                    return ""
            out.append({"name": name, "capacity": read("capacity"), "status": read("status"),
                        "health": read("health")})
        except Exception:
            continue
    return out


def _process_memory():
    try:
        with open("/proc/self/status", "r", encoding="ascii", errors="replace") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except Exception:
        pass
    try:
        import resource
        n = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return n if platform.system() == "Darwin" else n * 1024
    except Exception:
        return None


def _memory_snapshot():
    try:
        from memory_guard import snapshot
        s = snapshot(force=True)
        return s
    except Exception:
        return {}


def collect_snapshot(app=None, previous_cpu=None):
    """Collect a compact, best-effort snapshot. Missing sensors are reported as unavailable."""
    cpu, next_cpu = _cpu_percent(previous_cpu)
    snap = _memory_snapshot()
    result = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "host": platform.node() or "unknown",
        "platform": platform.platform(),
        "cpu_percent": cpu,
        "cpu_cores": os.cpu_count() or 1,
        "memory": snap,
        "process_rss": _process_memory(),
        "process_threads": _process_threads(),
        "uptime": _system_uptime(),
        "temperatures": _temperatures(),
        "batteries": _battery_status(),
        "network": _network_counters(),
        "disks": [],
        "pools": {},
        "exports": [],
        "audio": {},
        "plugins": [],
        "signal_io": {"endpoints": [], "routes": {}},
        "ui_stalls": [],
        "notes": [],
    }
    for path, label in (("/", "Root"), (os.path.expanduser("~"), "Home")):
        try:
            u = shutil.disk_usage(path)
            result["disks"].append({"name": label, "path": path, "total": u.total,
                                    "used": u.used, "free": u.free,
                                    "percent": 100.0 * u.used / max(1, u.total)})
        except Exception as exc:
            result["notes"].append(f"Disk {label}: {exc}")
    try:
        import thread_budget
        result["pools"] = {
            "budget": thread_budget.scheduler_budget(),
            "lanes": thread_budget.lane_report(limit=30),
            "streamable": bool(getattr(thread_budget, "streamable_enabled", lambda: True)()),
        }
    except Exception as exc:
        result["notes"].append(f"Worker pools unavailable: {exc}")
    if app is not None:
        try:
            scheduler = getattr(app, "_export_scheduler_obj", None)
            jobs = getattr(scheduler, "jobs", []) if scheduler is not None else []
            for job in list(jobs or [])[-100:]:
                result["exports"].append({
                    "name": str(getattr(job, "name", "Export")),
                    "state": str(getattr(job, "state", "?")),
                    "progress": int(getattr(job, "progress", 0) or 0),
                    "error": str(getattr(job, "error", "") or ""),
                })
        except Exception as exc:
            result["notes"].append(f"Export scheduler unavailable: {exc}")
        for attr in ("_audio_meters", "audio_meters", "_diagnostic_meters", "_live_meters"):
            value = getattr(app, attr, None)
            if isinstance(value, dict):
                result["audio"] = value
                break
        for attr in ("_plugin_hosts", "plugin_hosts", "_plugin_processes"):
            value = getattr(app, attr, None)
            if isinstance(value, (dict, list, tuple)):
                result["plugins"] = [str(x) for x in (value.keys() if isinstance(value, dict) else value)]
                break
        try:
            router = getattr(app, "_universal_signal_router", None)
            if router is not None:
                result["signal_io"] = {
                    "endpoints": [{"name": ep.name, "direction": ep.direction, "kind": ep.kind,
                                   "connected": bool(ep.connected)} for ep in router.endpoints.values()],
                    "routes": router.diagnostics(),
                }
        except Exception as exc:
            result["notes"].append(f"Signal I/O telemetry unavailable: {exc}")
    try:
        import ui_stall_watch
        result["ui_stalls"] = ui_stall_watch.report(20)
    except Exception:
        pass
    result["self_tests"] = engine_self_tests()
    return result, next_cpu


_SELF_TESTS = {"t": 0.0, "rows": []}


def engine_self_tests(max_age_s: float = 300.0, force: bool = False):
    """GROOVEBOX_R123_ENGINE_SELF_TESTS_20261119: carrier bridge (any-signal → any-context routes +
    determinism) and the Meum spectrum (book FFT vs NumPy, exact inverse, α = 0 identity).
    Cached for 5 minutes so the 1-s refresh stays cheap. Rows: (name, ok, detail)."""
    import time as _t
    if not force and _SELF_TESTS["rows"] and _t.monotonic() - _SELF_TESTS["t"] < max_age_s:
        return _SELF_TESTS["rows"]
    rows = []
    try:
        import carrier_bridge as cb
        probs = cb.validate()
        rows.append(("Carrier bridge routes", not probs, "all kinds reach every context" if not probs else "; ".join(probs[:4])))
        probs = cb.verify_guarantee(None)
        rows.append(("Seed-only guarantee", not probs, "deterministic (same SHA-256 twice)" if not probs else "; ".join(probs[:4])))
    except Exception as exc:
        rows.append(("Carrier bridge", False, f"{type(exc).__name__}: {exc}"))
    try:
        import meum_spectrum as ms
        r = ms.self_test()
        worst = max((v for k, v in r.items() if k != "ok"), default=0.0)
        rows.append(("Meum spectrum (FFT)", bool(r.get("ok")), f"worst error {worst:.2e} (limit 1e-9)"))
    except Exception as exc:
        rows.append(("Meum spectrum (FFT)", False, f"{type(exc).__name__}: {exc}"))
    _SELF_TESTS.update(t=_t.monotonic(), rows=rows)
    return rows


class MonitorCenter(QDialog):
    def __init__(self, app=None, parent=None):
        super().__init__(parent or app)
        self.app = app
        self.setWindowTitle("Groovebox · Monitoring & Diagnostics")
        self.resize(900, 650)
        self.setMinimumSize(680, 460)
        self.settings = QSettings("MathematiciansGroovebox", "MonitorCenter")
        self._previous_cpu = _read_cpu_stat()
        self._last_snapshot = {}
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        interval = int(self.settings.value("interval_ms", 2000))
        self.interval.setCurrentIndex(max(0, self.interval.findData(interval)))
        self.auto_refresh.setChecked(str(self.settings.value("auto_refresh", "true")).lower() in ("1", "true", "yes"))
        self._apply_timer()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        self.status = QLabel("Collecting system telemetry…")
        self.status.setStyleSheet("font-weight:700; color:#91d9bd;")
        header.addWidget(self.status, 1)
        self.auto_refresh = QCheckBox("Live refresh")
        self.auto_refresh.toggled.connect(self._apply_timer)
        header.addWidget(self.auto_refresh)
        self.interval = QComboBox()
        for label, ms in (("1 s", 1000), ("2 s", 2000), ("5 s", 5000), ("10 s", 10000)):
            self.interval.addItem(label, ms)
        self.interval.currentIndexChanged.connect(self._apply_timer)
        header.addWidget(self.interval)
        root.addLayout(header)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.metrics = QTableWidget(0, 3)
        self.metrics.setHorizontalHeaderLabels(["Monitor", "Reading", "Status / notes"])
        self.metrics.horizontalHeader().setStretchLastSection(True)
        self.metrics.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.metrics.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.metrics.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabs.addTab(self.metrics, "System")

        self.activity = QTableWidget(0, 4)
        self.activity.setHorizontalHeaderLabels(["Subsystem", "Name", "State", "Details"])
        self.activity.horizontalHeader().setStretchLastSection(True)
        self.activity.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabs.addTab(self.activity, "Workers & Exports")

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.tabs.addTab(self.details, "Diagnostics")

        controls = QGroupBox("Safe controls")
        grid = QGridLayout(controls)
        self.limit_migration = QCheckBox("Constrain adaptive worker migration to one worker")
        self.limit_migration.setToolTip("Advisory scheduling limit for migratory work only. Does not pause jobs or alter the audio callback.")
        try:
            import thread_budget
            saved_limit = self.settings.value("constrain_migration", None)
            constrained = (str(saved_limit).lower() in ("1", "true", "yes")
                           if saved_limit is not None else not thread_budget.streamable_enabled())
            self.limit_migration.setChecked(constrained)
            thread_budget.set_streamable(not constrained)
        except Exception:
            self.limit_migration.setEnabled(False)
        self.limit_migration.toggled.connect(self._set_migration)
        grid.addWidget(self.limit_migration, 0, 0, 1, 2)
        grid.addWidget(QLabel("This setting affects future scheduling decisions; active work is not interrupted."), 1, 0, 1, 2)
        root.addWidget(controls)

        buttons = QHBoxLayout()
        refresh = QPushButton("Refresh now")
        refresh.clicked.connect(self.refresh)
        stalls = QPushButton("UI stall report")
        stalls.clicked.connect(self._open_stalls)
        copy = QPushButton("Copy report")
        copy.clicked.connect(self._copy_report)
        save = QPushButton("Save report…")
        save.clicked.connect(self._save_report)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        for b in (refresh, stalls, copy, save):
            buttons.addWidget(b)
        buttons.addStretch(1)
        buttons.addWidget(close)
        root.addLayout(buttons)

    def _apply_timer(self, *_):
        ms = int(self.interval.currentData() or 2000)
        self.settings.setValue("interval_ms", ms)
        self.settings.setValue("auto_refresh", self.auto_refresh.isChecked())
        if self.auto_refresh.isChecked():
            self._timer.start(ms)
        else:
            self._timer.stop()

    def _set_migration(self, constrained):
        try:
            import thread_budget
            thread_budget.set_streamable(not bool(constrained))
            self.settings.setValue("constrain_migration", bool(constrained))
            self.status.setText("Adaptive migration constrained" if constrained else "Adaptive migration enabled")
        except Exception as exc:
            QMessageBox.warning(self, "Worker setting", str(exc))

    def _add_metric(self, name, value, note=""):
        row = self.metrics.rowCount()
        self.metrics.insertRow(row)
        for col, text in enumerate((name, value, note)):
            self.metrics.setItem(row, col, QTableWidgetItem(str(text)))

    def refresh(self):
        try:
            data, self._previous_cpu = collect_snapshot(self.app, self._previous_cpu)
            self._last_snapshot = data
            self.metrics.setRowCount(0)
            cpu = data.get("cpu_percent")
            self._add_metric("CPU utilization", f"{cpu:.1f}%" if cpu is not None else "Unavailable", f"{data['cpu_cores']} logical CPUs")
            mem = data.get("memory", {})
            self._add_metric("System memory available", _fmt_bytes(mem.get("available")), f"of {_fmt_bytes(mem.get('total'))}; reserve {_fmt_bytes(mem.get('reserve'))}")
            self._add_metric("Process resident memory", _fmt_bytes(data.get("process_rss")), "Groovebox process RSS")
            self._add_metric("Process threads", str(data.get("process_threads") or "—"), "Threads owned by Groovebox process")
            self._add_metric("System uptime", data.get("uptime", "Unavailable"), "Host uptime")
            for battery in data.get("batteries", []):
                self._add_metric(f"Battery · {battery.get('name')}", f"{battery.get('capacity') or '—'}%",
                                 f"{battery.get('status') or 'status unknown'} · {battery.get('health') or 'health unknown'}")
            for net in data.get("network", []):
                self._add_metric(f"Network · {net['interface']}", f"RX {_fmt_bytes(net['rx_bytes'])}",
                                 f"TX {_fmt_bytes(net['tx_bytes'])} · cumulative interface counters")
            for disk in data.get("disks", []):
                self._add_metric(f"Disk · {disk['name']}", f"{disk['percent']:.1f}% used", f"{_fmt_bytes(disk['free'])} free of {_fmt_bytes(disk['total'])}")
            temps = data.get("temperatures", [])
            if temps:
                for label, value in temps:
                    self._add_metric(f"Temperature · {label}", value, "Kernel thermal-zone sensor")
            else:
                self._add_metric("Temperature sensors", "Unavailable", "No readable thermal-zone sensors found")
            budget = data.get("pools", {}).get("budget", {})
            if budget:
                self._add_metric("Worker budget", str(budget.get("total_workers", "—")),
                                 f"bulk {budget.get('bulk_workers', '—')} · interactive {budget.get('interactive_workers', '—')} · engine {budget.get('engine_workers', '—')}")
            self._add_metric("UI stalls", str(len(data.get("ui_stalls", []))), "Recent recorded slow UI call sites")
            sio = data.get("signal_io", {})
            self._add_metric("Signal I/O", f"{len(sio.get('endpoints', []))} endpoints / {len(sio.get('routes', {}))} routes",
                             "Registered routes; packet/drop counters appear under Workers & Exports")
            self._fill_activity(data)
            self.details.setPlainText(json.dumps(data, indent=2, default=str))
            self.status.setText(f"Updated {data['timestamp']} · {data['host']}")
        except Exception as exc:
            self.status.setText(f"Monitor refresh failed: {exc}")

    def _fill_activity(self, data):
        self.activity.setRowCount(0)
        def add(subsystem, name, state, details):
            r = self.activity.rowCount(); self.activity.insertRow(r)
            for c, value in enumerate((subsystem, name, state, details)):
                self.activity.setItem(r, c, QTableWidgetItem(str(value)))
        pools = data.get("pools", {}).get("lanes", {})
        lanes = pools.get("lanes", []) if isinstance(pools, dict) else []
        for lane in lanes:
            add("Worker lane", lane.get("name", "lane"),
                f"{lane.get('active', 0)} active / {lane.get('queued', 0)} queued",
                f"{lane.get('kind', '?')} · wait {lane.get('wait_s', 0)} s · run {lane.get('run_s', 0)} s")
        for job in data.get("exports", []):
            add("Export", job.get("name", "job"), f"{job.get('state')} · {job.get('progress')}%", job.get("error", ""))
        for plugin in data.get("plugins", []):
            add("Plugin host", plugin, "Registered", "Host status is not exposed by this plugin adapter")
        audio = data.get("audio", {})
        if isinstance(audio, dict):
            for name, reading in list(audio.items())[:40]:
                add("Audio meter", name, "Live telemetry", str(reading)[:240])
        signal_io = data.get("signal_io", {})
        for endpoint in signal_io.get("endpoints", []):
            add("Signal endpoint", endpoint.get("name", "endpoint"),
                "Connected" if endpoint.get("connected") else "Disconnected",
                f"{endpoint.get('direction')} · {endpoint.get('kind')}")
        for route_id, route in signal_io.get("routes", {}).items():
            add("Signal route", f"{route.get('source')} → {route.get('destination')}",
                "Connected" if route.get("connected") else "Disconnected",
                f"{route.get('packets', 0)} packets · {route.get('dropped', 0)} dropped · {route.get('buffered', 0)} buffered")
        for name, ok, detail in data.get("self_tests", []):
            add("Self-test", name, "Pass" if ok else "FAIL", detail)
        if self.activity.rowCount() == 0:
            add("Activity", "No active worker lanes or export jobs", "Idle", "Refresh again while work is running")

    def _report_text(self):
        return json.dumps(self._last_snapshot, indent=2, default=str) + "\n"

    def _copy_report(self):
        try:
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(self._report_text())
            self.status.setText("Diagnostic report copied to clipboard")
        except Exception as exc:
            QMessageBox.warning(self, "Copy report", str(exc))

    def _save_report(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Groovebox Monitor Report", "groovebox-monitor-report.json", "JSON (*.json);;Text (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self._report_text())
            self.status.setText(f"Saved report: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Save report", str(exc))

    def _open_stalls(self):
        try:
            import ui_stall_watch
            ui_stall_watch.open_window(self.app)
        except Exception as exc:
            QMessageBox.information(self, "UI stall report", f"The stall watcher is unavailable: {exc}")

    def closeEvent(self, event):
        try:
            self._timer.stop()
        except Exception:
            pass
        super().closeEvent(event)


def open_monitor_center(app):
    old = getattr(app, "_monitor_center_window", None)
    try:
        if old is not None:
            old.show(); old.raise_(); old.activateWindow()
            return old
    except RuntimeError:
        pass
    window = MonitorCenter(app, app)
    window.setAttribute(__import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.WidgetAttribute.WA_DeleteOnClose, True)
    app._monitor_center_window = window
    window.destroyed.connect(lambda *_: setattr(app, "_monitor_center_window", None)
                             if getattr(app, "_monitor_center_window", None) is window else None)
    window.show(); window.raise_(); window.activateWindow()
    return window
