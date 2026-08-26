"""`EPIC-010` — the port every state store implements."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import (
    StateData,
    StateScope,
)


class IStateStore(ABC):
    """Reads and writes one slice at a time, addressed by `StateScope`.

    @details Deliberately narrow. A wider port would never be narrowed back —
    the same reasoning `application/ports/i_config_reader.py` records for
    itself. Four verbs cover every caller: read one slice, replace one slice,
    drop one slice, and force pending work out.

    @par Never raises
    Every implementation swallows I/O failure, logs once, and degrades. Callers
    reach this port from `teardown()`, and an exception there is exactly the
    class of defect `BUG-048` was: a failure on the shutdown path that hung the
    process instead of reporting.
    """

    @abstractmethod
    def read(self, scope: StateScope) -> StateData:
        """Returns the slice for `scope`, or an empty mapping.

        @details Absent, unreadable and corrupt are all reported the same way,
        because a caller can do nothing different about them: every one means
        "use your defaults". Distinguishing them is a diagnostic concern, not a
        control-flow one.
        """
        ...

    @abstractmethod
    def write(self, scope: StateScope, data: StateData) -> None:
        """Replaces the slice for `scope`, leaving every other slice intact.

        @details Slice-level replacement is not an optimisation, it is the
        correctness requirement. Presenters are lazily constructed, so a
        session that only opened one screen can only capture that screen — and
        writing the whole document would erase the slices belonging to screens
        this session never touched.
        """
        ...

    @abstractmethod
    def discard(self, scope: StateScope) -> None:
        """Forgets the slice for `scope` permanently.

        @details The verb exists so that "this instance is gone" is something a
        caller can *say*, rather than something that happens to be true because
        the data lived in memory. A no-op on a store that has nothing to drop.
        """
        ...

    @abstractmethod
    def flush(self) -> None:
        """Pushes any pending write out now. Never raises."""
        ...
