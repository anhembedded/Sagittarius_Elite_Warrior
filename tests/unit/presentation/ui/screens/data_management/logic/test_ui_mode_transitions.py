"""`EPIC-003B2` — `logic/ui_mode_transitions.py`."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.logic.ui_mode_transitions import (
    ALLOWED_TRANSITIONS,
    install_transitions,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import UIMode


class RecordingFsm:
    def __init__(self) -> None:
        self.registered: list[tuple[UIMode, UIMode]] = []

    def add_transition(self, source: UIMode, target: UIMode) -> None:
        self.registered.append((source, target))


def test_install_registers_every_row_and_nothing_else() -> None:
    fsm = RecordingFsm()

    install_transitions(fsm)

    assert fsm.registered == list(ALLOWED_TRANSITIONS)


def test_no_row_is_listed_twice() -> None:
    """A duplicate row is invisible at runtime (`add_transition` is
    idempotent) and hides an editing mistake in the table."""
    assert len(set(ALLOWED_TRANSITIONS)) == len(ALLOWED_TRANSITIONS)


def test_no_state_transitions_to_itself() -> None:
    assert all(source is not target for source, target in ALLOWED_TRANSITIONS)


def test_every_long_job_can_reach_idle_and_error() -> None:
    """Otherwise the screen locks: a job that finishes or fails with no
    legal move out leaves every button disabled forever."""
    for state in (UIMode.SCANNING, UIMode.SYNCING, UIMode.CLEARING):
        assert (state, UIMode.IDLE) in ALLOWED_TRANSITIONS
        assert (state, UIMode.ERROR) in ALLOWED_TRANSITIONS


def test_clearing_has_no_cancel_path() -> None:
    """Pinning what the code does, not wishing for something else:
    `_on_cancel` only transitions out of `SYNCING`/`SCANNING`, and the
    clear/purge handlers pass no cancellation token. A row added here
    without that plumbing would advertise a cancel the screen cannot
    honour."""
    assert (UIMode.CLEARING, UIMode.CANCELLING) not in ALLOWED_TRANSITIONS


def test_error_is_recoverable() -> None:
    assert (UIMode.ERROR, UIMode.IDLE) in ALLOWED_TRANSITIONS
