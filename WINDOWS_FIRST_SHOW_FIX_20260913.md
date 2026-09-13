# Windows first-show stability fix — 2026-09-13

Observed symptom: Groovebox exits on Windows immediately after the Qt window appears, after QPushButton stylesheet parse warnings.

Changes:
- Correct remaining out-of-range Qt rgba alpha values (>255) to valid 0..255 values.
- On Windows, avoid applying the same large main stylesheet twice (application-wide + main window). The main-window stylesheet remains authoritative and inherits to descendants.
- Use Qt Fusion style on Windows before constructing the main window to reduce native-style/QSS repolish variability.
- Delay the animated ParametricMathBackground until 750 ms after the first main-window realization/event-loop entry.
- Preserve Qt stylesheet stack tracing and persistent Windows crash logs.
- Add startup checkpoints around QApplication creation, main-window construction, show(), and event-loop entry.

Validation:
- Python compile: PASS
- NaN/video/exit regression: 19/19 PASS
- Carrier-clear regression: 6/6 PASS
