"""`EPIC-035H` — `IInstanceAccess` from an exclusive lock file.

The first process to lock the file is writable and holds the lock until it
releases it or ends; any other finds it taken and is read-only. No network, no
heartbeat, no stale-file cleanup: the operating system owns the lock, so a
crashed app leaves nothing to clear.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO, Self

from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.support.instance_lock.file_lock import (
    ensure_lockable_size,
    try_lock_exclusive,
    unlock,
)

#: How long a taken lock is retried before the copy is read-only: long enough
#: for a probe to let go, short enough that a real second copy starts at once.
RETRY_STEP_S = 0.01
RETRY_WINDOW_S = 0.25
RETRY_ATTEMPTS = int(RETRY_WINDOW_S / RETRY_STEP_S)


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
    def declined(cls, reason: str) -> Self:
        """Read-only because the caller asked not to write, with no lock taken:
        a command that only reads must neither be the writable copy (its boot
        would apply the restart rule to the bots) nor hold the lock a host is
        asked about (`EPIC-038C`)."""
        return cls(None, reason)

    @classmethod
    def acquire(
        cls, lock_file: Path, sleep: Callable[[float], None] = time.sleep
    ) -> Self:
        """Lock `lock_file`, creating it and its folder; read-only if it is taken.

        A taken lock is tried again for `RETRY_WINDOW_S` before this copy gives
        up (`EPIC-038C`): `status` and `IInstanceProbe` hold the lock for
        microseconds to ask whether it is free, and a host that started in that
        instant would otherwise be read-only for its whole life and silently
        trade nothing. A real second copy waits the window out and is read-only
        as before. `sleep` is injected so the race can be tested without waiting.
        """
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_file.open("a+b")
        ensure_lockable_size(handle)
        for _ in range(RETRY_ATTEMPTS):
            if try_lock_exclusive(handle):
                return cls(handle, "")
            sleep(RETRY_STEP_S)
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
