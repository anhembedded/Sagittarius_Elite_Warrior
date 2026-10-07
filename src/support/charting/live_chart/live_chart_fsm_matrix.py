"""`EPIC-034G` — whether a chart is live, as one lifecycle.

Four states a user can tell apart, the one command each offers, and the events
that move between them. It is a **view** of what `LiveChartCoordinator` does
(sync, then stream), not a second lifecycle: the chart dispatches an event
when it asks the coordinator for something and when the coordinator reports
back, and never decides a state on its own.

| State | Words on the chip | The command | Means |
| :-- | :-- | :-- | :-- |
| `HISTORY` | History | Go live | Stored candles only; no network (`BUG-107`) |
| `CONNECTING` | Connecting… | Cancel | Syncing and opening the stream |
| `LIVE` | Live | Stop live | The stream is open |
| `ERROR` | Error, with its reason | Retry | The sync or the stream failed |

An event that is not declared for a state is dropped by the chart: a report
that was already on its way when the user cancelled must not move a chart
that has since left that request.
"""

from __future__ import annotations

from enum import Enum


class LiveChartState(str, Enum):
    HISTORY = "HISTORY"
    CONNECTING = "CONNECTING"
    LIVE = "LIVE"
    ERROR = "ERROR"


class LiveChartEvent(str, Enum):
    #: The user (or an owner) asked for the live stream.
    GO_LIVE_REQUESTED = "GO_LIVE_REQUESTED"
    #: A new first window was asked for while live: another symbol or
    #: timeframe syncs and streams again.
    LOAD_RESTARTED = "LOAD_RESTARTED"
    #: The coordinator reported the stream open.
    STREAM_STARTED = "STREAM_STARTED"
    #: The coordinator reported the sync or the stream failed.
    STREAM_FAILED = "STREAM_FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    STOP_REQUESTED = "STOP_REQUESTED"
    RETRY_REQUESTED = "RETRY_REQUESTED"
    #: The owner closed the chart; its stream is released.
    SHUT_DOWN = "SHUT_DOWN"


class LiveChartCommand(str, Enum):
    """What the user can ask of the chart, one per state."""

    GO_LIVE = "GO_LIVE"
    CANCEL = "CANCEL"
    STOP_LIVE = "STOP_LIVE"
    RETRY = "RETRY"


S = LiveChartState
E = LiveChartEvent

LIVE_CHART_TRANSITIONS: dict[tuple[LiveChartState, LiveChartEvent], LiveChartState] = {
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

#: The one command each state offers.
STATE_COMMAND: dict[LiveChartState, LiveChartCommand] = {
    S.HISTORY: LiveChartCommand.GO_LIVE,
    S.CONNECTING: LiveChartCommand.CANCEL,
    S.LIVE: LiveChartCommand.STOP_LIVE,
    S.ERROR: LiveChartCommand.RETRY,
}

#: The event a command dispatches.
COMMAND_EVENT: dict[LiveChartCommand, LiveChartEvent] = {
    LiveChartCommand.GO_LIVE: E.GO_LIVE_REQUESTED,
    LiveChartCommand.CANCEL: E.CANCEL_REQUESTED,
    LiveChartCommand.STOP_LIVE: E.STOP_REQUESTED,
    LiveChartCommand.RETRY: E.RETRY_REQUESTED,
}

#: The words of each state's chip.
STATE_WORDS: dict[LiveChartState, str] = {
    S.HISTORY: "History",
    S.CONNECTING: "Connecting…",
    S.LIVE: "Live",
    S.ERROR: "Error",
}

#: The words of each command, as its action and button read.
COMMAND_WORDS: dict[LiveChartCommand, str] = {
    LiveChartCommand.GO_LIVE: "Go live",
    LiveChartCommand.CANCEL: "Cancel",
    LiveChartCommand.STOP_LIVE: "Stop live",
    LiveChartCommand.RETRY: "Retry",
}


def next_state(state: LiveChartState, event: LiveChartEvent) -> LiveChartState | None:
    """The state `event` leads to from `state`; `None` when it is not
    declared there."""
    return LIVE_CHART_TRANSITIONS.get((state, event))
