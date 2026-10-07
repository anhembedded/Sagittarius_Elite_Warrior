"""`EPIC-034D`, `EPIC-034H` — a bot's readiness lifecycle: Connect, Design, Run.

Six states: nothing selected (`NOT_CONNECTED`), the venue's account being read
(`CONNECTING`), could not be read (`FAILED`), and, once it was read, how far
the bot is: `DESIGNING` (the plan has a constraint to meet), `RUN_BLOCKED`
(the plan holds and something else stands in Start's way) and `READY` (Start
may be pressed). The chart and the Plan are open only once connected, which is
`DESIGNING` and after (D1).

A timer re-read (`REFRESH`) of a connected venue keeps its state while it runs,
so a slow read never locks a chart the user is looking at; only a failed
re-read does. Selecting another bot starts again whatever the state, and a late
answer for a bot that is no longer selected never reaches this table: the
screen's read fence drops it first (`async-ui-action-rule.md` §1).

Each assessment of the bot (`assess_readiness`) arrives as exactly one of
three events, and moves a connected bot to the state that names it. The table
holds no readiness of its own: the assessment is the truth, this is the
lifecycle that says what the screen shows around it (the primary action's
label, the progress) and what each event may do.
"""

from __future__ import annotations

from enum import Enum


class ReadinessState(str, Enum):
    NOT_CONNECTED = "NOT_CONNECTED"
    CONNECTING = "CONNECTING"
    FAILED = "FAILED"
    DESIGNING = "DESIGNING"
    RUN_BLOCKED = "RUN_BLOCKED"
    READY = "READY"


class ReadinessEvent(str, Enum):
    SELECTED = "SELECTED"
    DESELECTED = "DESELECTED"
    #: The user pressed Retry.
    RETRY = "RETRY"
    #: The timer asks again.
    REFRESH = "REFRESH"
    READ_OK = "READ_OK"
    READ_FAILED = "READ_FAILED"
    #: The assessment has a Design item left.
    DESIGN_OPEN = "DESIGN_OPEN"
    #: The plan holds; a Run item is left.
    RUN_OPEN = "RUN_OPEN"
    #: Nothing is left.
    ALL_CLEAR = "ALL_CLEAR"


_S = ReadinessState
_E = ReadinessEvent

#: Connected: the account was read, however far the bot is beyond it.
CONNECTED_STATES = (_S.DESIGNING, _S.RUN_BLOCKED, _S.READY)
_ANY = tuple(ReadinessState)

READINESS_TRANSITIONS: dict[tuple[ReadinessState, ReadinessEvent], ReadinessState] = {
    **{(state, _E.SELECTED): _S.CONNECTING for state in _ANY},
    **{(state, _E.DESELECTED): _S.NOT_CONNECTED for state in _ANY},
    (_S.FAILED, _E.RETRY): _S.CONNECTING,
    (_S.FAILED, _E.REFRESH): _S.CONNECTING,
    (_S.CONNECTING, _E.REFRESH): _S.CONNECTING,
    (_S.CONNECTING, _E.READ_OK): _S.DESIGNING,
    (_S.CONNECTING, _E.READ_FAILED): _S.FAILED,
    **{(state, _E.REFRESH): state for state in CONNECTED_STATES},
    **{(state, _E.RETRY): _S.CONNECTING for state in CONNECTED_STATES},
    **{(state, _E.READ_OK): state for state in CONNECTED_STATES},
    **{(state, _E.READ_FAILED): _S.FAILED for state in CONNECTED_STATES},
    **{(state, _E.DESIGN_OPEN): _S.DESIGNING for state in CONNECTED_STATES},
    **{(state, _E.RUN_OPEN): _S.RUN_BLOCKED for state in CONNECTED_STATES},
    **{(state, _E.ALL_CLEAR): _S.READY for state in CONNECTED_STATES},
}


def next_state(state: ReadinessState, event: ReadinessEvent) -> ReadinessState:
    """The state `event` leads to, or `state` itself when the table declares
    nothing: a refresh before any bot is selected, a stale answer, an
    assessment of a bot whose account is not connected."""
    return READINESS_TRANSITIONS.get((state, event), state)
