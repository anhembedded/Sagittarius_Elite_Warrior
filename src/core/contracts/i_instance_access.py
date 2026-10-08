"""`IInstanceAccess` — whether this copy of the app may change anything (`EPIC-035H`).

@details Two copies of the app on one data root would both read the bots'
files, both lay a ladder on the same account and both answer the same fills:
the best case is a `DUPLICATE_LEVEL_ORDER` halt, the worst is two ladders. The
first copy on a data root is **writable**; any later one is **read-only**: it
shows what is there and places, cancels and saves nothing.

The shell decides, once, at start-up, from an exclusive lock on a file under
the data root, and binds the answer here. A module asks this port and never
learns how the answer was reached.

@par Extension cases
  · a read-only copy that watches the first and takes over when it exits —
    one more implementation of this port, and a caller that re-asks;
  · a read-only mode the user chooses (a viewer on another machine) — the same
    port with another reason.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IInstanceAccess(ABC):
    """Whether this copy of the app is the one that may trade."""

    @property
    @abstractmethod
    def read_only(self) -> bool:
        """`True` when another copy holds the data root: this one changes nothing."""

    @property
    @abstractmethod
    def reason(self) -> str:
        """A sentence saying why this copy is read-only and what that means;
        empty when it is writable."""
