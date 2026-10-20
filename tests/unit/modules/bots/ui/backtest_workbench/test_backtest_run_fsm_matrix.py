"""`EPIC-040D` — the workbench does one thing at a time: a run, or a sync, or nothing."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_run_fsm_matrix import (
    RUN_TRANSITIONS,
    IllegalRunTransitionError,
    RunActivity,
    RunEvent,
    next_activity,
)


def test_a_run_and_a_sync_start_only_from_nothing() -> None:
    assert next_activity(RunActivity.IDLE, RunEvent.RUN_STARTED) is RunActivity.RUNNING
    assert next_activity(RunActivity.IDLE, RunEvent.SYNC_STARTED) is RunActivity.SYNCING
    for busy in (RunActivity.RUNNING, RunActivity.SYNCING):
        for start in (RunEvent.RUN_STARTED, RunEvent.SYNC_STARTED):
            with pytest.raises(IllegalRunTransitionError):
                next_activity(busy, start)


@pytest.mark.parametrize("busy", [RunActivity.RUNNING, RunActivity.SYNCING])
@pytest.mark.parametrize(
    "end",
    [
        RunEvent.ANSWERED,
        RunEvent.CANCELLED,
        RunEvent.FAILED,
        RunEvent.SELECTION_CHANGED,
    ],
)
def test_every_way_an_action_ends_returns_to_nothing(
    busy: RunActivity, end: RunEvent
) -> None:
    assert next_activity(busy, end) is RunActivity.IDLE


def test_nothing_running_has_nothing_to_answer_or_cancel() -> None:
    for event in (RunEvent.ANSWERED, RunEvent.CANCELLED, RunEvent.FAILED):
        with pytest.raises(IllegalRunTransitionError):
            next_activity(RunActivity.IDLE, event)
    assert (
        next_activity(RunActivity.IDLE, RunEvent.SELECTION_CHANGED) is RunActivity.IDLE
    )


def test_the_table_has_a_row_for_every_activity_and_selection_change() -> None:
    for activity in RunActivity:
        assert (activity, RunEvent.SELECTION_CHANGED) in RUN_TRANSITIONS
