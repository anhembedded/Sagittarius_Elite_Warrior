"""`EPIC-028E` — `GetOrderHistoryQuery` and `GetTradeHistoryQuery` answer one
ADR O5 page, newest first, from the addressed venue's own reader.

@details The reader is `FakeAccountHistoryReader`, the port's verified fake
(`AccountHistoryReaderContract`), with rows built by the contract's own
helpers, so a row here is one a real reader could return.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_order_history import (
    GetOrderHistoryQuery,
    GetOrderHistoryQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_trade_history import (
    GetTradeHistoryQuery,
    GetTradeHistoryQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HISTORY_PAGE_SIZE,
    HistoryPage,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.contract_account_history_reader import (
    CONTRACT_NOW,
    contract_order,
    contract_trade,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_history_reader import (
    FakeAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT = TradingVenue.SPOT_TESTNET
_SINCE = contract_order("BTCUSDT", 0).created_at


def _contexts(
    futures: FakeAccountHistoryReader, spot: FakeAccountHistoryReader
) -> FakeVenueContexts:
    return FakeVenueContexts(
        replace(fake_venue_context(_FUTURES), history_reader=futures),
        replace(fake_venue_context(_SPOT), history_reader=spot),
    )


def test_order_history_is_newest_first_from_the_addressed_venue() -> None:
    spot = FakeAccountHistoryReader(
        orders=[
            *(contract_order("BTCUSDT", h) for h in (3, 1, 2)),
            contract_order("ETHUSDT", 4),
        ],
        now=CONTRACT_NOW,
    )
    futures = FakeAccountHistoryReader(
        orders=[contract_order("BTCUSDT", 9)], now=CONTRACT_NOW
    )

    page = GetOrderHistoryQueryHandler(_contexts(futures, spot)).execute(
        GetOrderHistoryQuery(venue=_SPOT, symbol="BTCUSDT", since=_SINCE)
    )

    assert [row.created_at - _SINCE for row in page.rows] == [
        timedelta(hours=3),
        timedelta(hours=2),
        timedelta(hours=1),
    ]
    assert page.scanned_symbols == ("BTCUSDT",)


def test_a_page_holds_fifty_rows_and_the_total_counts_them_all() -> None:
    reader = FakeAccountHistoryReader(
        orders=[contract_order("BTCUSDT", h) for h in range(1, 121)], now=CONTRACT_NOW
    )
    handler = GetOrderHistoryQueryHandler(_contexts(reader, reader))

    first = handler.execute(
        GetOrderHistoryQuery(venue=_FUTURES, symbol="BTCUSDT", since=_SINCE)
    )
    last = handler.execute(
        GetOrderHistoryQuery(venue=_FUTURES, symbol="BTCUSDT", since=_SINCE, page=2)
    )

    assert len(first.rows) == HISTORY_PAGE_SIZE
    assert first.rows[0].created_at - _SINCE == timedelta(hours=120)
    assert (first.total_rows, first.page_count) == (120, 3)
    assert [row.created_at - _SINCE for row in last.rows] == [
        timedelta(hours=h) for h in range(20, 0, -1)
    ]


def test_a_page_past_the_last_is_empty_but_keeps_the_total() -> None:
    reader = FakeAccountHistoryReader(
        orders=[contract_order("BTCUSDT", 1)], now=CONTRACT_NOW
    )

    page = GetOrderHistoryQueryHandler(_contexts(reader, reader)).execute(
        GetOrderHistoryQuery(venue=_FUTURES, symbol="BTCUSDT", since=_SINCE, page=4)
    )

    assert page == HistoryPage(
        rows=(), page=4, total_rows=1, scanned_symbols=("BTCUSDT",)
    )


def test_every_symbol_means_the_readers_active_symbols_merged() -> None:
    reader = FakeAccountHistoryReader(
        trades=[
            contract_trade("ETHUSDT", 5),
            contract_trade("BTCUSDT", 7),
            contract_trade("BTCUSDT", 2),
        ],
        open_symbols=["SOLUSDT"],
        now=CONTRACT_NOW,
    )

    page = GetTradeHistoryQueryHandler(_contexts(reader, reader)).execute(
        GetTradeHistoryQuery(venue=_SPOT, symbol=None, since=_SINCE)
    )

    assert [(row.symbol, row.trade_id) for row in page.rows] == [
        ("BTCUSDT", 7),
        ("ETHUSDT", 5),
        ("BTCUSDT", 2),
    ]
    assert page.scanned_symbols == ("BTCUSDT", "ETHUSDT", "SOLUSDT")


def test_rows_older_than_since_are_left_out() -> None:
    reader = FakeAccountHistoryReader(
        trades=[contract_trade("BTCUSDT", h) for h in (1, 10)], now=CONTRACT_NOW
    )

    page = GetTradeHistoryQueryHandler(_contexts(reader, reader)).execute(
        GetTradeHistoryQuery(
            venue=_FUTURES, symbol="BTCUSDT", since=_SINCE + timedelta(hours=5)
        )
    )

    assert [row.trade_id for row in page.rows] == [10]


@pytest.mark.parametrize("query_type", [GetOrderHistoryQuery, GetTradeHistoryQuery])
def test_a_naive_since_or_a_negative_page_is_refused(query_type: type) -> None:
    with pytest.raises(ValueError, match="timezone"):
        query_type(venue=_SPOT, symbol=None, since=_SINCE.replace(tzinfo=None))
    with pytest.raises(ValueError, match="page"):
        query_type(venue=_SPOT, symbol=None, since=_SINCE, page=-1)
