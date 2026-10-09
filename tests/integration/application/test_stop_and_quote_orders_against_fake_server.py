"""`EPIC-028O` — a stop-limit and a quote-sized market buy, from the order
request to the wire and back, against the fake exchange.

@details Each order goes through the real `ExecuteOrderCommandHandler`:
the preview rounds it, the venue's real trading client maps it, and
`python-binance` form-encodes it to the fake server. What comes back is read
through the real payload mappers, so a Spot `STOP_LOSS_LIMIT` is proven to
round-trip as `OrderType.STOP_LIMIT`.

The Spot fake triggers a stop-limit when a test moves the last price
(`SpotAccountState.set_last_price`) and fills it at its limit.
A stop already crossed is refused before any request, which the server's
request log proves. The Futures stop-limit, sent through Binance's Algo Order
API since `EPIC-028R`, is `test_futures_algo_orders_against_fake_server.py`'s.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from binance.client import Client
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_account_reader import (
    SpotAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_metadata_provider import (
    SpotMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client_factory import (
    SpotTradingClientFactory,
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
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.session_readiness import (
    SessionReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
    ExecuteOrderStopRejection,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_fill_reporter import (
    FakeOrderFillReporter,
)
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

_SPOT = TradingVenue.SPOT_TESTNET
#: The Spot fake's starting last price for BTCUSDT (`spot_account_state.py`).
_LAST = Decimal(50000)
#: Generous limits: what this file checks is the order shape, not the
#: session limits (`TradingLimitPolicy` has its own coverage).
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

    def remove_stored(self) -> None:
        raise AssertionError("not used by this test")


def _spot_context() -> VenueContext:
    sessions = SpotSessionFactory()
    metadata = SpotMetadataProvider(sessions, InMemorySymbolOrderMetadataCache())
    return venue_context(
        _SPOT,
        account_reader=SpotAccountReader(sessions, _Credentials()),
        client_factory=SpotTradingClientFactory(
            sessions, _Credentials(), metadata, FakeOrderFillReporter()
        ),
        metadata_provider=metadata,
    )


def _execute(context: VenueContext, query: PreviewOrderQuery) -> ExecuteOrderResult:
    state = TradingSessionState()
    state.enable(set())
    handler = ExecuteOrderCommandHandler(
        single_venue_scopes(context, state),
        PreviewOrderQueryHandler(FakeVenueContexts(context)),
        TradingLimitPolicy(_LIMITS),
        SessionReadiness(single_venue_scopes(context, state), RecordingPublisher()),
    )
    return handler.execute(ExecuteOrderCommand(order_request=query, live=True))


def _stop_limit(
    venue: TradingVenue, side: OrderSide, stop: str, limit: str
) -> PreviewOrderQuery:
    return PreviewOrderQuery(
        venue=venue,
        symbol="BTCUSDT",
        side=side,
        order_type=OrderType.STOP_LIMIT,
        quantity=Decimal("0.01"),
        reference_price=Decimal(limit),
        stop_price=Decimal(stop),
        last_price=_LAST,
    )


def _with_fake_exchange(body: Callable[[FakeServerUrls], None]) -> None:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        body(urls)


def test_a_spot_buy_stop_rests_until_the_price_crosses_it_then_fills_at_its_limit() -> (
    None
):
    def body(urls: FakeServerUrls) -> None:
        context = _spot_context()
        result = _execute(context, _stop_limit(_SPOT, OrderSide.BUY, "51000", "51100"))
        assert result.blocked_by is None
        client = context.client_factory.create(OrderSubmissionMode.LIVE)

        (resting,) = client.get_open_orders("BTCUSDT")
        assert resting.order_type is OrderType.STOP_LIMIT
        assert resting.stop_price == Decimal(51000)
        assert resting.price == Decimal(51100)

        urls.spot_account.set_last_price("BTCUSDT", Decimal("50999.99"))
        assert len(client.get_open_orders("BTCUSDT")) == 1
        urls.spot_account.set_last_price("BTCUSDT", Decimal(51000))

        assert client.get_open_orders("BTCUSDT") == []
        (event, _) = urls.spot_account.drain_user_data_events()
        assert (event["o"], event["X"], event["L"]) == (
            "STOP_LOSS_LIMIT",
            "FILLED",
            "51100.00000000",
        )

    _with_fake_exchange(body)


def test_a_crossed_spot_stop_is_refused_and_never_sent() -> None:
    def body(urls: FakeServerUrls) -> None:
        result = _execute(
            _spot_context(), _stop_limit(_SPOT, OrderSide.SELL, "50000", "49900")
        )

        assert result.blocked_by is ExecuteOrderStopRejection.STOP_ON_WRONG_SIDE
        assert ("POST", "/api/v3/order") not in urls.requests

    _with_fake_exchange(body)


def test_a_quote_sized_spot_market_buy_spends_the_quote_amount() -> None:
    def body(urls: FakeServerUrls) -> None:
        result = _execute(
            _spot_context(),
            PreviewOrderQuery(
                venue=_SPOT,
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal(0),
                reference_price=_LAST,
                quote_quantity=Decimal(1000),
            ),
        )

        assert result.blocked_by is None
        (event, _) = urls.spot_account.drain_user_data_events()
        # 1000 USDT at 50 000 buys 0.02 BTC.
        assert (event["o"], event["z"]) == ("MARKET", "0.02000000")

    _with_fake_exchange(body)
