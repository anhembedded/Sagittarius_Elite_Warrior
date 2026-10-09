"""`EPIC-028P` — Phase 1's exit evidence: Futures and Spot run in one process,
against one fake exchange, and a command addressed to one venue never
reaches the other.

@details Both venues' real adapters (session factories, metadata providers,
account readers, trading clients, `python-binance` itself) point at one
`run_binance_fake_server()`, which serves `/fapi` and `/api` side by side
and logs every request it answers. The handlers are the real ones, over one
`VenueTradingScopes` that serves both venues, exactly as the running app
builds them. Each test acts on one venue and then checks the other three
ways:
- the server log holds no request to the other venue's API family;
- the other venue's open order on the exchange is still there;
- the other venue's session is still enabled.

Each runs in both directions. `test_venue_isolation.py` proves the same
rules with mocks; this file proves them across the wire, which is what the
README's Phase 1 exit row asks for (the PR #300 epic review found it
missing).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from binance.client import Client
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_reader import (
    FuturesAccountReader,
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
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.cancel_order import (
    CancelOrderCommand,
    CancelOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order import (
    ExecuteOrderCommand,
    ExecuteOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order import (
    PreviewOrderQuery,
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop import (
    EmergencyStopCommand,
    EmergencyStopCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.session_readiness import (
    SessionReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
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
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.recording_publisher import (
    RecordingPublisher,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    venue_context,
    venue_scopes,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests" / "sanity"))
from binance_fake_server import FakeServerUrls, run_binance_fake_server

_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT = TradingVenue.SPOT_TESTNET
_BOTH = [(_FUTURES, _SPOT), (_SPOT, _FUTURES)]
_SYMBOL = "BTCUSDT"
_QTY = Decimal("0.01")
#: Far below either fake's last price, so a limit buy rests open.
_RESTING_PRICE = Decimal(30000)
_MARKET_PRICE = Decimal(50000)
#: Each venue's API family on the shared fake server.
_PREFIX = {_FUTURES: "/fapi/", _SPOT: "/api/"}
_LIMITS = TradingLimits(
    max_orders_per_session=20,
    max_notional_per_order=Decimal(5000),
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


@dataclass
class _Process:
    """Both venues, wired as the running app wires them."""

    urls: FakeServerUrls
    contexts: dict[TradingVenue, VenueContext]
    states: dict[TradingVenue, TradingSessionState]
    execute: ExecuteOrderCommandHandler
    cancel: CancelOrderCommandHandler
    emergency_stop: EmergencyStopCommandHandler

    def place(
        self, venue: TradingVenue, order_type: OrderType, price: Decimal
    ) -> ClientOrderId:
        result = self.execute.execute(
            ExecuteOrderCommand(
                order_request=PreviewOrderQuery(
                    venue=venue,
                    symbol=_SYMBOL,
                    side=OrderSide.BUY,
                    order_type=order_type,
                    quantity=_QTY,
                    reference_price=price,
                ),
                live=True,
            )
        )
        assert result.blocked_by is None, (venue, result.blocked_by)
        assert result.submitted_order is not None
        return result.submitted_order.client_order_id

    def open_order_ids(self, venue: TradingVenue) -> set[str]:
        client = self.contexts[venue].client_factory.create(OrderSubmissionMode.LIVE)
        return {str(order.client_order_id) for order in client.get_open_orders()}

    def requests_after(self, mark: int) -> list[tuple[str, str]]:
        return self.urls.requests[mark:]


def _futures_context(credentials: _FakeCredentialsProvider) -> VenueContext:
    sessions = FuturesSessionFactory()
    metadata = FuturesMetadataProvider(sessions, InMemorySymbolOrderMetadataCache())
    return venue_context(
        _FUTURES,
        account_reader=FuturesAccountReader(sessions, credentials),
        client_factory=FuturesTradingClientFactory(sessions, credentials, metadata),
        metadata_provider=metadata,
    )


def _spot_context(credentials: _FakeCredentialsProvider) -> VenueContext:
    sessions = SpotSessionFactory()
    metadata = SpotMetadataProvider(sessions, InMemorySymbolOrderMetadataCache())
    return venue_context(
        _SPOT,
        account_reader=SpotAccountReader(sessions, credentials),
        client_factory=SpotTradingClientFactory(
            sessions, credentials, metadata, FakeOrderFillReporter()
        ),
        metadata_provider=metadata,
    )


@pytest.fixture
def process():
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        credentials = _FakeCredentialsProvider()
        contexts = {
            _FUTURES: _futures_context(credentials),
            _SPOT: _spot_context(credentials),
        }
        states = {venue: TradingSessionState() for venue in contexts}
        for state in states.values():
            # Spot's baseline is the whole account, so an Emergency Stop
            # sells nothing it did not buy (`EPIC-027M`).
            state.enable(set(), spot_baseline_holdings={"BTC": Decimal(1000)})
        scopes = venue_scopes(*contexts.values(), session_states=states)
        preview = PreviewOrderQueryHandler(FakeVenueContexts(*contexts.values()))
        yield _Process(
            urls=urls,
            contexts=contexts,
            states=states,
            execute=ExecuteOrderCommandHandler(
                scopes,
                preview,
                TradingLimitPolicy(_LIMITS),
                SessionReadiness(scopes, RecordingPublisher()),
            ),
            cancel=CancelOrderCommandHandler(scopes),
            emergency_stop=EmergencyStopCommandHandler(scopes, RecordingPublisher()),
        )


def _assert_only(requests: list[tuple[str, str]], venue: TradingVenue) -> None:
    assert requests, f"{venue.value} sent nothing at all"
    strays = [r for r in requests if not r[1].startswith(_PREFIX[venue])]
    assert strays == [], f"{venue.value}'s command reached the other venue: {strays}"


@pytest.mark.parametrize(("acting", "other"), _BOTH)
def test_a_market_order_reaches_only_its_venue(
    process: _Process, acting: TradingVenue, other: TradingVenue
) -> None:
    resting = process.place(other, OrderType.LIMIT, _RESTING_PRICE)
    mark = len(process.urls.requests)

    process.place(acting, OrderType.MARKET, _MARKET_PRICE)

    _assert_only(process.requests_after(mark), acting)
    assert str(resting) in process.open_order_ids(other)
    assert process.states[other].enabled is True


@pytest.mark.parametrize(("acting", "other"), _BOTH)
def test_a_cancel_reaches_only_its_venue(
    process: _Process, acting: TradingVenue, other: TradingVenue
) -> None:
    resting = process.place(other, OrderType.LIMIT, _RESTING_PRICE)
    to_cancel = process.place(acting, OrderType.LIMIT, _RESTING_PRICE)
    mark = len(process.urls.requests)

    result = process.cancel.execute(
        CancelOrderCommand(_SYMBOL, str(to_cancel), venue=acting)
    )

    assert result.blocked_by is None
    _assert_only(process.requests_after(mark), acting)
    assert str(to_cancel) not in process.open_order_ids(acting)
    assert str(resting) in process.open_order_ids(other)


@pytest.mark.parametrize(("acting", "other"), _BOTH)
def test_an_emergency_stop_reaches_only_its_venue(
    process: _Process, acting: TradingVenue, other: TradingVenue
) -> None:
    resting = process.place(other, OrderType.LIMIT, _RESTING_PRICE)
    process.place(acting, OrderType.LIMIT, _RESTING_PRICE)
    mark = len(process.urls.requests)

    result = process.emergency_stop.execute(EmergencyStopCommand(venue=acting))

    assert result.orders_cancelled.succeeded, result
    _assert_only(process.requests_after(mark), acting)
    assert process.open_order_ids(acting) == set()
    assert process.states[acting].enabled is False
    assert str(resting) in process.open_order_ids(other)
    assert process.states[other].enabled is True


def test_the_two_venues_keep_their_own_filters_for_the_same_symbol(
    process: _Process,
) -> None:
    """The same `BTCUSDT` is two instruments: each venue rounds with its own
    catalog, and neither catalog is fetched from the other's API family."""
    mark = len(process.urls.requests)

    futures = process.contexts[_FUTURES].metadata_provider.get_or_fetch(_SYMBOL)
    spot = process.contexts[_SPOT].metadata_provider.get_or_fetch(_SYMBOL)

    assert futures is not None and spot is not None
    paths = [path for _, path in process.requests_after(mark)]
    assert any(p.startswith("/fapi/") for p in paths)
    assert any(p.startswith("/api/") for p in paths)
    assert (futures.step_size, futures.tick_size) != (
        spot.step_size,
        spot.tick_size,
    ) or (futures.min_notional != spot.min_notional)
