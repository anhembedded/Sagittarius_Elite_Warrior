"""`EPIC-034G` — the four states a chart can be live in, as one table."""

from __future__ import annotations

import itertools

import pytest
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_fsm_matrix import (
    COMMAND_EVENT,
    COMMAND_WORDS,
    LIVE_CHART_TRANSITIONS,
    STATE_COMMAND,
    STATE_WORDS,
    LiveChartCommand,
    LiveChartEvent,
    LiveChartState,
    next_state,
)

S = LiveChartState
E = LiveChartEvent
C = LiveChartCommand

#: The whole table, written out once more by hand: a row added to or dropped
#: from the matrix fails here until the table says so too.
_EXPECTED = {
    (S.HISTORY, E.GO_LIVE_REQUESTED): S.CONNECTING,
    (S.HISTORY, E.SHUT_DOWN): S.HISTORY,
    (S.CONNECTING, E.LOAD_RESTARTED): S.CONNECTING,
    (S.CONNECTING, E.STREAM_STARTED): S.LIVE,
    (S.CONNECTING, E.STREAM_FAILED): S.ERROR,
    (S.CONNECTING, E.CANCEL_REQUESTED): S.HISTORY,
    (S.CONNECTING, E.SHUT_DOWN): S.HISTORY,
    (S.LIVE, E.LOAD_RESTARTED): S.CONNECTING,
    (S.LIVE, E.STREAM_FAILED): S.ERROR,
    (S.LIVE, E.STOP_REQUESTED): S.HISTORY,
    (S.LIVE, E.SHUT_DOWN): S.HISTORY,
    (S.ERROR, E.LOAD_RESTARTED): S.CONNECTING,
    (S.ERROR, E.RETRY_REQUESTED): S.CONNECTING,
    (S.ERROR, E.STOP_REQUESTED): S.HISTORY,
    (S.ERROR, E.SHUT_DOWN): S.HISTORY,
}


def test_the_matrix_is_exactly_the_declared_table() -> None:
    assert LIVE_CHART_TRANSITIONS == _EXPECTED


@pytest.mark.parametrize(("state", "event"), list(itertools.product(S, E)))
def test_every_pair_is_declared_or_dropped(state: S, event: E) -> None:
    assert next_state(state, event) is _EXPECTED.get((state, event))


def test_each_state_offers_one_command_with_its_own_words() -> None:
    assert STATE_COMMAND == {
        S.HISTORY: C.GO_LIVE,
        S.CONNECTING: C.CANCEL,
        S.LIVE: C.STOP_LIVE,
        S.ERROR: C.RETRY,
    }
    assert [COMMAND_WORDS[c] for c in STATE_COMMAND.values()] == [
        "Go live",
        "Cancel",
        "Stop live",
        "Retry",
    ]
    assert [STATE_WORDS[s] for s in S] == ["History", "Connecting…", "Live", "Error"]


@pytest.mark.parametrize("state", list(S))
def test_the_command_a_state_offers_is_a_move_from_that_state(state: S) -> None:
    """A button the table has no move for would be a dead button."""
    event = COMMAND_EVENT[STATE_COMMAND[state]]
    assert next_state(state, event) is not None


@pytest.mark.parametrize("state", list(S))
def test_a_command_always_leaves_its_state(state: S) -> None:
    """Whatever state the chart is in, the user can leave it by its command."""
    event = COMMAND_EVENT[STATE_COMMAND[state]]
    assert next_state(state, event) is not state
