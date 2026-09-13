# Windows crash diagnostics — 2026-09-13

This build adds persistent crash diagnostics for Windows and other desktop hosts.

Windows logs are written to:

    %APPDATA%\MathematiciansGroovebox\logs

Start with:

    LATEST_CRASH_LOG.txt

It points at the session log and native crash log from the most recent run.

The session log captures stdout/stderr, uncaught Python exceptions, worker-thread
exceptions, and the Qt event-loop exit code. The native log is backed by Python's
faulthandler and is opened before media, sCode workers, and Qt startup so native
faults have a persistent destination.

LAUNCH_GROOVEBOX_WINDOWS.bat now keeps its console open when Groovebox returns a
non-zero code and prints the log directory instead of letting the traceback vanish.

Regression status after patch:
- run_groovebox.py / launch_groovebox.py compile: PASS
- NaN/video/exit regression: 19/19 PASS
