"""`EPIC-029E` — a bot's reads of the venue's history of its own orders and fills.

@details Paged reads of the account's order and trade history for one symbol, split from the
gateway (`architecture-rule.md` §5.4): the gateway sends and cancels, this reads back. A ladder is
many orders, so the reconcile reads the history once for all of them rather than once per order
(one read per order would multiply the rate-limit weight by the ladder's size).
"""

from __future__ import annotations

from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HISTORY_PAGE_SIZE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_request import (
    HistoryRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_activity import (
    IAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)


class BotOrderHistory:
    """Reads one symbol's order and trade history."""

    def __init__(self, activity: IAccountActivity, symbol: str) -> None:
        self._activity = activity
        self._symbol = symbol

    def order_record(self, client_order_id: str, since: datetime) -> OrderRecord | None:
        """The venue's history of one of the bot's orders, or `None` when
        the history since `since` does not hold it.
        @raise AccountHistoryUnavailableError The venue did not answer."""
        request = HistoryRequest(self._symbol, since)
        while True:
            page = self._activity.order_history(request)
            for record in page.rows:
                if record.order.client_order_id == client_order_id:
                    return record
            if (request.page + 1) * HISTORY_PAGE_SIZE >= page.total_rows:
                return None
            request = request.at_page(request.page + 1)

    def order_records(
        self, client_order_ids: frozenset[str], since: datetime
    ) -> dict[str, OrderRecord]:
        """The venue's history of each of the named orders that `since` holds,
        read in one pass over the history.
        @raise AccountHistoryUnavailableError The venue did not answer."""
        request = HistoryRequest(self._symbol, since)
        found: dict[str, OrderRecord] = {}
        while True:
            page = self._activity.order_history(request)
            for record in page.rows:
                if record.order.client_order_id in client_order_ids:
                    found[record.order.client_order_id] = record
            if (request.page + 1) * HISTORY_PAGE_SIZE >= page.total_rows:
                return found
            request = request.at_page(request.page + 1)

    def orders_trades(
        self, exchange_order_ids: frozenset[int], since: datetime
    ) -> dict[int, tuple[TradeRecord, ...]]:
        """Every fill of each of the named orders since `since`, read in one pass over the trade
        history (`BUG-258`: an opening of several slices is not one scan per slice).
        @raise AccountHistoryUnavailableError The venue did not answer."""
        request = HistoryRequest(self._symbol, since)
        found: dict[int, list[TradeRecord]] = {
            order: [] for order in exchange_order_ids
        }
        while True:
            page = self._activity.trade_history(request)
            for row in page.rows:
                if row.order_id in found:
                    found[row.order_id].append(row)
            if (request.page + 1) * HISTORY_PAGE_SIZE >= page.total_rows:
                return {order: tuple(rows) for order, rows in found.items()}
            request = request.at_page(request.page + 1)
