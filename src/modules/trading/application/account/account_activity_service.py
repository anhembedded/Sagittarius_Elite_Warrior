"""`EPIC-028J` — `IAccountActivity`, implemented over venue-addressed
queries.

Same shape as `OrderEntryTermsService`: a façade over the dispatcher, one
instance per venue, adding a name and a type and no rule. Each answer's
type is checked, so an unbound handler is named instead of handing `None`
to a table.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_account_summary.query import (
    GetAccountSummaryQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_orders.query import (
    GetOpenOrdersQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_order_history.query import (
    GetOrderHistoryQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_trade_history.query import (
    GetTradeHistoryQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HistoryPage,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_request import (
    HistoryRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_activity import (
    IAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class AccountActivityService(IAccountActivity):
    """The account activity of one venue (`EPIC-028J`)."""

    def __init__(self, dispatcher: ICommandDispatcher, venue: TradingVenue) -> None:
        self._dispatcher = dispatcher
        self._venue = venue

    def summary(self) -> AccountSummary | None:
        query = GetAccountSummaryQuery(venue=self._venue)
        answer = self._dispatcher.dispatch(GetAccountSummaryQuery, query)
        if answer is None:
            return None
        return _typed(query, answer, AccountSummary)

    def open_orders(self) -> tuple[Order, ...]:
        query = GetOpenOrdersQuery(venue=self._venue)
        return _typed(
            query, self._dispatcher.dispatch(GetOpenOrdersQuery, query), tuple
        )

    def order_history(self, request: HistoryRequest) -> HistoryPage[OrderRecord]:
        query = GetOrderHistoryQuery(
            venue=self._venue,
            symbol=request.symbol,
            since=request.since,
            page=request.page,
            desk_symbol=request.desk_symbol,
        )
        return _typed(
            query, self._dispatcher.dispatch(GetOrderHistoryQuery, query), HistoryPage
        )

    def trade_history(self, request: HistoryRequest) -> HistoryPage[TradeRecord]:
        query = GetTradeHistoryQuery(
            venue=self._venue,
            symbol=request.symbol,
            since=request.since,
            page=request.page,
            desk_symbol=request.desk_symbol,
        )
        return _typed(
            query, self._dispatcher.dispatch(GetTradeHistoryQuery, query), HistoryPage
        )


def _typed[T](query: object, answer: object, answer_type: type[T]) -> T:
    if not isinstance(answer, answer_type):
        raise TypeError(
            f"{type(query).__name__} was answered with {type(answer).__name__}, "
            f"not {answer_type.__name__} — its handler is not bound"
        )
    return answer
