"""`EPIC-035M` — what one fill of the bot's own order is worth in the ladder's books.

Split out of `GridFacts` (the 400-line ceiling, `architecture-rule.md` §5.4; a pure move): the
trade report's fee is split by the asset it was paid in, and a fee in a third asset (BNB) is
priced in the quote asset at the moment of the fill.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_fresh_price_reader import (
    FreshPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    LevelFill,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    BUDGET_QUOTE_ASSET,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class GridFillConversion:
    """Turns a trade report into the ladder's `LevelFill`."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context

    def level_fill(self, fill: BotOrderFill) -> LevelFill:
        base_asset = self._context.base_asset
        fee = fill.fee_amount or Decimal(0)
        quote_fee = fee if fill.fee_asset == BUDGET_QUOTE_ASSET else Decimal(0)
        if fee > 0 and fill.fee_asset not in (None, base_asset, BUDGET_QUOTE_ASSET):
            quote_fee = self._fee_in_quote(fill.fee_asset, fee)
        return LevelFill(
            fill.client_order_id,
            fill.price,
            fill.quantity,
            base_fee=fee if fill.fee_asset == base_asset else Decimal(0),
            quote_fee=quote_fee,
        )

    def _fee_in_quote(self, asset: str | None, amount: Decimal) -> Decimal:
        """A fee paid in a third asset (BNB), in the quote asset at the moment of
        the fill (`EPIC-035M`). One that cannot be priced is counted in the run's
        `unpriced_fees` and said, never guessed or dropped without a trace."""
        state = self._context.state
        try:
            return amount * self._context.asset_price(str(asset))
        except FreshPriceUnavailableError as unavailable:
            logger.warning(
                "Bot %s: a fee of %s %s could not be priced in %s (%s); the "
                "profit and the total are short by it [unpriced-fee]",
                state.bot_id,
                amount,
                asset,
                BUDGET_QUOTE_ASSET,
                unavailable,
            )
            state.update(
                replace(state.runtime, unpriced_fees=state.runtime.unpriced_fees + 1)
            )
            return Decimal(0)
