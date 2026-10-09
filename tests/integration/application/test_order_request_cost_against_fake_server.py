"""`EPIC-035D` (M3) — what one order costs the exchange, counted on the wire.

Audit M3: each order cost about three extra requests. Measured on `be67b47` with
this test's journey, a Spot LIMIT order after the first cost **10 requests**: the
session the account read opened (ping, clock), the account read's own connection
check (ping, clock, account, and one price per priced holding, here two), the
session the trading client opened (ping, clock), and the order. A session is now
opened once per venue and key and reused, so the steady-state order costs **6**:
the safety gate's connection check (ping, clock, account, two prices) and the order.

The remaining five are the gate's read of the account (`EXPECTED_STEADY_ORDER`), kept
on purpose: a bot's order is refused when the exchange cannot be reached, and the
connection check is what says so. A lighter readiness probe would cut them to one;
that changes `IVenueAccountReader` and is recorded as a follow-up, not built here.

The journey is `test_spot_manual_order_pipeline_against_fake_server.py`'s, through the
real `ExecuteOrderCommandHandler`, `SpotAccountReader`, `SpotTradingClient` and the
fake exchange's request log.
"""

from __future__ import annotations

import sys
from collections import Counter
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
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
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
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
from binance_fake_server import run_binance_fake_server

#: The steady-state order, by path, measured on the wire (see the module docstring).
EXPECTED_STEADY_ORDER = Counter(
    {
        "/api/v3/ping": 1,
        "/api/v3/time": 1,
        "/api/v3/account": 1,
        "/api/v3/ticker/price": 2,
        "/api/v3/order": 1,
    }
)
_LIMITS = TradingLimits(
    max_orders_per_session=20,
    max_notional_per_order=Decimal(50000),
    max_positions_per_symbol=1,
    min_order_interval=timedelta(0),
)


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


def test_a_steady_state_order_costs_the_documented_minimum_of_requests() -> None:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        session_factory = SpotSessionFactory()
        metadata = SpotMetadataProvider(
            session_factory, InMemorySymbolOrderMetadataCache()
        )
        credentials = _FakeCredentialsProvider()
        session_state = TradingSessionState()
        session_state.enable(set())
        context = venue_context(
            TradingVenue.SPOT_TESTNET,
            account_reader=SpotAccountReader(session_factory, credentials),
            client_factory=SpotTradingClientFactory(
                session_factory, credentials, metadata, FakeOrderFillReporter()
            ),
            metadata_provider=metadata,
        )
        handler = ExecuteOrderCommandHandler(
            single_venue_scopes(context, session_state),
            PreviewOrderQueryHandler(FakeVenueContexts(context)),
            TradingLimitPolicy(_LIMITS),
            SessionReadiness(
                single_venue_scopes(context, session_state), RecordingPublisher()
            ),
        )

        def order() -> Counter[str]:
            before = len(urls.requests)
            result = handler.execute(
                ExecuteOrderCommand(
                    order_request=PreviewOrderQuery(
                        venue=TradingVenue.SPOT_TESTNET,
                        symbol="BTCUSDT",
                        side=OrderSide.BUY,
                        order_type=OrderType.LIMIT,
                        quantity=Decimal("0.5"),
                        reference_price=Decimal(50000),
                        reduce_only=False,
                    ),
                    live=True,
                )
            )
            assert result.blocked is False, result.blocked_by
            return Counter(path for _method, path in urls.requests[before:])

        order()  # the first order opens the session and reads the symbol's filters
        steady = [order(), order()]

    assert steady == [EXPECTED_STEADY_ORDER, EXPECTED_STEADY_ORDER]
    assert sum(EXPECTED_STEADY_ORDER.values()) == 6
