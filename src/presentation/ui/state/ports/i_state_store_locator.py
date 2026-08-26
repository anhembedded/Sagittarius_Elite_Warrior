"""`EPIC-010` — where the persistent store's file lives, and how to remove it."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class IStateStoreLocator(ABC):
    """Owns the file's location and its deletion — nothing else.

    @details Split from `IStateStore` because the two change for different
    reasons: the store changes when the *format* changes, the locator when the
    *placement policy* does. Moving to `QStandardPaths` for a packaged build
    must not require touching a single line that reads or writes a slice.

    @par Not a lifetime router
    Choosing between the persistent and the session store is routing, and it
    belongs to the coordinator. This type is asked only about the file, and
    only the persistent store has one.
    """

    @abstractmethod
    def state_file(self) -> Path:
        """Absolute path of the state file. Need not exist yet."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Deletes the state file if present. Never raises.

        @details This is the whole implementation of "restore defaults" — the
        mitigation for the risk that remembered values become sticky and the
        user cannot work out why the application will not go back to how it
        started.
        """
        ...
