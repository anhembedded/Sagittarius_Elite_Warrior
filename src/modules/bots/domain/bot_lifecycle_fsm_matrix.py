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

`resume` from RECOVERING **(added by `BUG-204`)** is the owner's way out on the desktop:
the order session, which a restart leaves closed, opens with it, and the session's
opening has the bot reconcile. It is a self-loop, since the reconcile decides the next
state (`reconcile_ok` or `reconcile_mismatch`), not the click.

`AWAITING_RECOVERY` **(added by `EPIC-042B`)** is a halt a kind named transient: the
ladder is off, the base is kept, the exits are watched, and the bot waits for the cause
to stay clear for the dwell, then resumes through the person's Resume path
(`condition_cleared`). Its events and why each row is there: ADR 042 §2.1.

`halt` also answers a quiet price feed (`EPIC-035A`, `PRICE_FEED_STALE`), which
can be heard in any state that holds or lays orders: STARTING and RECOVERING
gained the cell for it, RUNNING and PAUSED already had it. STOPPING has one but
is deliberately not halted by it (`PRICE_STALENESS_HALTS`).
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
    AWAITING_RECOVERY = "AWAITING_RECOVERY"
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
    HALT_TRANSIENT = "halt_transient"
    CONDITION_CLEARED = "condition_cleared"
    BUDGET_EXHAUSTED = "budget_exhausted"


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
    (_S.STARTING, _E.HALT): _S.HALTED,
    (_S.STARTING, _E.HALT_TRANSIENT): _S.AWAITING_RECOVERY,
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
    (_S.RUNNING, _E.HALT_TRANSIENT): _S.AWAITING_RECOVERY,
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
    # `BUG-204` - Resume opens the venue's order session and reconciles; the bot
    # stays RECOVERING until `reconcile_ok` or `reconcile_mismatch` moves it.
    (_S.RECOVERING, _E.RESUME): _S.RECOVERING,
    (_S.RECOVERING, _E.SWITCH_OFF): _S.RECOVERING,
    (_S.RECOVERING, _E.RECONCILE_OK): _T.PRIOR,
    (_S.RECOVERING, _E.RECONCILE_MISMATCH): _S.HALTED,
    (_S.RECOVERING, _E.HALT): _S.HALTED,
    (_S.RECOVERING, _E.FAULT): _S.ERROR,
    (_S.RECOVERING, _E.APP_RESTART): _S.RECOVERING,
    # --- HALTED --- (resume re-plans and asks again, D13)
    (_S.HALTED, _E.RESUME): _S.STARTING,
    (_S.HALTED, _E.STOP): _S.STOPPING,
    (_S.HALTED, _E.SWITCH_OFF): _S.HALTED,
    (_S.HALTED, _E.FAULT): _S.ERROR,
    (_S.HALTED, _E.APP_RESTART): _S.HALTED,
    # --- AWAITING_RECOVERY --- (`EPIC-042`, ADR 042 §2.1: a halt a kind named transient,
    # waiting for its cause to stay clear for the dwell. Only RUNNING and STARTING enter
    # it: PAUSED and RECOVERING have no `halt_transient` cell, so the owner's Pause and a
    # restart's closed order session are never undone by a machine, D8.)
    (_S.AWAITING_RECOVERY, _E.CONDITION_CLEARED): _S.STARTING,
    (_S.AWAITING_RECOVERY, _E.RESUME): _S.STARTING,
    (_S.AWAITING_RECOVERY, _E.BUDGET_EXHAUSTED): _S.HALTED,
    (_S.AWAITING_RECOVERY, _E.HALT): _S.HALTED,
    (_S.AWAITING_RECOVERY, _E.STOP): _S.STOPPING,
    (_S.AWAITING_RECOVERY, _E.SWITCH_OFF): _S.HALTED,
    (_S.AWAITING_RECOVERY, _E.FAULT): _S.ERROR,
    # A restart is not a person's confirmation and closes the order session (D9, O1 a).
    (_S.AWAITING_RECOVERY, _E.APP_RESTART): _S.HALTED,
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

#: The states in which a bot owns a price stream (`EPIC-035A`): every state but
#: the two a bot rests in. A stop loss is watched while the bot may still hold
#: orders or a position, whether or not any chart is open.
PRICE_STREAM_STATES: frozenset[BotLifecycleState] = frozenset(_S) - {
    _S.DRAFT,
    _S.STOPPED,
}

#: The states a quiet feed halts (`EPIC-035A`): those that hold orders or are
#: laying them, and can still be told to stop placing. Not STOPPING (a stop
#: needs no price, and a halt would turn the user's Stop into a resume that
#: re-plans a ladder), and not HALTED or ERROR (they already place nothing).
PRICE_STALENESS_HALTS: frozenset[BotLifecycleState] = frozenset(
    {_S.STARTING, _S.RUNNING, _S.PAUSED, _S.RECOVERING}
)

#: The states whose Resume re-plans: it cancels the bot's tagged orders and proposes a
#: fresh ladder, which a person (or the host's `--resume-halted`) confirms. HALTED has
#: always been one; AWAITING_RECOVERY is the same re-plan, run by a person ahead of the
#: automatic one (`EPIC-042`). Every consumer that treated "HALTED" as "Resume re-plans"
#: asks here, so the second state is answered in one place.
RESUME_PROPOSES_STATES: frozenset[BotLifecycleState] = frozenset(
    {_S.HALTED, _S.AWAITING_RECOVERY}
)

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


def restarts_into_recovering(state: BotLifecycleState) -> bool:
    """Whether a restart moves a bot in `state` to RECOVERING: the restart rule's own answer.

    RUNNING and PAUSED do, and so does RECOVERING itself (a second restart before a
    reconcile). Anything that must know which saved bots a restart will hold back asks
    here, not a list of its own (`EPIC-038D`'s mainnet refusal for `--resume-recovering`).
    """
    return (
        is_declared(state, BotLifecycleEvent.APP_RESTART)
        and next_target(state, BotLifecycleEvent.APP_RESTART)
        is BotLifecycleState.RECOVERING
    )


def permits_edit(state: BotLifecycleState) -> bool:
    """Whether a bot in `state` may be edited (DRAFT and STOPPED): the table's own answer."""
    return is_declared(state, BotLifecycleEvent.EDIT)


def permits_delete(state: BotLifecycleState) -> bool:
    """Whether a bot in `state` may be deleted (DRAFT and STOPPED): the table's own answer."""
    return (
        is_declared(state, BotLifecycleEvent.DELETE)
        and next_target(state, BotLifecycleEvent.DELETE) is BotLifecycleTarget.REMOVED
    )
