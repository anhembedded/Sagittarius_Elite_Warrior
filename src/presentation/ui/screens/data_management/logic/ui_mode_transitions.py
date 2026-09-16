"""`EPIC-003B2` — which Data Management UI-mode transitions are legal.

@details Twelve `fsm.add_transition(...)` calls used to sit inside
`DataManagementPresenter.__init__`, in the middle of coordinator
construction and log-handler wiring. They are a **table**, not wiring: the
legal moves of this screen's state machine, which is exactly the kind of
thing a reader wants to see whole and a test wants to assert against
without constructing a Presenter.

@par Read the table, not the calls
`ALLOWED_TRANSITIONS` is the answer to "can this screen go from CANCELLING
to ERROR" — a question that previously required scrolling a 162-line
`__init__` and mentally deduplicating three comment-separated groups.
"""

from __future__ import annotations

from typing import Any

from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import UIMode

#: Every legal `(from, to)` move, grouped as the original comments grouped
#: them. Order is preserved from the code this replaces — `add_transition`
#: is order-independent, but a diff that reorders rows is harder to read
#: than one that does not.
ALLOWED_TRANSITIONS: tuple[tuple[UIMode, UIMode], ...] = (
    # Out of IDLE, into the three long jobs.
    (UIMode.IDLE, UIMode.SCANNING),
    (UIMode.IDLE, UIMode.SYNCING),
    (UIMode.IDLE, UIMode.CLEARING),
    # Back to IDLE when each finishes.
    (UIMode.SCANNING, UIMode.IDLE),
    (UIMode.SYNCING, UIMode.IDLE),
    (UIMode.CLEARING, UIMode.IDLE),
    # Cancellation. CLEARING has no cancel path, and matches the code
    # that would use one: `_on_cancel` only transitions when the current
    # state is `SYNCING` or `SCANNING`, and the clear/purge handlers
    # (`_on_clear_data`, `_on_clear_row`, `_on_purge_all`) hand no
    # cancellation token to their worker.
    (UIMode.SCANNING, UIMode.CANCELLING),
    (UIMode.SYNCING, UIMode.CANCELLING),
    (UIMode.CANCELLING, UIMode.IDLE),
    (UIMode.CANCELLING, UIMode.ERROR),
    # Failure of any long job.
    (UIMode.SCANNING, UIMode.ERROR),
    (UIMode.SYNCING, UIMode.ERROR),
    (UIMode.CLEARING, UIMode.ERROR),
    # And the way out of a reported failure.
    (UIMode.ERROR, UIMode.IDLE),
)


def install_transitions(fsm: Any) -> None:
    """Register every legal transition on `fsm`."""
    for source, target in ALLOWED_TRANSITIONS:
        fsm.add_transition(source, target)
