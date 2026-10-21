"""`BUG-258` — the opening's fills, booked into the saved runtime from the exchange's record.

A start counts its opening from the exchange (`IOpeningStrategy`), yet the runtime books a market
order's fill only when the user-data stream reports it (`GridFacts._apply_fill`). A stream that is
late or down left the saved position at 0 beside the one the exchange and trading both showed, so
the first gap reconcile after RUNNING disagreed with a WARNING and a second run could act on it.

Once the opening is counted, this books each slice's trades from the order history, the same way
`GridMissedFills` replays a ladder order, and remembers their trade ids (`AppliedFills`), so the
stream's report of the same fill, early or late, is counted once. A slice the history does not hold
is left to the stream, as before.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_fill_conversion import (
    GridFillConversion,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_books import (
    book_market_fill,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class OpeningFillsBooking:
    """Books the fills of the start's opening slices from the order history."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context
        self._conversion = GridFillConversion(context)

    def book(self) -> None:
        context = self._context
        state = context.state
        since = state.bot.lifecycle.run_started_at
        if since is None:
            return
        for client_order_id in sorted(context.off_ladder.openings):
            try:
                record = context.gateway.order_record(client_order_id, since)
                trades = (
                    ()
                    if record is None
                    else context.gateway.order_trades(record.exchange_order_id, since)
                )
            except AccountHistoryUnavailableError as error:
                logger.warning(
                    "Bot %s: the history of opening slice %s did not answer (%s); the stream "
                    "will report its fills [opening-fills]",
                    state.bot_id,
                    client_order_id,
                    error,
                )
                continue
            for trade in trades:
                if context.applied_fills.knows(client_order_id, trade.trade_id):
                    continue
                context.applied_fills.record(client_order_id, trade.trade_id)
                fill = self._conversion.level_fill(
                    BotOrderFill(
                        client_order_id,
                        trade.side,
                        trade.price,
                        trade.quantity,
                        trade.fee,
                        trade.fee_asset,
                        trade.trade_id,
                        trade.realized_pnl,
                    )
                )
                state.update(
                    book_market_fill(
                        state.runtime, trade.side, fill
                    ).with_fill_commission(fill.base_fee, fill.quote_fee, fill.price)
                )
                logger.info(
                    "Bot %s: opening fill %s of %s booked from the exchange's record: "
                    "%s at %s [opening-fills]",
                    state.bot_id,
                    trade.trade_id,
                    client_order_id,
                    trade.quantity,
                    trade.price,
                )
