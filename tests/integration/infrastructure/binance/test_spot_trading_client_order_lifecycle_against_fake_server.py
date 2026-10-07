"""`EPIC-027K` — `SpotTradingClient`'s full order lifecycle (place → appears
in `get_open_orders()` → cancel → gone) against a real HTTP round trip
through the fake server's Spot signed routes (`EPIC-027J`), mirroring
`test_futures_trading_client_order_lifecycle_against_fake_server.py`'s own
established pattern for the Futures side.

@details A `LIMIT` order, not `MARKET`: unlike Futures' fake exchange (no
matching engine at all — `order_book_state.py`'s own docstring), Spot's
fake exchange fills a `MARKET` order immediately
(`test_fake_exchange_spot_routes.py::test_a_filled_market_buy_...`), so a
`MARKET` order here would never stay open long enough to appear in
`get_open_orders()`. A `LIMIT` order stays `NEW` until canceled — the same
choice `test_fake_exchange_spot_routes.py::
test_a_limit_order_stays_open_until_canceled` already made for the raw SDK
client this test exercises through the real `SpotTradingClient` adapter
instead.

Constructs `SpotTradingClient` with `OrderSubmissionMode.LIVE` directly —
same `OrderSubmissionMode.LIVE` usage-guard exemption
(`test_order_submission_mode_live_is_restricted.py` scans only `src/` and
`scripts/`) the Futures lifecycle test already relies on.
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
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_metadata_provider import (
    SpotMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client import (
    SpotTradingClient,
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


def _limit_order(client_order_id: str = "SEW-lifecycle0001") -> Order:
    return Order(
        client_order_id=ClientOrderId(client_order_id),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal(1),
        price=Decimal(40000),
        time_in_force=TimeInForce.GTC,
    )


def _client_and_provider() -> tuple[SpotTradingClient, SpotMetadataProvider]:
    session_factory = SpotSessionFactory()
    metadata_provider = SpotMetadataProvider(
        session_factory, InMemorySymbolOrderMetadataCache()
    )
    client = SpotTradingClient(
        session_factory,
        _FakeCredentialsProvider(),
        metadata_provider,
        OrderSubmissionMode.LIVE,
    )
    return client, metadata_provider


def test_placed_order_appears_in_open_orders_then_cancel_removes_it() -> None:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        client, _metadata_provider = _client_and_provider()
        order = _limit_order()

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
        client, _metadata_provider = _client_and_provider()
        client.place_order(_limit_order("SEW-lifecycle0002"))
        client.place_order(_limit_order("SEW-lifecycle0003"))

        canceled = client.cancel_all_orders("BTCUSDT")

        assert {str(o.client_order_id) for o in canceled} == {
            "SEW-lifecycle0002",
            "SEW-lifecycle0003",
        }
        assert client.get_open_orders("BTCUSDT") == []


def test_a_market_order_fills_immediately_and_never_appears_in_open_orders() -> None:
    """The Spot-specific difference the module docstring names: unlike
    Futures' fake exchange, Spot's does simulate a fill — this is not a
    defect in the lifecycle test above, but the reason it uses `LIMIT`."""
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        client, _metadata_provider = _client_and_provider()
        market_order = Order(
            client_order_id=ClientOrderId("SEW-lifecycle0004"),
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal(1),
        )

        client.place_order(market_order)

        assert client.get_open_orders("BTCUSDT") == []


def test_positions_are_always_flat_a_spot_account_has_no_leveraged_positions() -> None:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        client, _metadata_provider = _client_and_provider()
        client.place_order(_limit_order())

        assert client.get_positions("BTCUSDT") == []
