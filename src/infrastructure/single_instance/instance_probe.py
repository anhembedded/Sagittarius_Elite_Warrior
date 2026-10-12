"""`EPIC-038C` - `IInstanceProbe` over the same lock file `InstanceAccess` takes.

It tries the lock and gives it back at once. It never creates the file: a data
root nobody has run on has no lock to hold, and `status` must not leave one
behind. A lock that cannot be taken for a reason other than "held" is reported
as held (the safe side for a monitor, and `file_lock` has already logged why).
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_probe import (
    IInstanceProbe,
)
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.file_lock import (
    try_lock_exclusive,
    unlock,
)


class FileLockInstanceProbe(IInstanceProbe):
    """Probes `lock_file`."""

    def __init__(self, lock_file: Path) -> None:
        self._lock_file = lock_file

    def is_held(self) -> bool:
        if not self._lock_file.exists():
            return False
        with self._lock_file.open("a+b") as handle:
            if not try_lock_exclusive(handle):
                return True
            unlock(handle)
            return False
