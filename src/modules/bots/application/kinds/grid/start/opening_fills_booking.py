"""`BUG-258` — the opening's fills, booked into the saved runtime from the exchange's record.

A start counts its opening from the exchange (`IOpeningStrategy`), yet the runtime books a market
order's fill only when the user-data stream reports it (`GridFacts._apply_fill`). A stream that is
late or down left the saved position at 0 beside the one the exchange and trading both showed, so
the first gap reconcile after RUNNING disagreed with a WARNING and a second run could act on it.

Once the opening is counted, this books each slice's trades from the order history, read in one
pass for every slice, the way `GridMissedFills` replays a ladder order, and remembers their trade
ids (`AppliedFills`), so the stream's report of the same fill, early or late, is counted once. What
the history does not hold yet is said (`[opening-fills]`) and left to the stream, as before.
"""

from __future__ import annotations

import logging
from decimal import Decimal

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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
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
        slices = sorted(context.off_ladder.openings)
        if since is None or not slices:
            return
        try:
            records = context.gateway.order_records(frozenset(slices), since)
            trades = (
                context.gateway.orders_trades(
                    frozenset(record.exchange_order_id for record in records.values()),
                    since,
                )
                if records
                else {}
            )
        except AccountHistoryUnavailableError as error:
            logger.warning(
                "Bot %s: the history of the %d opening slice(s) did not answer (%s); the "
                "stream will report their fills [opening-fills]",
                state.bot_id,
                len(slices),
                error,
            )
            return
        for client_order_id in slices:
            record = records.get(client_order_id)
            if record is None:
                logger.info(
                    "Bot %s: opening slice %s is not in the history yet; the stream will "
                    "report its fills [opening-fills]",
                    state.bot_id,
                    client_order_id,
                )
                continue
            self._book_slice(client_order_id, record, trades[record.exchange_order_id])

    def _book_slice(
        self, client_order_id: str, record: OrderRecord, trades: tuple[TradeRecord, ...]
    ) -> None:
        context = self._context
        state = context.state
        known = Decimal(0)
        for trade in trades:
            known += trade.quantity
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
                book_market_fill(state.runtime, trade.side, fill).with_fill_commission(
                    fill.base_fee, fill.quote_fee, fill.price
                )
            )
            logger.info(
                "Bot %s: opening fill %s of %s booked from the exchange's record: %s at %s "
                "[opening-fills]",
                state.bot_id,
                trade.trade_id,
                client_order_id,
                trade.quantity,
                trade.price,
            )
        if known < record.executed_quantity:
            logger.info(
                "Bot %s: opening slice %s: the history shows %s of the %s it executed; the "
                "stream will report the rest [opening-fills]",
                state.bot_id,
                client_order_id,
                known,
                record.executed_quantity,
            )
