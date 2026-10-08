"""`EPIC-029E` — what a refused or failed order does to a running Grid (ADR D9, §3.1).

  · `SWITCH_OFF` → `switch_off`: trading is off; HALTED (STOPPING waits). While
    STARTING it writes `START_CUT_BY_SWITCH_OFF`: the partial ladder cannot be
    cancelled with the session closed, so the cancel is owed and paid when
    trading is enabled (`BUG-190`, as `EPIC-035C` does for a restart).
  · `REFUSED` → `start_refused` while STARTING, `halt` otherwise, naming the
    refusal.
  · `FAULT` → `fault`: the request raised; ERROR, whose exit is `stop`.

`halt_with` is the same for a halt the ladder itself decided (`Halt`).
`fault_with` is `fault` for a step that raised outside any order: a price,
terms or history read, a value the ladder refused. The executor's one fault
boundary calls it, so no failure leaves a bot in a state with no reason.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_order_gateway import (
    OrderOutcome,
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_run_state import (
    BotRunState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

#: What a start cut by the switch tells the user, after the order's own detail.
START_CUT_BY_SWITCH_OFF_DETAIL = (
    "trading went off while this bot was starting; its tagged orders may still "
    "rest and are cancelled when trading is enabled"
)


def fail_with(state: BotRunState, outcome: OrderOutcome, what: str) -> None:
    """Move the bot for `outcome` (not done); `what` names the order."""
    detail = f"{what}: {outcome.detail}"
    if outcome.kind is OrderOutcomeKind.SWITCH_OFF:
        if state.state is BotLifecycleState.STARTING:
            _apply(
                state,
                BotLifecycleEvent.SWITCH_OFF,
                GridReason.START_CUT_BY_SWITCH_OFF,
                f"{detail}; {START_CUT_BY_SWITCH_OFF_DETAIL}",
            )
        else:
            _apply(state, BotLifecycleEvent.SWITCH_OFF, GridReason.SWITCH_OFF, detail)
    elif outcome.kind is OrderOutcomeKind.FAULT:
        _apply(state, BotLifecycleEvent.FAULT, GridReason.ORDER_FAILED, detail)
    elif state.state is BotLifecycleState.STARTING:
        _apply(state, BotLifecycleEvent.START_REFUSED, GridReason.START_REFUSED, detail)
    else:
        _apply(state, BotLifecycleEvent.HALT, GridReason.ORDER_REFUSED, detail)


def fault_with(state: BotRunState, what: str, error: Exception) -> None:
    """ERROR for a step that raised; `what` names the step."""
    detail = f"{what}: {type(error).__name__}; see the log"
    _apply(state, BotLifecycleEvent.FAULT, GridReason.TASK_FAILED, detail)


def halt_with(state: BotRunState, reason: GridReason, detail: str) -> None:
    _apply(state, BotLifecycleEvent.HALT, reason, detail)


def _apply(
    state: BotRunState, event: BotLifecycleEvent, reason: GridReason, detail: str
) -> None:
    if state.can(event):
        state.transition(event, reason, detail)
    else:
        state.update(state.runtime.with_reason(reason, detail))
