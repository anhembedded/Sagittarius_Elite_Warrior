"""`EPIC-028E` — `GetOrderHistoryQuery` and `GetTradeHistoryQuery` answer one
ADR O5 page, newest first, from the addressed venue's own reader.

@details The reader is `FakeAccountHistoryReader`, the port's verified fake
(`AccountHistoryReaderContract`), with rows built by the contract's own
helpers, so a row here is one a real reader could return.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.history_scope import (
    EVERY_SYMBOL_SCAN_LIMIT,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_order_history import (
    GetOrderHistoryQuery,
    GetOrderHistoryQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_trade_history import (
    GetTradeHistoryQuery,
    GetTradeHistoryQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_gaps import (
    HistoryGaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HISTORY_PAGE_SIZE,
    HistoryPage,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
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


def test_every_symbol_finds_pairs_traded_since_the_requested_time_only() -> None:
    """`EPIC-028Q` — the handler asks the reader for the pairs active since
    the query's own `since`, so a pair traded before it is not scanned."""
    reader = FakeAccountHistoryReader(
        trades=[contract_trade("ETHUSDT", 1), contract_trade("BTCUSDT", 9)],
        now=CONTRACT_NOW,
    )

    page = GetTradeHistoryQueryHandler(_contexts(reader, reader)).execute(
        GetTradeHistoryQuery(
            venue=_FUTURES, symbol=None, since=_SINCE + timedelta(hours=5)
        )
    )

    assert page.scanned_symbols == ("BTCUSDT",)


_GAPS = HistoryGaps(order_history=("orders gap",), every_symbol=("pairs gap",))


@pytest.mark.parametrize(
    ("symbol", "notices"),
    [("BTCUSDT", ("orders gap",)), (None, ("orders gap", "pairs gap"))],
)
def test_order_pages_state_the_venues_gaps(
    symbol: str | None, notices: tuple[str, ...]
) -> None:
    """`EPIC-028Q` — the every-pair gap is shown only on an every-pair page."""
    reader = FakeAccountHistoryReader(now=CONTRACT_NOW, gaps=_GAPS)

    page = GetOrderHistoryQueryHandler(_contexts(reader, reader)).execute(
        GetOrderHistoryQuery(venue=_FUTURES, symbol=symbol, since=_SINCE)
    )

    assert page.notices == notices


@pytest.mark.parametrize(
    ("symbol", "notices"), [("BTCUSDT", ()), (None, ("pairs gap",))]
)
def test_trade_pages_state_only_the_every_symbol_gap(
    symbol: str | None, notices: tuple[str, ...]
) -> None:
    """A fill is never purged, so a trade page carries no order gap."""
    reader = FakeAccountHistoryReader(now=CONTRACT_NOW, gaps=_GAPS)

    page = GetTradeHistoryQueryHandler(_contexts(reader, reader)).execute(
        GetTradeHistoryQuery(venue=_SPOT, symbol=symbol, since=_SINCE)
    )

    assert page.notices == notices


@pytest.mark.parametrize("query_type", [GetOrderHistoryQuery, GetTradeHistoryQuery])
def test_a_naive_since_or_a_negative_page_is_refused(query_type: type) -> None:
    with pytest.raises(ValueError, match="timezone"):
        query_type(venue=_SPOT, symbol=None, since=_SINCE.replace(tzinfo=None))
    with pytest.raises(ValueError, match="page"):
        query_type(venue=_SPOT, symbol=None, since=_SINCE, page=-1)


class _RecordingReader(FakeAccountHistoryReader):
    """The verified fake, recording the pairs a history read reaches."""

    def __init__(self, open_symbols: list[str]) -> None:
        super().__init__(open_symbols=open_symbols, now=CONTRACT_NOW)
        self.read: list[str] = []

    def order_history(self, symbol: str, since: datetime) -> tuple[OrderRecord, ...]:
        self.read.append(symbol)
        return super().order_history(symbol, since)

    def trade_history(self, symbol: str, since: datetime) -> tuple[TradeRecord, ...]:
        self.read.append(symbol)
        return super().trade_history(symbol, since)


@pytest.mark.parametrize(
    "execute",
    [
        lambda contexts: GetOrderHistoryQueryHandler(contexts).execute(
            GetOrderHistoryQuery(venue=_SPOT, symbol=None, since=_SINCE)
        ),
        lambda contexts: GetTradeHistoryQueryHandler(contexts).execute(
            GetTradeHistoryQuery(venue=_SPOT, symbol=None, since=_SINCE)
        ),
    ],
    ids=["orders", "trades"],
)
def test_every_symbol_reads_at_most_the_scan_limit_and_says_so(execute) -> None:
    """`BUG-145` — a Spot Testnet account holds some five hundred assets, and
    an every-pair page read each one's history: Binance answered `-1003` and
    a bot's Start could no longer read its commission rate. The page reads
    the first `EVERY_SYMBOL_SCAN_LIMIT` pairs and names how many it left."""
    held = [f"C{n:03d}USDT" for n in range(EVERY_SYMBOL_SCAN_LIMIT + 495)]
    reader = _RecordingReader(held)

    page = execute(_contexts(reader, reader))

    assert reader.read == held[:EVERY_SYMBOL_SCAN_LIMIT]
    assert page.scanned_symbols == tuple(held[:EVERY_SYMBOL_SCAN_LIMIT])
    assert any(
        f"{EVERY_SYMBOL_SCAN_LIMIT} of {len(held)} active pairs" in notice
        for notice in page.notices
    )


def test_every_symbol_at_the_scan_limit_reads_them_all_without_a_notice() -> None:
    """`BUG-145`, the boundary: as many active pairs as the limit is the
    whole account, so nothing is said to be left out."""
    held = [f"C{n:03d}USDT" for n in range(EVERY_SYMBOL_SCAN_LIMIT)]
    reader = _RecordingReader(held)

    page = GetTradeHistoryQueryHandler(_contexts(reader, reader)).execute(
        GetTradeHistoryQuery(venue=_SPOT, symbol=None, since=_SINCE)
    )

    assert page.scanned_symbols == tuple(held)
    assert page.notices == ()
