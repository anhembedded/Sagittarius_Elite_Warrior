"""`EPIC-010` — what an object must offer to have its state remembered.

@details `typing.Protocol`, not an ABC to inherit from.
`architecture-rule.md` §2 forbids multiple inheritance, and every real
contributor (a `BasePresenter` subclass, or `MainWindow`, a `QMainWindow`
subclass) already has a base class of its own. A Protocol is satisfied
structurally, so it costs nothing to adopt and never touches the MRO —
`PresenterManager.register()` is deliberately duck-typed for the identical
reason: *"this router deliberately does not require that base"*.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import (
    StateData,
    StateScope,
)


@runtime_checkable
class IStateContributor(Protocol):
    """One object whose remembered state lives under one `StateScope`."""

    @property
    def state_scope(self) -> StateScope:
        """This contributor's address in the store. Constant for its lifetime."""
        ...

    def capture_state(self) -> StateData:
        """Returns what should be remembered right now.

        @details Must return only JSON-safe values — the store raises rather
        than silently dropping anything else, and it raises *here*, on the
        same call stack as the mistake, not deferred to the shutdown path.
        """
        ...

    def restore_state(self, data: StateData) -> None:
        """Applies a previously captured slice, or a subset of it.

        @details `data` is a *request*, not a command: it may be empty (no
        prior session, or file was unreadable), and any key inside it may
        describe a value that is no longer legal (a deleted symbol, a removed
        strategy). Validating each value — and falling back to this
        contributor's own default when one fails — is this method's job, not
        the coordinator's: the coordinator must not need to know what a
        `TimeFrame` is. Must not cause a visible side effect (a network call,
        a signal that looks like the user just acted) — see `EPIC-010`
        design's failure mode #12.
        """
        ...
