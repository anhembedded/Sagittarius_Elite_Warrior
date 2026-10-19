"""`BOT-189` — tells the rest of the app that an order of the ladder filled whole.

The one place a `FilledOrder` becomes a `BotOrderFilledEvent`, so that no way a fill is settled (the
stream, a parked counter replayed, a reconcile's missed fill) can forget it. It only reads what the
reaction already holds and publishes; it changes no order and no state of the bot.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_order_filled_event import (
    BotOrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_filled_order import (
    FilledOrder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    BUDGET_QUOTE_ASSET,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class GridFillAnnouncer:
    """Publishes one event per order that filled whole."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context

    def announce(self, filled: Iterable[FilledOrder]) -> None:
        for order in filled:
            self._context.events.publish(
                BotOrderFilledEvent(
                    bot_id=self._context.state.bot_id,
                    order_id=order.client_order_id,
                    side=order.side.value,
                    price=order.price,
                    quantity=order.quantity,
                    level=order.level_index,
                    realised_total=order.realised_total,
                    completed_cycles=order.completed_cycles,
                    quote_asset=BUDGET_QUOTE_ASSET,
                    cycle_profit=order.cycle_profit,
                )
            )
            logger.debug(
                "Bot %s: order %s filled whole, announced [order-filled]",
                self._context.state.bot_id,
                order.client_order_id,
            )
