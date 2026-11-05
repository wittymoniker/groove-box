"""GROOVEBOX_R23R_MEMORY_MANAGER_20261103 — RAM budget, SSD swap and project tabs capacity.

RAM never floods, and several projects can stay open:

  * SSD SWAP — a Groovebox-owned swap area on disk whose capacity equals the system RAM (capped
    at 90 % of the free disk space). Large buffers are written there as NumPy memory-maps: the
    data stays usable (reads page in from the SSD on demand, the OS keeps the working region in
    its cache), so a spilled track still plays — only the part being played is in RAM.
  * BUDGET — Groovebox's own buffers may use up to `budget_fraction` of RAM (default 50 %). When
    the budget is exceeded, or the system's available memory falls under the floor (15 % of RAM or
    768 MiB), registered caches spill, least valuable first: inactive project tabs, then the active
    project's cold buffers (the parts of the track you are not working on), memos, pools.
  * TABS — how many main-window project tabs fit is computed from the budget, the sCode pool's
    real usage and the measured per-project footprint (see max_tabs()).

Spill targets register callbacks (register_spill); each returns the bytes it freed.
"""
from __future__ import annotations

import ctypes
import os
import shutil
import sys
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

_LOCK = threading.RLock()


# ----------------------------------------------------------------------------- system memory
def ram_info() -> Tuple[int, int]:
    """(available, total) bytes — Linux /proc/meminfo, Windows GlobalMemoryStatusEx, macOS sysctl."""
    try:
        import memory_guard
        avail, total = memory_guard._read_meminfo()
        if total > 0 and sys.platform.startswith("linux"):
            return avail, total
    except Exception:
        pass
    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        st = MEMORYSTATUSEX(); st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        try:
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                return int(st.ullAvailPhys), int(st.ullTotalPhys)
        except Exception:
            pass
    if sys.platform == "darwin":
        try:
            import subprocess
            total = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=2).stdout.strip())
            vm = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=2).stdout
            page = 4096
            free = 0
            for line in vm.splitlines():
                if "page size of" in line:
                    page = int(line.split("page size of")[1].split()[0])
                if line.startswith(("Pages free", "Pages inactive", "Pages speculative")):
                    free += int(line.split(":")[1].strip().rstrip("."))
            return free * page, total
        except Exception:
            pass
    try:
        page = os.sysconf("SC_PAGE_SIZE")
        total = int(os.sysconf("SC_PHYS_PAGES")) * page
        avail = int(os.sysconf("SC_AVPHYS_PAGES")) * page
        return avail, total
    except Exception:
        return 0, 0


def process_rss() -> int:
    """Resident memory of this process (bytes; 0 if unknown)."""
    try:
        with open("/proc/self/statm", "r") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except Exception:
        pass
    if os.name == "nt":
        try:
            class PMC(ctypes.Structure):
                _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
            pmc = PMC(); pmc.cb = ctypes.sizeof(PMC)
            h = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
                return int(pmc.WorkingSetSize)
        except Exception:
            pass
    try:
        import resource
        r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(r) if sys.platform == "darwin" else int(r) * 1024
    except Exception:
        return 0


# ----------------------------------------------------------------------------- SSD swap
class SwapStore:
    """Disk-backed buffer store (capacity = system RAM, ≤ 90 % of free disk). Arrays become
    read-only memory-maps of .npy files; least-recently-used files are removed when full."""

    def __init__(self, root: Optional[str] = None):
        if root is None:
            try:
                import groovebox_paths
                root = os.path.join(groovebox_paths.cache_dir(), "swap")
            except Exception:
                root = os.path.join(os.path.expanduser("~"), ".groovebox", "cache", "swap")
        self.root = root
        os.makedirs(self.root, exist_ok=True)
        self._files: Dict[str, Tuple[str, int, float]] = {}       # key → (path, bytes, last access)
        self._clean_stale()
        _a, total = ram_info()
        try:
            free = shutil.disk_usage(self.root).free
        except Exception:
            free = total
        self.capacity = int(min(total or (4 << 30), 0.9 * free))

    def _clean_stale(self):
        """Files from a previous session are not ours any more."""
        try:
            for f in os.listdir(self.root):
                if f.endswith(".npy"):
                    try:
                        os.remove(os.path.join(self.root, f))
                    except OSError:
                        pass
        except OSError:
            pass

    @property
    def used(self) -> int:
        return sum(b for _p, b, _t in self._files.values())

    def _evict(self, need: int):
        for key in sorted(self._files, key=lambda k: self._files[k][2]):
            if self.used + need <= self.capacity:
                break
            self.drop(key)

    def put(self, key: str, arr) -> Optional[np.memmap]:
        """Write ``arr`` to swap and return a read-only memory-map of it (None if it cannot fit)."""
        a = np.asarray(arr)
        need = int(a.nbytes)
        with _LOCK:
            if need > self.capacity:
                return None
            self.drop(key)
            self._evict(need)
            path = os.path.join(self.root, f"{abs(hash(key)) & 0xFFFFFFFFFFFF:012x}-{os.getpid()}.npy")
            try:
                mm = np.lib.format.open_memmap(path, mode="w+", dtype=a.dtype, shape=a.shape)
                mm[...] = a
                mm.flush()
                del mm
                ro = np.load(path, mmap_mode="c")   # copy-on-write: writers get private pages, the file stays intact
            except Exception:
                try:
                    os.remove(path)
                except OSError:
                    pass
                return None
            self._files[key] = (path, need, time.monotonic())
            return ro

    def get(self, key: str) -> Optional[np.memmap]:
        with _LOCK:
            rec = self._files.get(key)
            if rec is None:
                return None
            self._files[key] = (rec[0], rec[1], time.monotonic())
            try:
                return np.load(rec[0], mmap_mode="c")
            except Exception:
                return None

    def drop(self, key: str):
        rec = self._files.pop(key, None)
        if rec is not None:
            try:
                os.remove(rec[0])
            except OSError:
                pass

    def drop_prefix(self, prefix: str):
        for k in [k for k in self._files if k.startswith(prefix)]:
            self.drop(k)


def is_swapped(arr) -> bool:
    return isinstance(arr, np.memmap)


# ----------------------------------------------------------------------------- manager
class MemoryManager:
    def __init__(self, budget_fraction: float = 0.5):
        self.budget_fraction = float(budget_fraction)
        self._spills: List[Tuple[int, str, object, Callable[[int], int], Callable[[], int]]] = []
        self.swap: Optional[SwapStore] = None
        self.per_project_bytes = 0
        self.base_rss = process_rss()
        self.last = {}

    def swap_store(self) -> SwapStore:
        if self.swap is None:
            self.swap = SwapStore()
        return self.swap

    def budget(self) -> int:
        _a, total = ram_info()
        return int((total or (4 << 30)) * self.budget_fraction)

    def floor(self) -> int:
        _a, total = ram_info()
        return int(max(768 << 20, 0.15 * (total or 0)))

    def register_spill(self, owner, name: str, priority: int, spill: Callable[[int], int],
                       size: Callable[[], int]):
        """priority: lower spills first. owner: the project window (inactive owners spill first)."""
        with _LOCK:
            self._spills = [s for s in self._spills if not (s[2] is owner and s[1] == name)]
            self._spills.append((int(priority), name, owner, spill, size))

    def unregister_owner(self, owner):
        with _LOCK:
            self._spills = [s for s in self._spills if s[2] is not owner]

    def tracked_bytes(self) -> int:
        tot = 0
        for _p, _n, _o, _sp, size in list(self._spills):
            try:
                tot += int(size() or 0)
            except Exception:
                pass
        return tot

    def pressure(self) -> int:
        """Bytes to free now (0 = fine)."""
        avail, _total = ram_info()
        need_sys = max(0, self.floor() - avail) if avail else 0
        need_budget = max(0, self.tracked_bytes() - self.budget())
        return max(need_sys, need_budget)

    def tick(self, active_owner=None) -> int:
        """Spill until the pressure is relieved. Returns bytes freed."""
        need = self.pressure()
        self.last = {"need": need, "at": time.monotonic()}
        if need <= 0:
            return 0
        freed = 0
        order = sorted(self._spills, key=lambda s: (0 if s[2] is not active_owner else 1, s[0]))
        for _p, name, owner, spill, _size in order:
            if freed >= need:
                break
            try:
                freed += int(spill(need - freed) or 0)
            except Exception:
                pass
        self.last["freed"] = freed
        return freed

    def park(self, owner) -> int:
        """Spill everything an (inactive) project owns."""
        freed = 0
        for _p, _name, o, spill, _size in list(self._spills):
            if o is owner:
                try:
                    freed += int(spill(1 << 62) or 0)
                except Exception:
                    pass
        return freed

    def max_tabs(self, open_tabs: int, pool_bytes: int = 0) -> int:
        """How many project tabs fit: the active project keeps its working set (measured footprint +
        sCode pool); every other tab is parked (its buffers in swap) and costs its resident baseline."""
        per = int(self.per_project_bytes or 0)
        if per <= 0:
            per = max(256 << 20, int(process_rss() - 120 * (1 << 20)) // max(1, open_tabs))
        avail, total = ram_info()
        budget = self.budget()
        active = per + int(pool_bytes)
        parked = max(96 << 20, int(per * 0.6))              # code objects + widgets stay resident
        room = min(budget, max(0, avail - self.floor()) + per * open_tabs)
        n = 1 + max(0, (room - active) // parked)
        return int(max(1, min(12, n)))

    def status(self, pool_bytes: int = 0, open_tabs: int = 1) -> dict:
        avail, total = ram_info()
        sw = self.swap
        return {"ram_avail": avail, "ram_total": total, "budget": self.budget(), "tracked": self.tracked_bytes(),
                "swap_used": sw.used if sw else 0, "swap_capacity": sw.capacity if sw else 0,
                "rss": process_rss(), "max_tabs": self.max_tabs(open_tabs, pool_bytes)}


_MANAGER: Optional[MemoryManager] = None


def manager() -> MemoryManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = MemoryManager()
    return _MANAGER


def fmt_bytes(n) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"
