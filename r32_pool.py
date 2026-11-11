"""r32_pool.py — GROOVEBOX_R32_POOL_FIX_20261110: one shared pool for every R32 worker task.

R32 modules used QThreadPool.globalInstance(), a second thread pool outside sCode's shared
executor, so their work competed with the budgeted lanes. They now all use one
ui_runtime.SharedQtPool lane (QThreadPool-compatible) and fall back to Qt only if the
shared runtime is unavailable."""
_POOL = [None]


def pool():
    if _POOL[0] is None:
        try:
            import ui_runtime
            _POOL[0] = ui_runtime.make_qt_pool("r32-workers", max_workers=2, max_pending=64)
        except Exception:
            from PyQt6.QtCore import QThreadPool
            _POOL[0] = QThreadPool.globalInstance()
    return _POOL[0]


def start(runnable):
    return pool().start(runnable)
