"""Write a file only its owner can read, whole or not at all (`EPIC-047B`).

The catalog of shared mechanisms lists only `src/support`, `src/core` and `src/shell`; this one
lives beside its first consumer and moves to `src/support` when a second one (`health.json`,
`DirectoryHostControl`) adopts it.

The bytes go to a temporary file beside the target, which is **created** `0600` (a `chmod` after
the write would leave a window in which another account could open it), flushed to disk and renamed
over the target. A rename within one directory is atomic on both platforms (`os.replace`), so a
reader sees the previous file or this one; a process killed in between leaves the previous file
untouched and a temporary file the next write replaces.

**Known limit, Windows:** the mode bits do nothing there; the file inherits the ACL of `state/`.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_health_snapshot_sink import (
    REPLACE_ATTEMPTS,
    REPLACE_STEP_S,
)

_PRIVATE_FILE = 0o600
_CREATE_NEW = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)


def write_owner_only_atomically(
    target: Path,
    data: bytes,
    replace: Callable[[Path, Path], object] = os.replace,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """@brief `data` as the whole content of `target`, owner-only, or nothing changed.
    @param replace The rename; injected so a test can refuse it.
    @throws OSError The directory cannot be made, or the file written or renamed."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.unlink(missing_ok=True)
    try:
        descriptor = os.open(temporary, _CREATE_NEW, _PRIVATE_FILE)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_tolerating_a_reader(temporary, target, replace, sleep)
    finally:
        temporary.unlink(missing_ok=True)


def _replace_tolerating_a_reader(
    temporary: Path,
    target: Path,
    replace: Callable[[Path, Path], object],
    sleep: Callable[[float], None],
) -> None:
    """On Windows a rename over a file another process holds open is refused with
    `PermissionError` for a few milliseconds; only a refusal that outlasts the tries is raised."""
    for _ in range(REPLACE_ATTEMPTS - 1):
        try:
            replace(temporary, target)
        except PermissionError:
            sleep(REPLACE_STEP_S)
        else:
            return
    replace(temporary, target)
