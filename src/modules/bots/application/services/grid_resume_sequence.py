"""`EPIC-029E` — resuming a HALTED Grid is always safe (ADR D13, O2).

`propose` runs when the user asks to resume a HALTED bot. In this order:

  1. **Register the budget**, which derives the inventory from the exchange
     (D6) — after a disable the old ladder may still rest; after an Emergency
     Stop the bot may be flat, partly flat or still invested (§1.4).
  2. **Cancel every order carrying the bot's tag**: no ladder is ever laid
     over orphans.
  3. **Propose a new plan** from the current price and that inventory: the
     SELL side sized to what the bot holds, no opening buy (§3.4).

Nothing is placed. The bot stays HALTED with the proposal until the user
confirms it (`confirm`): only then does `resume` move it to STARTING and the
ladder go out. A proposal lives in memory; after a restart the user resumes
again, which proposes afresh from the exchange as it then is.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_order_gateway import (
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_housekeeping import (
    GridHousekeeping,
    refusal_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_order_failure import (
    fail_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_start_sequence import (
    GridStartSequence,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.symbol_status_gate import (
    SymbolStatusGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    resized_for_inventory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)

logger = logging.getLogger("App.Bots.GridExecutor")


@dataclass(frozen=True, slots=True)
class ResumeProposal:
    """The ladder a resume would lay, and the inventory it was sized to."""

    plan: GridPlan
    inventory: OwnerInventory


class GridResumeSequence:
    """Proposes a fresh ladder for a HALTED Grid, and lays it once confirmed."""

    def __init__(
        self,
        context: GridRunContext,
        start: GridStartSequence,
        status: SymbolStatusGate,
    ) -> None:
        self._context = context
        self._start = start
        self._status = status
        self._housekeeping = GridHousekeeping(context)

    def propose(self, price: Decimal) -> ResumeProposal | None:
        """Steps 1–3; `None` when a step could not finish (the reason says why)."""
        state = self._context.state
        registration = self._housekeeping.register()
        if not registration.registered or registration.inventory is None:
            reason = state.runtime.reason or GridReason.SWITCH_OFF
            detail = (
                f"resume waits: the budget was refused: {refusal_text(registration)}"
            )
            state.update(state.runtime.with_reason(reason, detail))
            return None
        report = self._housekeeping.cancel_tagged()
        if report.failed is not None:
            if report.failed.kind is OrderOutcomeKind.FAULT:
                fail_with(state, report.failed, f"cancel {report.client_order_id}")
            return None
        inventory = registration.inventory
        proposal = ResumeProposal(
            resized_for_inventory(
                plan(self._context.params, self._context.terms, price),
                inventory.quantity,
                self._context.terms.min_notional,
            ),
            inventory,
        )
        logger.info(
            "Bot %s: resume proposes %d orders from %s with %s held; waiting for confirmation",
            state.bot_id,
            len(proposal.plan.order_levels),
            price,
            inventory.quantity,
        )
        return proposal

    def confirm(self, proposal: ResumeProposal) -> None:
        """Lay the confirmed ladder: HALTED → STARTING → RUNNING, unless the
        symbol does not trade (`SymbolStatusGate`): then it stays HALTED."""
        if not self._status.admits():
            return
        self._context.state.transition(BotLifecycleEvent.RESUME)
        self._start.place_ladder(proposal.plan, proposal.inventory)
