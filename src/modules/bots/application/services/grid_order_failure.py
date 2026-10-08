"""`EPIC-029E` — what a refused or failed order does to a running Grid (ADR D9, §3.1).

  · `SWITCH_OFF` → `switch_off`: trading is off; HALTED (STOPPING waits).
  · `REFUSED` → `start_refused` while STARTING, `halt` otherwise, naming the
    refusal.
  · `FAULT` → `fault`: the request raised; ERROR, whose exit is `stop`.
  · `SYMBOL_NOT_TRADING` / `SYMBOL_NOT_LISTED` → a refusal that names the
    symbol's status (`EPIC-035E`): `start_refused` while STARTING, `halt`
    otherwise. A RUNNING ladder pauses instead, in `GridLadderPlacer`, because
    only there are the orders not yet placed in hand to be held.

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

#: The reason a refusal that names its cause records, whatever state it met.
_REFUSAL_REASONS: dict[OrderOutcomeKind, GridReason] = {
    OrderOutcomeKind.SYMBOL_NOT_TRADING: GridReason.SYMBOL_NOT_TRADING,
    OrderOutcomeKind.SYMBOL_NOT_LISTED: GridReason.SYMBOL_DELISTED,
}


def fail_with(state: BotRunState, outcome: OrderOutcome, what: str) -> None:
    """Move the bot for `outcome` (not done); `what` names the order."""
    detail = f"{what}: {outcome.detail}"
    if outcome.kind is OrderOutcomeKind.SWITCH_OFF:
        _apply(state, BotLifecycleEvent.SWITCH_OFF, GridReason.SWITCH_OFF, detail)
    elif outcome.kind is OrderOutcomeKind.FAULT:
        _apply(state, BotLifecycleEvent.FAULT, GridReason.ORDER_FAILED, detail)
    else:
        _refuse(state, outcome.kind, detail)


def _refuse(state: BotRunState, kind: OrderOutcomeKind, detail: str) -> None:
    """HALTED for a refusal: STARTING says `start_refused`, any other state `halt`."""
    starting = state.state is BotLifecycleState.STARTING
    default = GridReason.START_REFUSED if starting else GridReason.ORDER_REFUSED
    event = BotLifecycleEvent.START_REFUSED if starting else BotLifecycleEvent.HALT
    _apply(state, event, _REFUSAL_REASONS.get(kind, default), detail)


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
