"""Whether some copy of the app holds the data root's lock, asked without taking it for good (`EPIC-038C`).

`IInstanceAccess` answers "may *I* write"; this answers "is *anyone* running".
`status` needs it because a snapshot file survives a crash and the lock does
not: a fresh-looking file with a free lock is a host that just died
(`DESIGN_2026-10-09_headless_operation.md` §8).

@par Extension cases
  · a host on another machine (a shared data root) - another implementation of
    this port; `status` is untouched.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IInstanceProbe(ABC):
    """Whether the instance lock is held right now."""

    @abstractmethod
    def is_held(self) -> bool:
        """`True` when another process holds the lock; `False` when it is free
        or has never been taken. Leaves it as it found it."""
