"""`EPIC-029B` — the bot lifecycle, declared in one place (ADR D3, D12, D13, §3.1).

Every transition a bot can make is a row of `BOT_LIFECYCLE_TRANSITIONS`; nothing
else in the module sets a bot's state (`code/quality.md` §3, FSM cohesion). A
use case asks `next_state()` and gets either the next state or
`InvalidBotTransitionError`, naming the state and the event, for every pair the
table does not declare.

Two targets are not states, and the table says so instead of hiding them:

  · `REMOVED` — `delete` from DRAFT or STOPPED. A removed bot has no state;
    the store deletes its file. It is never persisted and never restored.
  · `PRIOR` — `reconcile_ok` from RECOVERING returns to the state the bot was
    in before the restart (RUNNING or PAUSED). `Bot` remembers it as
    `recovering_from` when it enters RECOVERING (`bot.py`).

`app_restart` is the restore rule of ADR D12 expressed as a transition, so a
loaded bot goes through this table like every other change: RUNNING and PAUSED
become RECOVERING, STARTING becomes HALTED (review round 2), and every other
state keeps itself. Nothing at start places an order (D12).

`halt` **(added by `EPIC-029E`)** is the ADR's "halts the bot" for a cause the
table had no column for: a level that keeps ending, an order the exchange
rejected, a counter order with nowhere to go (RUNNING or PAUSED), and an exit
slice that failed (STOPPING, naming the unsold remainder, §3.4). Each leads to
HALTED, whose exit is a resume that re-plans (D13) or a stop.
"""

from __future__ import annotations

from enum import Enum


class BotLifecycleState(str, Enum):
    """Where a bot is in its life. The values are what the store writes."""

    DRAFT = "DRAFT"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    RECOVERING = "RECOVERING"
    HALTED = "HALTED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class BotLifecycleEvent(str, Enum):
    """What can happen to a bot (ADR §3.1, the column headers)."""

    EDIT = "edit"
    DELETE = "delete"
    START = "start"
    LADDER_READY = "ladder_ready"
    START_REFUSED = "start_refused"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    STOP_CONFIRMED = "stop_confirmed"
    SWITCH_OFF = "switch_off"
    RECONCILE_OK = "reconcile_ok"
    RECONCILE_MISMATCH = "reconcile_mismatch"
    FAULT = "fault"
    APP_RESTART = "app_restart"
    HALT = "halt"


class BotLifecycleTarget(str, Enum):
    """The two table cells that are not a state; see the module docstring."""

    REMOVED = "REMOVED"
    PRIOR = "PRIOR"


class InvalidBotTransitionError(ValueError):
    """The table declares no transition for this state and event."""

    def __init__(self, state: BotLifecycleState, event: BotLifecycleEvent) -> None:
        super().__init__(
            f"A bot in {state.value} cannot take the event {event.value!r}"
        )
        self.state = state
        self.event = event


_S = BotLifecycleState
_E = BotLifecycleEvent
_T = BotLifecycleTarget

#: (current state, event) -> next state, `REMOVED` or `PRIOR`. ADR §3.1, row by row.
BOT_LIFECYCLE_TRANSITIONS: dict[
    tuple[BotLifecycleState, BotLifecycleEvent], BotLifecycleState | BotLifecycleTarget
] = {
    # --- DRAFT ---
    (_S.DRAFT, _E.EDIT): _S.DRAFT,
    (_S.DRAFT, _E.DELETE): _T.REMOVED,
    (_S.DRAFT, _E.START): _S.STARTING,
    (_S.DRAFT, _E.APP_RESTART): _S.DRAFT,
    # --- STARTING ---
    (_S.STARTING, _E.LADDER_READY): _S.RUNNING,
    (_S.STARTING, _E.START_REFUSED): _S.HALTED,
    (_S.STARTING, _E.STOP): _S.STOPPING,
    (_S.STARTING, _E.SWITCH_OFF): _S.HALTED,
    (_S.STARTING, _E.FAULT): _S.ERROR,
    (_S.STARTING, _E.APP_RESTART): _S.HALTED,
    # --- RUNNING ---
    (_S.RUNNING, _E.PAUSE): _S.PAUSED,
    (_S.RUNNING, _E.STOP): _S.STOPPING,
    (_S.RUNNING, _E.SWITCH_OFF): _S.HALTED,
    (_S.RUNNING, _E.FAULT): _S.ERROR,
    (_S.RUNNING, _E.HALT): _S.HALTED,
    (_S.RUNNING, _E.APP_RESTART): _S.RECOVERING,
    # --- PAUSED ---
    (_S.PAUSED, _E.RESUME): _S.RUNNING,
    (_S.PAUSED, _E.STOP): _S.STOPPING,
    (_S.PAUSED, _E.SWITCH_OFF): _S.HALTED,
    (_S.PAUSED, _E.FAULT): _S.ERROR,
    (_S.PAUSED, _E.HALT): _S.HALTED,
    (_S.PAUSED, _E.APP_RESTART): _S.RECOVERING,
    # --- RECOVERING ---
    (_S.RECOVERING, _E.STOP): _S.STOPPING,
    (_S.RECOVERING, _E.SWITCH_OFF): _S.RECOVERING,
    (_S.RECOVERING, _E.RECONCILE_OK): _T.PRIOR,
    (_S.RECOVERING, _E.RECONCILE_MISMATCH): _S.HALTED,
    (_S.RECOVERING, _E.FAULT): _S.ERROR,
    (_S.RECOVERING, _E.APP_RESTART): _S.RECOVERING,
    # --- HALTED --- (resume re-plans and asks again, D13)
    (_S.HALTED, _E.RESUME): _S.STARTING,
    (_S.HALTED, _E.STOP): _S.STOPPING,
    (_S.HALTED, _E.SWITCH_OFF): _S.HALTED,
    (_S.HALTED, _E.FAULT): _S.ERROR,
    (_S.HALTED, _E.APP_RESTART): _S.HALTED,
    # --- STOPPING --- (waits while the switch is off; never STOPPED early;
    # `stop` again is a retry, `EPIC-035C`)
    (_S.STOPPING, _E.STOP): _S.STOPPING,
    (_S.STOPPING, _E.STOP_CONFIRMED): _S.STOPPED,
    (_S.STOPPING, _E.SWITCH_OFF): _S.STOPPING,
    (_S.STOPPING, _E.FAULT): _S.ERROR,
    (_S.STOPPING, _E.HALT): _S.HALTED,
    (_S.STOPPING, _E.APP_RESTART): _S.STOPPING,
    # --- STOPPED ---
    (_S.STOPPED, _E.EDIT): _S.DRAFT,
    (_S.STOPPED, _E.DELETE): _T.REMOVED,
    (_S.STOPPED, _E.START): _S.STARTING,
    (_S.STOPPED, _E.APP_RESTART): _S.STOPPED,
    # --- ERROR --- (`stop` is the only way out; the lease is kept until then)
    (_S.ERROR, _E.STOP): _S.STOPPING,
    (_S.ERROR, _E.SWITCH_OFF): _S.ERROR,
    (_S.ERROR, _E.APP_RESTART): _S.ERROR,
}

#: The states a new run starts from: `start` here stamps a new `run_started_at`
#: (ADR D6, review round 2). Resuming from HALTED is the same run.
RUN_STARTING_STATES: frozenset[BotLifecycleState] = frozenset({_S.DRAFT, _S.STOPPED})

#: The states `reconcile_ok` may return to; `Bot` records one on entering RECOVERING.
RECOVERABLE_STATES: frozenset[BotLifecycleState] = frozenset({_S.RUNNING, _S.PAUSED})


def next_target(
    state: BotLifecycleState, event: BotLifecycleEvent
) -> BotLifecycleState | BotLifecycleTarget:
    """The table's cell for `(state, event)`.

    @raise InvalidBotTransitionError The table declares no such transition.
    """
    try:
        return BOT_LIFECYCLE_TRANSITIONS[(state, event)]
    except KeyError:
        raise InvalidBotTransitionError(state, event) from None


def is_declared(state: BotLifecycleState, event: BotLifecycleEvent) -> bool:
    """Whether the table has a cell for `(state, event)`; the UI enables a control on it."""
    return (state, event) in BOT_LIFECYCLE_TRANSITIONS
