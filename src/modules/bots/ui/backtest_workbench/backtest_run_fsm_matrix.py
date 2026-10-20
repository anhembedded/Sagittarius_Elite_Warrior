"""`EPIC-040D` — what the Backtest workbench is doing: one action at a time.

Three activities: nothing, a replay in flight, a candle sync in flight. While one runs every other
action is locked, so a second click can never race the first (`async-ui-action-rule.md` §1); the
action settles back on nothing, whatever it ended in (a result, a refusal, a cancel, a failure). What
the page *shows* (a result, a refusal and its offers) is not an activity: it is the last answer, held
by the presenter beside this table, so a cancelled replay returns to "nothing running" with the last
result still on screen.

Selecting another bot ends whatever runs, and a late answer is dropped by the presenter's fence.
"""

from __future__ import annotations

from enum import Enum


class RunActivity(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    SYNCING = "SYNCING"


class RunEvent(str, Enum):
    RUN_STARTED = "RUN_STARTED"
    SYNC_STARTED = "SYNC_STARTED"
    #: An answer came back (a result, a refusal, a cancelled value, a synced period).
    ANSWERED = "ANSWERED"
    #: The person pressed Cancel or Stop.
    CANCELLED = "CANCELLED"
    #: The work raised.
    FAILED = "FAILED"
    #: Another bot was selected, or the workbench closed.
    SELECTION_CHANGED = "SELECTION_CHANGED"


class IllegalRunTransitionError(ValueError):
    """An event the activity has no row for: a second action while one is in flight."""


_ENDS = (RunEvent.ANSWERED, RunEvent.CANCELLED, RunEvent.FAILED)

RUN_TRANSITIONS: dict[tuple[RunActivity, RunEvent], RunActivity] = {
    (RunActivity.IDLE, RunEvent.RUN_STARTED): RunActivity.RUNNING,
    (RunActivity.IDLE, RunEvent.SYNC_STARTED): RunActivity.SYNCING,
    (RunActivity.IDLE, RunEvent.SELECTION_CHANGED): RunActivity.IDLE,
    **{(RunActivity.RUNNING, event): RunActivity.IDLE for event in _ENDS},
    **{(RunActivity.SYNCING, event): RunActivity.IDLE for event in _ENDS},
    (RunActivity.RUNNING, RunEvent.SELECTION_CHANGED): RunActivity.IDLE,
    (RunActivity.SYNCING, RunEvent.SELECTION_CHANGED): RunActivity.IDLE,
}


def next_activity(state: RunActivity, event: RunEvent) -> RunActivity:
    """@raise IllegalRunTransitionError `state` has no row for `event`."""
    try:
        return RUN_TRANSITIONS[(state, event)]
    except KeyError:
        raise IllegalRunTransitionError(
            f"{state.value} cannot take {event.value}"
        ) from None
