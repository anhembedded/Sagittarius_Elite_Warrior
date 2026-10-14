"""`EPIC-029E` — the Spot close: sell the base the bot bought (ADR §3.1, D6, D21).

@details In slices at or below the per-order cap, each waiting its turn
(`send_exit_slices`). A base worth less than the exchange's minimum is kept as dust. A halt
leaves the base: the ladder comes off and what was bought stays held (the owner's 2026-10-09
halt), so the user decides.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_exit_slices import (
    send_exit_slices,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_closer import (
    IExposureCloser,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.stop_progress import (
    StopProgress,
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

    def closes_on_halt(self) -> bool:
        return False

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
        return send_exit_slices(
            self._context,
            slices,
            lambda piece: self._context.gateway.market_sell(piece, price),
        )
