"""`EPIC-035H` — an exclusive, non-blocking lock on an open file, on either platform.

The lock belongs to the open file, so the operating system releases it when the
process ends, however it ends: nothing is left behind by a crash.

Windows has no `fcntl`; `msvcrt.locking` locks a byte range instead, one byte
at the start of the file here. A lock file therefore holds one byte (written by
`ensure_lockable_size`) so the range exists on both platforms alike.
"""

from __future__ import annotations

import errno
import logging
import sys
from typing import BinaryIO

logger = logging.getLogger("App.Instance")

#: What a lock call raises when another process holds the lock. Anything else
#: (a filesystem without `flock`, an interrupted call) is refused as well, which
#: is the safe side, but is not worded as another copy running.
_TAKEN = frozenset({errno.EAGAIN, errno.EACCES, errno.EDEADLK})


def _refuse(error: OSError) -> bool:
    """`False` always: the lock was not taken. A cause other than 'held' is logged."""
    if error.errno not in _TAKEN:
        logger.warning(
            "The instance lock could not be taken (%s: errno %s); this copy "
            "will be read-only [instance-lock-error]",
            errno.errorcode.get(error.errno or 0, "?"),
            error.errno,
        )
    return False


if sys.platform == "win32":
    import msvcrt

    def try_lock_exclusive(handle: BinaryIO) -> bool:
        """Lock `handle`; `False` when another process already holds it."""
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            return _refuse(error)
        return True

    def unlock(handle: BinaryIO) -> None:
        """Release a lock `try_lock_exclusive` took."""
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def try_lock_exclusive(handle: BinaryIO) -> bool:
        """Lock `handle`; `False` when another process already holds it."""
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            return _refuse(error)
        return True

    def unlock(handle: BinaryIO) -> None:
        """Release a lock `try_lock_exclusive` took."""
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def ensure_lockable_size(handle: BinaryIO) -> None:
    """Make the file at least one byte long, the range Windows locks."""
    handle.seek(0, 2)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
