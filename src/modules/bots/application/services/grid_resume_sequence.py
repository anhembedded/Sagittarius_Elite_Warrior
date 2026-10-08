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
ladder go out — after the price is read from the book again (`EPIC-035J`): a
market that moved past `RESUME_PRICE_TOLERANCE` since the proposal refuses the
ladder, with `PROPOSAL_PRICE_MOVED`, and the user resumes again. **Both steps ask the store first** (`EPIC-035G`, D6, `GridStorageWatch.admits_relaunch`): a ladder is not laid over a file that cannot say so, whoever asks, the user or the rate-limit timer. A proposal lives in memory; after a restart the user resumes
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
    halt_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_start_sequence import (
    GridStartSequence,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_storage_watch import (
    GridStorageWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.symbol_status_gate import (
    SymbolStatusGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_fresh_price_reader import (
    FreshPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    buys_within_capital,
    resized_for_inventory,
    unplaced_inventory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    LadderRules,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.reference_price import (
    RESUME_PRICE_TOLERANCE,
    moved_beyond,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)

logger = logging.getLogger("App.Bots.GridExecutor")

#: Introduces the sentence a resume proposal adds to the bot's reason detail.
_UNPLACED_MARK = "; resume proposal: "


@dataclass(frozen=True, slots=True)
class ResumeProposal:
    """The ladder a resume would lay, and the inventory it was sized to."""

    plan: GridPlan
    inventory: OwnerInventory
    #: The base the plan's SELL levels do not reach (`EPIC-035R`); it stays held.
    unplaced_inventory: Decimal


class GridResumeSequence:
    """Proposes a fresh ladder for a HALTED Grid, and lays it once confirmed."""

    def __init__(
        self,
        context: GridRunContext,
        start: GridStartSequence,
        status: SymbolStatusGate,
        storage: GridStorageWatch,
    ) -> None:
        self._context = context
        self._start = start
        self._status = status
        self._storage = storage
        self._housekeeping = GridHousekeeping(context)

    def propose(self, price: Decimal) -> ResumeProposal | None:
        """Steps 1–3; `None` when a step could not finish (the reason says why)."""
        state = self._context.state
        if not self._storage.admits_relaunch():
            return None
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
            if report.failed.kind in (
                OrderOutcomeKind.FAULT,
                OrderOutcomeKind.RATE_LIMITED,
                OrderOutcomeKind.KEY_REJECTED,
            ):
                fail_with(state, report.failed, f"cancel {report.client_order_id}")
            return None
        proposal = self._proposal_for(price, registration.inventory)
        self._name_unplaced(proposal.unplaced_inventory)
        logger.info(
            "Bot %s: resume proposes %d orders from %s with %s held; waiting for confirmation",
            state.bot_id,
            len(proposal.plan.order_levels),
            price,
            proposal.inventory.quantity,
        )
        return proposal

    def _proposal_for(
        self, price: Decimal, inventory: OwnerInventory
    ) -> ResumeProposal:
        """The plan at `price` over `inventory` (`EPIC-035R`): SELLs sized to
        what is held, BUYs sized to the capital it leaves."""
        terms = self._context.terms
        rules = LadderRules(terms.step_size, terms.min_notional)
        sells = resized_for_inventory(
            plan(self._context.params, terms, price),
            inventory.quantity,
            terms.min_notional,
        )
        left = self._context.params.capital_quote - inventory.cost
        sized = buys_within_capital(sells, left, rules)
        return ResumeProposal(
            sized, inventory, unplaced_inventory(sized, inventory.quantity)
        )

    def _name_unplaced(self, unplaced: Decimal) -> None:
        """Say on the HALTED bot which base no SELL level covers, once: an earlier
        resume's sentence is replaced, and removed when nothing is left over."""
        runtime = self._context.state.runtime
        head = runtime.reason_detail.split(_UNPLACED_MARK)[0]
        detail = head
        if unplaced > 0:
            detail = (
                f"{head}{_UNPLACED_MARK}{unplaced} {self._context.base_asset} of the "
                "inventory has no SELL level to go on and stays unplaced"
            )
        if detail != runtime.reason_detail:
            reason = runtime.reason or GridReason.SWITCH_OFF
            self._context.state.update(runtime.with_reason(reason, detail))

    def confirm(self, proposal: ResumeProposal) -> None:
        """Lay the confirmed ladder: HALTED → STARTING → RUNNING, unless the
        symbol does not trade (`SymbolStatusGate`) or the market has left the price
        it was proposed at (`PROPOSAL_PRICE_MOVED`): then it stays HALTED."""
        if not self._storage.admits_relaunch():
            return
        if not self._status.admits() or self._moved_since(proposal):
            return
        self._context.state.transition(BotLifecycleEvent.RESUME)
        self._start.place_ladder(proposal.plan, proposal.inventory)

    def _moved_since(self, proposal: ResumeProposal) -> bool:
        state = self._context.state
        proposed = proposal.plan.last_price
        try:
            now = self._context.reference_price.fresh()
        except FreshPriceUnavailableError:
            logger.warning(
                "Bot %s: the book could not be read to re-price the resume",
                state.bot_id,
                exc_info=True,
            )
            halt_with(
                state,
                GridReason.PROPOSAL_PRICE_MOVED,
                f"the price could not be read to confirm the ladder proposed at "
                f"{proposed}; nothing was laid, resume again",
            )
            return True
        if not moved_beyond(proposed, now, RESUME_PRICE_TOLERANCE):
            return False
        halt_with(
            state,
            GridReason.PROPOSAL_PRICE_MOVED,
            f"the price moved from {proposed} to {now}, more than "
            f"{RESUME_PRICE_TOLERANCE:.1%}, since the ladder was proposed; "
            "nothing was laid, resume again",
        )
        return True
