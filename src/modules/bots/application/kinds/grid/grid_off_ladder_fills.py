"""`EPIC-029E` — the fills of orders no level holds: the bot's market orders and its exits.

Split from `GridFacts` (the 400-line ceiling, `architecture-rule.md` §5.4): a fill whose client
order id no level holds is either one of the bot's market orders (the opening buy, an exit slice,
the exchange-side protective stop), booked into the inventory without a cycle, or not the bot's at
all, which is ignored and logged.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_exit_report import (
    GridExitReport,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_books import (
    book_exit_fill,
    book_market_fill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    LevelFill,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class GridOffLadderFills:
    """Books a fill that no level of the ladder holds."""

    def __init__(
        self, context: GridRunContext, supervise_protection: Callable[[], None]
    ) -> None:
        self._context = context
        self._supervise_protection = supervise_protection
        self._exit_report = GridExitReport(context)

    def book(self, fill: BotOrderFill, level_fill: LevelFill) -> None:
        state = self._context.state
        order_id = fill.client_order_id
        if order_id not in self._context.off_ladder:
            logger.info(
                "Bot %s: fill of %s ignored; no level holds it and the bot "
                "neither sent it as a market order nor took it off the ladder",
                state.bot_id,
                order_id,
            )
            return
        booked = (
            book_exit_fill
            if self._context.off_ladder.is_exit(order_id)
            else book_market_fill
        )
        state.update(
            booked(state.runtime, fill.side, level_fill).with_fill_commission(
                level_fill.base_fee, level_fill.quote_fee, level_fill.price
            )
        )
        if self._is_protective_stop(order_id):
            # The exchange ran the stop that stands over the position: the look at the stops
            # reads its status and the bot stops (`EPIC-039L`).
            self._supervise_protection()
        if self._context.off_ladder.is_exit(order_id):
            self._exit_report.after_exit_fill()

    def _is_protective_stop(self, client_order_id: str) -> bool:
        return any(
            stop.client_order_id == client_order_id
            for stop in self._context.state.runtime.protective_stops
        )
