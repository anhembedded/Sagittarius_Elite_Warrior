"""`EPIC-028E` — `SpotHistoryReader` and `FuturesHistoryReader` over a real
HTTP round trip to the fake exchange server.

@details Orders are placed and canceled through the real trading clients, so
the history read back is the account's own. The Spot fake refuses a span
longer than twenty-four hours with Binance's `-1127`, the way the real
exchange does, so a seven-day read that comes back at all was split into
windows the exchange accepts. The server itself runs on this machine and
ignores signatures (`tests/sanity/binance_fake_server.py`); what this proves is
the request shapes, the paging and the payload mapping, end to end.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from binance.client import Client
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.cached_history_reader import (
    CachedAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_history_reader import (
    FuturesHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_metadata_provider import (
    FuturesMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_session_factory import (
    FuturesSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.listed_symbols import (
    ListedSymbols,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_history_reader import (
    SpotHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_metadata_provider import (
    SpotMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client import (
    SpotTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.active_symbol import (
    ActiveReason,
    ActiveSymbol,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_fill_reporter import (
    FakeOrderFillReporter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests" / "sanity"))
from binance_fake_server import FakeServerUrls, run_binance_fake_server


class _Credentials(IExchangeCredentialsProvider):
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="fake-key", api_secret="fake-secret"),
            CredentialsSource.FILE,
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise AssertionError("not used by this test")

    def remove_stored(self) -> None:
        raise AssertionError("not used by this test")


@contextmanager
def _fake_exchange() -> Iterator[FakeServerUrls]:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        yield urls


def _order(cid: str, order_type: OrderType) -> Order:
    is_limit = order_type is OrderType.LIMIT
    return Order(
        client_order_id=ClientOrderId(cid),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=order_type,
        quantity=Decimal("0.1"),
        price=Decimal(40000) if is_limit else None,
        time_in_force=TimeInForce.GTC if is_limit else None,
    )


def _week_ago() -> datetime:
    return datetime.now(UTC) - timedelta(days=7)


def _spot() -> tuple[SpotTradingClient, SpotHistoryReader]:
    sessions = SpotSessionFactory()
    cache = InMemorySymbolOrderMetadataCache()
    metadata = SpotMetadataProvider(sessions, cache)
    trading = SpotTradingClient(
        sessions,
        _Credentials(),
        metadata,
        OrderSubmissionMode.LIVE,
        FakeOrderFillReporter(),
    )
    return trading, SpotHistoryReader(
        sessions, _Credentials(), ListedSymbols(metadata, cache)
    )


def test_a_week_of_spot_orders_reads_back_filled_and_canceled() -> None:
    with _fake_exchange():
        trading, history = _spot()
        trading.place_order(_order("SEW-hist-market01", OrderType.MARKET))
        trading.place_order(_order("SEW-hist-limit001", OrderType.LIMIT))
        trading.cancel_order("BTCUSDT", "SEW-hist-limit001")

        rows = history.order_history("BTCUSDT", _week_ago())

    by_id = {row.order.client_order_id: row for row in rows}
    filled = by_id[ClientOrderId("SEW-hist-market01")]
    assert filled.order.status is OrderStatus.FILLED
    assert filled.executed_quantity == Decimal("0.1")
    assert filled.average_price == Decimal(50000)
    canceled = by_id[ClientOrderId("SEW-hist-limit001")]
    assert canceled.order.status is OrderStatus.CANCELED
    assert canceled.average_price is None


def test_a_spot_fill_reads_back_with_its_fee_in_the_received_asset() -> None:
    with _fake_exchange():
        trading, history = _spot()
        trading.place_order(_order("SEW-hist-market02", OrderType.MARKET))

        fills = history.trade_history("BTCUSDT", _week_ago())

    assert len(fills) == 1
    assert fills[0].side is OrderSide.BUY
    assert fills[0].quantity == Decimal("0.1")
    assert fills[0].price == Decimal(50000)
    assert fills[0].fee == Decimal("0.0001")
    assert fills[0].fee_asset == "BTC"


def test_paging_a_spot_week_twice_sends_the_windows_once() -> None:
    """`EPIC-028Q` — each page re-runs the query; behind the cache the second
    run sends nothing, where the bare reader sends all eight windows again."""
    since = _week_ago()
    with _fake_exchange() as urls:
        _, bare = _spot()
        cached = CachedAccountHistoryReader(bare)

        cached.trade_history("BTCUSDT", since)
        first = urls.requests.count(("GET", "/api/v3/myTrades"))
        cached.trade_history("BTCUSDT", since)
        after_cached = urls.requests.count(("GET", "/api/v3/myTrades"))
        bare.trade_history("BTCUSDT", since)
        after_bare = urls.requests.count(("GET", "/api/v3/myTrades"))

    assert first >= 7
    assert after_cached == first
    assert after_bare == 2 * first


def test_spot_active_symbols_are_the_listed_pairs_of_what_the_account_holds() -> None:
    """The fake account holds BTC, ETH and USDT; both pairs are listed."""
    with _fake_exchange():
        _, history = _spot()

        assert history.active_symbols(_week_ago()) == (
            ActiveSymbol("BTCUSDT", ActiveReason.HELD),
            ActiveSymbol("ETHUSDT", ActiveReason.HELD),
        )


def test_a_canceled_futures_order_reads_back_and_there_are_no_fills() -> None:
    """A resting Futures order is placed and canceled, never filled (a
    market fill's history is `test_futures_fills_against_fake_server.py`)."""
    with _fake_exchange():
        sessions = FuturesSessionFactory()
        metadata = FuturesMetadataProvider(sessions, InMemorySymbolOrderMetadataCache())
        trading = FuturesTradingClient(
            sessions,
            _Credentials(),
            metadata,
            OrderSubmissionMode.LIVE,
        )
        history = FuturesHistoryReader(sessions, _Credentials())
        trading.place_order(_order("SEW-hist-fut-lim01", OrderType.LIMIT))
        active_while_open = history.active_symbols(_week_ago())
        trading.cancel_order("BTCUSDT", "SEW-hist-fut-lim01")

        rows = history.order_history("BTCUSDT", _week_ago())
        fills = history.trade_history("BTCUSDT", _week_ago())

    assert active_while_open == (ActiveSymbol("BTCUSDT", ActiveReason.OPEN_ORDER),)
    assert [(row.order.client_order_id, row.order.status) for row in rows] == [
        (ClientOrderId("SEW-hist-fut-lim01"), OrderStatus.CANCELED)
    ]
    assert fills == ()


def test_a_futures_week_read_is_not_refused_for_a_start_older_than_seven_days() -> None:
    """`BUG-173` — the desk asks for "now minus seven days"; by the time the
    request reaches Binance that start is older than seven days and `allOrders`
    and `userTrades` answer -4181 `Invalid start time`. The reader keeps its
    start inside what the exchange accepts."""
    with _fake_exchange():
        sessions = FuturesSessionFactory()
        history = FuturesHistoryReader(sessions, _Credentials())

        orders = history.order_history("BTCUSDT", _week_ago())
        fills = history.trade_history("BTCUSDT", _week_ago())

    assert orders == ()
    assert fills == ()
