"""`EPIC-021J` — `FuturesTradingClient`'s full order lifecycle (place →
appears in `get_open_orders()` → cancel → gone, for a resting order; a
market order fills, `EPIC-028O`) against a real HTTP round
trip through the fake server's new stateful futures routes.

@details Same "what this proves" boundary as the other `EPIC-021`
fake-server integration tests: the fixture serves fixed/state-derived
responses regardless of signature/timestamp, so this proves the whole call
chain (client construction, signing headers attached, URL routing, JSON
parsing, VO assembly) runs unchanged end to end — not Binance's own
signature validation.

Constructs `FuturesTradingClient` with `OrderSubmissionMode.LIVE` directly
— the `OrderSubmissionMode.LIVE` usage guard
(`test_order_submission_mode_live_is_restricted.py`) scans only `src/` and
`scripts/`, precisely so a test exercising the adapter's LIVE code path
against a local fixture (never real money, never real network) is not
mistaken for a second production entry point. Before this test,
`place_order()`'s `else: client.futures_create_order(**params)` branch had
zero coverage anywhere in the suite — this closes that gap.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from binance.client import Client
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests" / "sanity"))
from binance_fake_server import run_binance_fake_server


class _FakeCredentialsProvider:
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="fake-key", api_secret="fake-secret"),
            CredentialsSource.FILE,
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise NotImplementedError("not used by this test")

    def remove_stored(self) -> None:
        raise AssertionError("not used by this test")


def _order(client_order_id: str = "SEW-lifecycle0001") -> Order:
    """A resting order: `EPIC-028O`'s fake fills a market order at once, so
    the open-and-cancel lifecycle is a limit order's."""
    return Order(
        client_order_id=ClientOrderId(client_order_id),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.002"),
        price=Decimal(50000),
        time_in_force=TimeInForce.GTC,
    )


def _market_order(client_order_id: str, side: OrderSide, quantity: str) -> Order:
    return Order(
        client_order_id=ClientOrderId(client_order_id),
        symbol="BTCUSDT",
        side=side,
        order_type=OrderType.MARKET,
        quantity=Decimal(quantity),
    )


def test_placed_order_appears_in_open_orders_then_cancel_removes_it() -> None:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        session_factory = FuturesSessionFactory()
        metadata_provider = FuturesMetadataProvider(
            session_factory, InMemorySymbolOrderMetadataCache()
        )
        client = FuturesTradingClient(
            session_factory,
            _FakeCredentialsProvider(),
            metadata_provider,
            OrderSubmissionMode.LIVE,
        )
        order = _order()

        client.place_order(order)
        open_orders = client.get_open_orders("BTCUSDT")
        assert [o.client_order_id for o in open_orders] == [order.client_order_id]
        assert open_orders[0].status.name == "NEW"

        canceled = client.cancel_order("BTCUSDT", str(order.client_order_id))
        assert canceled.status.name == "CANCELED"
        assert client.get_open_orders("BTCUSDT") == []


def test_cancel_all_orders_returns_what_was_open_and_clears_the_book() -> None:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        session_factory = FuturesSessionFactory()
        metadata_provider = FuturesMetadataProvider(
            session_factory, InMemorySymbolOrderMetadataCache()
        )
        client = FuturesTradingClient(
            session_factory,
            _FakeCredentialsProvider(),
            metadata_provider,
            OrderSubmissionMode.LIVE,
        )
        client.place_order(_order("SEW-lifecycle0002"))
        client.place_order(_order("SEW-lifecycle0003"))

        canceled = client.cancel_all_orders("BTCUSDT")

        assert {str(o.client_order_id) for o in canceled} == {
            "SEW-lifecycle0002",
            "SEW-lifecycle0003",
        }
        assert client.get_open_orders("BTCUSDT") == []


def test_a_filled_market_order_becomes_a_position_and_never_rests() -> None:
    """`EPIC-028O` — the fake now fills a market order at the book: a buy
    at the ask (64 000.1). The order never rests, and the position it opens
    is read back through `positionRisk` v3, whose notional is signed."""
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        session_factory = FuturesSessionFactory()
        metadata_provider = FuturesMetadataProvider(
            session_factory, InMemorySymbolOrderMetadataCache()
        )
        client = FuturesTradingClient(
            session_factory,
            _FakeCredentialsProvider(),
            metadata_provider,
            OrderSubmissionMode.LIVE,
        )
        client.place_order(_market_order("SEW-fill00000001", OrderSide.BUY, "0.002"))
        long_positions = client.get_positions("BTCUSDT")
        open_orders = client.get_open_orders("BTCUSDT")
        client.place_order(_market_order("SEW-fill00000002", OrderSide.SELL, "0.005"))
        short_positions = client.get_positions("BTCUSDT")

    assert open_orders == []
    (long_position,) = long_positions
    assert long_position.position_amt == Decimal("0.002")
    assert long_position.entry_price == Decimal("64000.1")
    assert long_position.leverage == 20
    (short_position,) = short_positions
    assert short_position.position_amt == Decimal("-0.003")
    assert short_position.entry_price == Decimal("63999.9")
    assert short_position.leverage == 20
