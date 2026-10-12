"""`EPIC-038C` - `IInstanceProbe` over the same lock file `InstanceAccess` takes.

It tries the lock and gives it back at once. It never creates the file: a data
root nobody has run on has no lock to hold, and `status` must not leave one
behind. A lock that cannot be taken for a reason other than "held" is reported
as held (the safe side for a monitor, and `file_lock` has already logged why).

The probe holds the writer's lock for an instant, so `InstanceAccess.acquire`
retries a taken lock briefly: a host that starts in that instant still becomes
the writer (`EPIC-038C`, review finding).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_probe import (
    IInstanceProbe,
)
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.file_lock import (
    try_lock_exclusive,
    unlock,
)

#: How often, and how far apart, a taken lock is re-asked before it is called a host.
CONFIRMATIONS = 3
CONFIRM_STEP_S = 0.02


class FileLockInstanceProbe(IInstanceProbe):
    """Probes `lock_file`."""

    def __init__(
        self, lock_file: Path, sleep: Callable[[float], None] = time.sleep
    ) -> None:
        self._lock_file = lock_file
        self._sleep = sleep

    def is_held(self) -> bool:
        """A lock found taken is asked about again `CONFIRMATIONS` times: a host
        holds it for its whole life, but another probe (two monitors polling)
        holds it for microseconds and must not be reported as a host."""
        if not self._lock_file.exists():
            return False
        for attempt in range(CONFIRMATIONS):
            if self._free_now():
                return False
            if attempt < CONFIRMATIONS - 1:
                self._sleep(CONFIRM_STEP_S)
        return True

    def _free_now(self) -> bool:
        with self._lock_file.open("a+b") as handle:
            if not try_lock_exclusive(handle):
                return False
            unlock(handle)
            return True
