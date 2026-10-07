"""`EPIC-034D` — the Connect step's own lifecycle, apart from any bot's.

Four states: nothing selected (`NOT_CONNECTED`), the venue's account being
read (`CONNECTING`), read (`CONNECTED`), and could not be read (`FAILED`). The
chart and the Plan are open only in `CONNECTED` (D1); `EPIC-034H` completes the
readiness lifecycle this one starts.

A timer re-read (`REFRESH`) of a connected venue keeps it `CONNECTED` while it
runs, so a slow read never locks a chart the user is looking at; only a failed
re-read does. Selecting another bot starts again whatever the state, and a late
answer for a bot that is no longer selected never reaches this table: the
screen's read fence drops it first (`async-ui-action-rule.md` §1).
"""

from __future__ import annotations

from enum import Enum


class ConnectState(str, Enum):
    NOT_CONNECTED = "NOT_CONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    FAILED = "FAILED"


class ConnectEvent(str, Enum):
    SELECTED = "SELECTED"
    DESELECTED = "DESELECTED"
    #: The user pressed Retry.
    RETRY = "RETRY"
    #: The timer asks again.
    REFRESH = "REFRESH"
    READ_OK = "READ_OK"
    READ_FAILED = "READ_FAILED"


_ANY = tuple(ConnectState)

CONNECT_TRANSITIONS: dict[tuple[ConnectState, ConnectEvent], ConnectState] = {
    **{(state, ConnectEvent.SELECTED): ConnectState.CONNECTING for state in _ANY},
    **{(state, ConnectEvent.DESELECTED): ConnectState.NOT_CONNECTED for state in _ANY},
    (ConnectState.FAILED, ConnectEvent.RETRY): ConnectState.CONNECTING,
    (ConnectState.FAILED, ConnectEvent.REFRESH): ConnectState.CONNECTING,
    (ConnectState.CONNECTING, ConnectEvent.REFRESH): ConnectState.CONNECTING,
    (ConnectState.CONNECTED, ConnectEvent.REFRESH): ConnectState.CONNECTED,
    (ConnectState.CONNECTED, ConnectEvent.RETRY): ConnectState.CONNECTING,
    (ConnectState.CONNECTING, ConnectEvent.READ_OK): ConnectState.CONNECTED,
    (ConnectState.CONNECTING, ConnectEvent.READ_FAILED): ConnectState.FAILED,
    (ConnectState.CONNECTED, ConnectEvent.READ_OK): ConnectState.CONNECTED,
    (ConnectState.CONNECTED, ConnectEvent.READ_FAILED): ConnectState.FAILED,
}


def next_state(state: ConnectState, event: ConnectEvent) -> ConnectState:
    """The state `event` leads to, or `state` itself when the table declares
    nothing: a refresh before any bot is selected, a stale answer."""
    return CONNECT_TRANSITIONS.get((state, event), state)
