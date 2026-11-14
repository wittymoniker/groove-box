# Runtime and UI execution contract — R30.3

## Python environment

- Supported interpreter baseline: CPython 3.10 or newer, defined once in the root `runtime_contract.py` module that is included in the ISO runtime inventory.
- The desktop launcher and direct `groovebox.py` entry point call the same runtime check before importing NumPy or constructing Qt.
- Runtime provisioning and the startup import probe share the same dependency manifest; QtWebEngine stays optional and does not block the audio UI from launching.
- Desktop, Windows, macOS and sOS launch wrappers set UTF-8 and unbuffered output consistently before application startup.
- `PYTHONUTF8=1` and unbuffered diagnostics are enabled by the launch wrappers unless explicitly overridden on POSIX.
- Qt/PyQt6 must come from one ABI-compatible installation. Fedora uses the distro-matched Qt/PyQt6 stack; other platforms use the provisioned project runtime. Do not mix distro Qt libraries with pip Qt wheels.
- Scientific-library thread counts are configured by `thread_budget.apply()` before NumPy is imported.

## UI-thread rules

1. Only QApplication's thread may read or mutate QWidget/QObject UI state.
2. Workers receive immutable data snapshots and perform decoding, rendering, file I/O, DSP preparation, and other blocking work away from Qt.
3. Worker results return through `ui_runtime.post_to_ui()` or `ui_runtime.submit_ui_task()`; the dispatcher queues/coalesces publications, bounds pending UI work, and drops stale-generation results.
4. Do not use `Future.result()`, `Thread.join()`, `QThread.wait()`, process waits, or `QApplication.processEvents()` on the GUI thread to make an operation appear asynchronous.
5. Realtime audio callbacks do not post per-sample UI events. They publish bounded snapshots/metrics for a timer or coalesced UI update.
6. Each subsystem may have a logical lane for ordering/backpressure, but worker threads are drawn from the process-wide sCode scheduler and its CPU/memory budget. The shared Qt adapter is deliberately not a new executor.

## Current migration scope

- Main composition/project/audio lanes use shared sCode work lanes.
- Performance scan/file-manager jobs, scope/spectrum renderers, preview/video decode, audio export, USB storage operations, phrase generation, video-object FX, and per-engine canonical preparation are routed through bounded sCode lanes. Their logical lanes do not create additional thread pools.
- Live Player media loading and take finalization publish through the common UI dispatcher.
- Clip Timeline Studio rendering uses the shared lane and coalesced UI progress updates.
- Performance, Video Clip Studio, Clip Timeline Studio, scopes, spectrum, preview rendering, and audio export use `SharedQtPool` adapters backed by the same sCode process-wide executor. The adapter preserves the small `QRunnable` call surface (`start`, bounded queueing, `clear`, and `waitForDone`) without allocating private Qt worker threads.
- Video-object FX and canonical-engine preparation also use bounded sCode lanes instead of one executor per engine/window.
- Known legacy risks remain: `groovebox.py::_run_off_gui()` still blocks its caller with `Future.result()` for stem-export, Bake & Compare, WAV-finalization, and video-process-finalization callers. `video_clip_studio.py` also retains an export loop using `QApplication.processEvents()` and a bounded frame-thread join. These must become staged callback-driven state machines before the project can claim that every user-initiated render is nonblocking.
- A small number of bounded `.join(timeout=...)` calls remain in recorder/device shutdown paths. They are lifecycle waits, not render work, but should be checked on physical GUI shutdown.
