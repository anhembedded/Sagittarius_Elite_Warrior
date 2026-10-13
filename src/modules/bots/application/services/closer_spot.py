"""`EPIC-029E` — the Spot close: sell the base the bot bought (ADR §3.1, D6, D21).

@details In slices at or below the per-order cap, each waiting its turn. A base worth less than
the exchange's minimum is kept as dust. A refused or failed slice halts the bot, naming the
unsold remainder; a rate limit or a closed order session waits.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_order_gateway import (
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_order_failure import (
    fail_with,
    halt_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stopping_wait import (
    wait_in_stopping,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_closer import (
    IExposureCloser,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.stop_progress import (
    StopProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.market_slices import (
    base_slices,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistrationResult,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class SpotExposureCloser(IExposureCloser):
    """Sells the Spot base the bot holds."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context

    def close(
        self, registration: OwnerBudgetRegistrationResult, price: Decimal
    ) -> StopProgress | None:
        """`None` when the base is sold or kept as dust; otherwise how the stop ended."""
        inventory = (
            registration.inventory.quantity if registration.inventory else Decimal(0)
        )
        if inventory * price < self._context.terms.min_notional:
            logger.info(
                "Bot %s: %s %s kept as dust, worth less than the %s minimum",
                self._context.state.bot_id,
                inventory,
                self._context.base_asset,
                self._context.terms.min_notional,
            )
            return None
        slices = base_slices(
            inventory, price, self._context.cap, self._context.terms.market_step
        )
        remaining = sum(slices, Decimal(0))
        for index, piece in enumerate(slices, start=1):
            outcome = self._context.gateway.market_sell(piece, price)
            self._context.off_ladder.add(outcome.client_order_id)
            logger.info(
                "Bot %s: exit slice %d of %s -> %s %s",
                self._context.state.bot_id,
                index,
                piece,
                outcome.kind.value,
                outcome.client_order_id or outcome.detail,
            )
            if outcome.kind is OrderOutcomeKind.SWITCH_OFF:
                wait_in_stopping(
                    self._context, f"exit slice {index} refused: trading is off"
                )
                return StopProgress.WAITING_FOR_TRADING
            if outcome.kind is OrderOutcomeKind.KEY_REJECTED:
                fail_with(self._context.state, outcome, f"exit slice {index}")
                return StopProgress.ENDED
            if outcome.kind is OrderOutcomeKind.RATE_LIMITED:
                # Nothing was sent: the next run derives what is left and sells it.
                wait_in_stopping(
                    self._context, f"exit slice {index} not sent: {outcome.detail}"
                )
                return StopProgress.WAITING_ON_EXCHANGE
            if not outcome.done:
                # A slice that raised may still have executed: say so rather
                # than count it unsold; the next stop or resume derives again.
                unsold = (
                    "possibly unsold (the request may have executed)"
                    if outcome.kind is OrderOutcomeKind.FAULT
                    else "unsold"
                )
                halt_with(
                    self._context.state,
                    GridReason.EXIT_SLICE_FAILED,
                    f"{remaining} {unsold} after slice {index}: {outcome.detail}",
                )
                return StopProgress.ENDED
            remaining -= piece
        return None
