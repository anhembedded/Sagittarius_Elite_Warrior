"""`EPIC-035H` — `IInstanceAccess` from an exclusive lock file.

The first process to lock the file is writable and holds the lock until it
releases it or ends; any other finds it taken and is read-only. No network, no
heartbeat, no stale-file cleanup: the operating system owns the lock, so a
crashed app leaves nothing to clear.
"""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Self

from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.file_lock import (
    ensure_lockable_size,
    try_lock_exclusive,
    unlock,
)


class InstanceAccess(IInstanceAccess):
    """This copy's access, and the lock file handle that backs it."""

    def __init__(self, handle: BinaryIO | None, reason: str) -> None:
        self._handle = handle
        self._reason = reason

    @classmethod
    def unguarded(cls) -> Self:
        """Writable with no lock: for a run that is not the app's own (a test,
        a script) and so does not contend for the data root."""
        return cls(None, "")

    @classmethod
    def acquire(cls, lock_file: Path) -> Self:
        """Lock `lock_file`, creating it and its folder; read-only if it is taken."""
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_file.open("a+b")
        ensure_lockable_size(handle)
        if try_lock_exclusive(handle):
            return cls(handle, "")
        handle.close()
        reason = (
            f"Another copy of Sagittarius is already running on the same data ({lock_file.parent}). "
            "This copy is read-only: it shows what is there, and places, cancels "
            "and saves nothing."
        )
        return cls(None, reason)

    @property
    def read_only(self) -> bool:
        return bool(self._reason)

    @property
    def reason(self) -> str:
        return self._reason

    def release(self) -> None:
        """Give the lock up (a clean exit). Harmless twice, and on a read-only copy."""
        handle, self._handle = self._handle, None
        if handle is None:
            return
        unlock(handle)
        handle.close()
