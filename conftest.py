"""R132 test harness: leave through the OS after the session, like run_groovebox.py does.

Tests that build the full main window start appliance / nearby / optimizer threads that still hold Python objects
while PyQt destroys its C++ side; a normal interpreter exit then faults in sip (exit 139) AFTER every test passed.
The app itself already exits with os._exit (QT_TEARDOWN_20261103); the test session now does the same, so a
segfault in teardown can no longer hide (or fake) a test result.
"""
import os
import sys


def pytest_unconfigure(config):
    status = getattr(config, "_r132_exitstatus", None)
    if status is None or os.environ.get("GROOVEBOX_TEST_NORMAL_EXIT") == "1":
        return
    try:
        sys.stdout.flush(); sys.stderr.flush()
    finally:
        os._exit(int(status))


def pytest_sessionfinish(session, exitstatus):
    session.config._r132_exitstatus = int(exitstatus)
