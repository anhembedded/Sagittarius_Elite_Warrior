"""Resident memory, read from the operating system without a dependency (`EPIC-038D`).

Linux reads `/proc/self/statm` (its second field is resident pages). Windows asks
`GetProcessMemoryInfo` for the working set through `ctypes`. Neither needs `psutil`,
which is not a dependency of this application. A platform with neither answers
`None`, and so does a read that fails: the health line must never be the thing that
breaks the host.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
from ctypes import wintypes
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_process_memory import (
    IProcessMemory,
)

logger = logging.getLogger("App.Operations")

_BYTES_PER_MB = 1024 * 1024
STATM_PATH = Path("/proc/self/statm")


class ProcfsProcessMemory(IProcessMemory):
    """Linux: resident pages times the page size."""

    def __init__(self, statm: Path = STATM_PATH, page_size: int | None = None) -> None:
        self._statm = statm
        self._page_size = page_size

    def resident_mb(self) -> int | None:
        try:
            fields = self._statm.read_text(encoding="ascii").split()
            resident_pages = int(fields[1])
            page_size = self._page_size or os.sysconf("SC_PAGE_SIZE")
        except (OSError, ValueError, IndexError):
            return None
        return resident_pages * page_size // _BYTES_PER_MB


class _ProcessMemoryCounters(ctypes.Structure):
    """`PROCESS_MEMORY_COUNTERS` (psapi.h)."""

    _fields_ = (
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    )


class WindowsProcessMemory(IProcessMemory):
    """Windows: the process's working set."""

    def resident_mb(self) -> int | None:
        if sys.platform != "win32":
            return None
        try:
            counters = _ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            process = ctypes.windll.kernel32.GetCurrentProcess()  # type: ignore[attr-defined]
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(  # type: ignore[attr-defined]
                process, ctypes.byref(counters), counters.cb
            )
        except (OSError, AttributeError):
            return None
        return int(counters.WorkingSetSize) // _BYTES_PER_MB if ok else None


class UnknownProcessMemory(IProcessMemory):
    """A platform that gives no answer: `na` on the line, said once at start."""

    def resident_mb(self) -> int | None:
        return None


def default_process_memory(platform: str = sys.platform) -> IProcessMemory:
    if platform.startswith("linux"):
        return ProcfsProcessMemory()
    if platform == "win32":
        return WindowsProcessMemory()
    logger.info(
        "[health] resident memory is not read on %s; rss_mb will be na", platform
    )
    return UnknownProcessMemory()
