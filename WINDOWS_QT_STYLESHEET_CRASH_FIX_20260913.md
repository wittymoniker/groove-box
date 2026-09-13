# Windows Qt stylesheet crash hardening — 2026-09-13

This build addresses Windows sessions that close after Qt prints messages such as:
`Could not parse stylesheet of object QPushButton(...)`.

Changes:
- Clears inherited `QT_FATAL_WARNINGS` before PyQt initializes so ordinary Qt warnings cannot abort Groovebox.
- Captures Qt stylesheet parse warnings into the persistent Groovebox session log with a Python stack trace.
- Throttles duplicate stylesheet warning stack dumps to prevent a repaint loop from flooding the log/UI thread.
- Rebuilds selected STEP button QSS as a complete declaration block instead of incrementally appending style fragments.
- Preserves the Windows persistent crash logs under `%APPDATA%\\MathematiciansGroovebox\\logs`.

Validation:
- `python -m py_compile groovebox.py run_groovebox.py`: PASS
- NaN/video/exit regression: 19/19 PASS
- carrier-clear regression: 6/6 PASS
