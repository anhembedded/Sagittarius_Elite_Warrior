"""`EPIC-021J` — `FuturesTradingClient`'s full order lifecycle (place →
appears in `get_open_orders()` → cancel → gone) against a real HTTP round
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
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import ClientOrderId
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_metadata_provider import (
    FuturesMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.futures_symbol_metadata_cache import (
    InMemoryFuturesSymbolMetadataCache,
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


def _order(client_order_id: str = "SEW-lifecycle0001") -> Order:
    return Order(
        client_order_id=ClientOrderId(client_order_id),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.002"),
    )


def test_placed_order_appears_in_open_orders_then_cancel_removes_it() -> None:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        session_factory = ExchangeSessionFactory(MarketDataVenue.MAINNET_PUBLIC)
        metadata_provider = FuturesMetadataProvider(
            session_factory, InMemoryFuturesSymbolMetadataCache()
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
        session_factory = ExchangeSessionFactory(MarketDataVenue.MAINNET_PUBLIC)
        metadata_provider = FuturesMetadataProvider(
            session_factory, InMemoryFuturesSymbolMetadataCache()
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


def test_positions_are_always_flat_no_matching_engine() -> None:
    """`order_book_state.py`'s own docstring: no fills, no position
    tracking — placing an order never makes `get_positions()` non-empty."""
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        session_factory = ExchangeSessionFactory(MarketDataVenue.MAINNET_PUBLIC)
        metadata_provider = FuturesMetadataProvider(
            session_factory, InMemoryFuturesSymbolMetadataCache()
        )
        client = FuturesTradingClient(
            session_factory,
            _FakeCredentialsProvider(),
            metadata_provider,
            OrderSubmissionMode.LIVE,
        )
        client.place_order(_order())

        assert client.get_positions("BTCUSDT") == []
