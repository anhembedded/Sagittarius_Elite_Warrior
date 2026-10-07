"""`EPIC-028R` — a Futures stop-limit through Binance's Algo Order API, from
the order request to the wire and back, against the fake exchange.

@details Each order goes through the real `ExecuteOrderCommandHandler`,
`FuturesTradingClient` and `python-binance`, so the request path and the
`clientAlgoId` are the library's own. The fake triggers a conditional order
when a test moves the price (`OrderBookState.move_price`) and places its
regular order. Emergency Stop is the real handler: a conditional order placed
straight on the fake, as Binance's own UI would, is cancelled by it.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from binance.client import Client
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_reader import (
    FuturesAccountReader,
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
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client_factory import (
    FuturesTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.handler import (
    ExecuteOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.handler import (
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.query import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop.command import (
    EmergencyStopCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop.handler import (
    EmergencyStopCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.session_readiness import (
    SessionReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimits,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.recording_publisher import (
    RecordingPublisher,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    single_venue_scopes,
    venue_context,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests" / "sanity"))
from binance_fake_server import FakeServerUrls, run_binance_fake_server

_FUTURES = TradingVenue.FUTURES_TESTNET
#: The last price the app judges a stop by in these requests.
_LAST = Decimal(50000)
_LIMITS = TradingLimits(
    max_orders_per_session=20,
    max_notional_per_order=Decimal(100000),
    max_positions_per_symbol=5,
    min_order_interval=timedelta(0),
)


class _Credentials(IExchangeCredentialsProvider):
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="fake-key", api_secret="fake-secret"),
            CredentialsSource.FILE,
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise AssertionError("not used by this test")


def _context() -> VenueContext:
    sessions = FuturesSessionFactory()
    metadata = FuturesMetadataProvider(sessions, InMemorySymbolOrderMetadataCache())
    return venue_context(
        _FUTURES,
        account_reader=FuturesAccountReader(sessions, _Credentials()),
        client_factory=FuturesTradingClientFactory(sessions, _Credentials(), metadata),
        metadata_provider=metadata,
    )


def _place_sell_stop(context: VenueContext) -> Order:
    """A sell stop at 49 000 (limit 48 900) below the 50 000 last price."""
    state = TradingSessionState()
    state.enable(set())
    handler = ExecuteOrderCommandHandler(
        single_venue_scopes(context, state),
        PreviewOrderQueryHandler(FakeVenueContexts(context)),
        TradingLimitPolicy(_LIMITS),
        SessionReadiness(single_venue_scopes(context, state), RecordingPublisher()),
    )
    result = handler.execute(
        ExecuteOrderCommand(
            order_request=PreviewOrderQuery(
                venue=_FUTURES,
                symbol="BTCUSDT",
                side=OrderSide.SELL,
                order_type=OrderType.STOP_LIMIT,
                quantity=Decimal("0.01"),
                reference_price=Decimal(48900),
                stop_price=Decimal(49000),
                last_price=_LAST,
            ),
            live=True,
        )
    )
    assert result.blocked_by is None, result.blocked_by
    assert result.submitted_order is not None
    return result.submitted_order


def _client(context: VenueContext) -> ITradingClient:
    return context.client_factory.create(OrderSubmissionMode.LIVE)


def _with_fake_exchange(body: Callable[[FakeServerUrls], None]) -> None:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        body(urls)


def test_a_futures_stop_limit_is_placed_and_read_back_by_the_apps_id() -> None:
    def body(urls: FakeServerUrls) -> None:
        context = _context()
        sent = _place_sell_stop(context)

        posted = [path for method, path in urls.requests if method == "POST"]
        assert "/fapi/v1/algoOrder" in posted
        assert "/fapi/v1/order" not in posted
        (resting,) = _client(context).get_open_orders("BTCUSDT")
        assert resting.client_order_id == sent.client_order_id
        assert resting.order_type is OrderType.STOP_LIMIT
        assert (resting.stop_price, resting.price) == (Decimal(49000), Decimal(48900))
        assert resting.status is OrderStatus.NEW

    _with_fake_exchange(body)


def test_a_futures_stop_limit_is_cancelled_by_the_apps_id() -> None:
    def body(urls: FakeServerUrls) -> None:
        context = _context()
        sent = _place_sell_stop(context)
        client = _client(context)

        cancelled = client.cancel_order("BTCUSDT", str(sent.client_order_id))

        assert cancelled.status is OrderStatus.CANCELED
        assert client.get_open_orders("BTCUSDT") == []

    _with_fake_exchange(body)


def test_a_triggered_stop_places_its_limit_order_and_leaves_history() -> None:
    def body(urls: FakeServerUrls) -> None:
        context = _context()
        sent = _place_sell_stop(context)
        client = _client(context)

        urls.futures_book.move_price("BTCUSDT", Decimal("49000.1"))
        assert [o.client_order_id for o in client.get_open_orders("BTCUSDT")] == [
            sent.client_order_id
        ]
        urls.futures_book.move_price("BTCUSDT", Decimal(49000))

        (placed,) = client.get_open_orders("BTCUSDT")
        assert placed.order_type is OrderType.LIMIT
        assert (placed.side, placed.price) == (OrderSide.SELL, Decimal(48900))
        reader = FuturesHistoryReader(
            FuturesSessionFactory(), _Credentials(), lambda: datetime.now(UTC)
        )
        history = reader.order_history(
            "BTCUSDT", datetime.now(UTC) - timedelta(hours=1)
        )
        algo = [r for r in history if r.order.client_order_id == sent.client_order_id]
        assert [r.order.status for r in algo] == [OrderStatus.TRIGGERED]

    _with_fake_exchange(body)


def test_emergency_stop_cancels_a_conditional_order_placed_anywhere() -> None:
    """Placed straight on the fake, as Binance's own UI would: the app never
    sent it, and Emergency Stop still cancels it."""

    def body(urls: FakeServerUrls) -> None:
        status, _ = urls.futures_book.algo.place(
            {
                "algoType": "CONDITIONAL",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "type": "STOP_MARKET",
                "quantity": "0.01",
                "triggerPrice": "70000",
                "clientAlgoId": "web_placed_in_binance_ui",
            }
        )
        assert status == 200
        context = _context()
        assert len(_client(context).get_open_orders()) == 1
        state = TradingSessionState()
        state.enable(set())

        result = EmergencyStopCommandHandler(
            single_venue_scopes(context, state), RecordingPublisher()
        ).execute(EmergencyStopCommand(venue=_FUTURES))

        assert result.orders_cancelled.succeeded, result.orders_cancelled.detail
        assert _client(context).get_open_orders() == []
        assert ("DELETE", "/fapi/v1/algoOpenOrders") in urls.requests

    _with_fake_exchange(body)
