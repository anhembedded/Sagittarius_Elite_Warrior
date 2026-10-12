"""What `status` concludes about a host from the lock and the snapshot (`EPIC-038C`).

Not `HostState`: that is what the host says about itself (`SERVING`, `DRAINING`);
this is what an observer can prove. A host can say `SERVING` in a file it wrote
a minute before it was killed, which is why the lock is asked too.
"""

from __future__ import annotations

from enum import StrEnum


class HostLiveness(StrEnum):
    """Spelled as `status` prints them."""

    #: The lock is held and the snapshot is fresh.
    RUNNING = "running"
    #: The lock is held but the snapshot is missing, unreadable or too old: a
    #: host that is alive and not reporting, which is a reason to look.
    STALE = "stale"
    #: Nobody holds the lock, whatever the file says.
    NOT_RUNNING = "not running"
