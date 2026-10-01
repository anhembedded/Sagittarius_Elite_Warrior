"""`EPIC-028J` — `AccountActivityService` reads a desk's summary, open
orders and histories through queries addressed to its own venue."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account.account_activity_service import (
    AccountActivityService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_account_summary import (
    GetAccountSummaryQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_orders import (
    GetOpenOrdersQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_order_history import (
    GetOrderHistoryQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_trade_history import (
    GetTradeHistoryQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    SpotAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HistoryPage,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_request import (
    HistoryRequest,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_SPOT = TradingVenue.SPOT_TESTNET
_SINCE = datetime(2026, 9, 24, tzinfo=UTC)
_EMPTY_PAGE: HistoryPage[object] = HistoryPage(
    rows=(), page=2, total_rows=0, scanned_symbols=("BTCUSDT",)
)


class _AnsweringDispatcher(ICommandDispatcher):
    def __init__(self, answers: dict[type, object]) -> None:
        self._answers = answers
        self.dispatched: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.dispatched.append(input_dto)
        return self._answers.get(handler_class)


def test_every_read_is_addressed_to_the_services_venue() -> None:
    summary = SpotAccountSummary(
        venue=_SPOT,
        available_balance=Decimal(5),
        equity=None,
        quote_asset="USDT",
        quote_free=Decimal(5),
        quote_locked=Decimal(0),
    )
    dispatcher = _AnsweringDispatcher(
        {
            GetAccountSummaryQuery: summary,
            GetOpenOrdersQuery: (),
            GetOrderHistoryQuery: _EMPTY_PAGE,
            GetTradeHistoryQuery: _EMPTY_PAGE,
        }
    )
    service = AccountActivityService(dispatcher, _SPOT)
    request = HistoryRequest(symbol="BTCUSDT", since=_SINCE, page=2)

    assert service.summary() is summary
    assert service.open_orders() == ()
    assert service.order_history(request) is _EMPTY_PAGE
    assert service.trade_history(request) is _EMPTY_PAGE
    assert dispatcher.dispatched == [
        GetAccountSummaryQuery(venue=_SPOT),
        GetOpenOrdersQuery(venue=_SPOT),
        GetOrderHistoryQuery(venue=_SPOT, symbol="BTCUSDT", since=_SINCE, page=2),
        GetTradeHistoryQuery(venue=_SPOT, symbol="BTCUSDT", since=_SINCE, page=2),
    ]


def test_an_unread_account_has_no_summary() -> None:
    service = AccountActivityService(_AnsweringDispatcher({}), _SPOT)

    assert service.summary() is None


def test_an_unbound_handler_is_named_rather_than_handed_to_a_table() -> None:
    service = AccountActivityService(_AnsweringDispatcher({}), _SPOT)

    with pytest.raises(TypeError, match="GetOrderHistoryQuery .* not bound"):
        service.order_history(HistoryRequest(symbol=None, since=_SINCE))


@pytest.mark.parametrize(
    ("since", "page", "message"),
    [
        (datetime(2026, 9, 24), 0, "timezone-aware"),  # noqa: DTZ001 - the naive datetime under test
        (_SINCE, -1, "zero or more"),
    ],
)
def test_a_history_request_is_one_instant_and_a_real_page(
    since: datetime, page: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        HistoryRequest(symbol=None, since=since, page=page)


def test_another_page_keeps_the_span() -> None:
    first = HistoryRequest(symbol=None, since=_SINCE)

    assert first.at_page(3) == HistoryRequest(symbol=None, since=_SINCE, page=3)
