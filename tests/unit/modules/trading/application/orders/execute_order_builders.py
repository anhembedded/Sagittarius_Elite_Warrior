"""The builders the `ExecuteOrderCommandHandler` tests share (`BOT-146`).

The test file outgrew the 400-line ceiling, and its three parts moved to
`test_execute_order_safety_gates.py`, `test_execute_order_rejections.py` and
`test_execute_order_submission.py`. Each imports its handler and fixtures from
here rather than keeping a copy.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client_factory import (
    FuturesTradingClientFactory,
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
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    PercentPriceBand,
    SymbolOrderMetadata,
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
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    single_venue_scopes,
    venue_context,
)

CREDENTIALS = ExchangeCredentials(api_key="key", api_secret="secret")

LIMITS = TradingLimits(
    max_orders_per_session=20,
    max_notional_per_order=Decimal(500),
    max_positions_per_symbol=1,
    min_order_interval=timedelta(seconds=60),
)


class StaticMetadataProvider(IMarketMetadataProvider):
    def __init__(self, catalog: dict[str, SymbolOrderMetadata]) -> None:
        self._catalog = catalog

    def get_or_fetch(self, symbol: str) -> SymbolOrderMetadata | None:
        return self._catalog.get(symbol)

    def refresh(self) -> None:
        raise NotImplementedError


def static_metadata_provider(
    price_band: PercentPriceBand | None = None,
) -> IMarketMetadataProvider:
    """@param price_band `BUG-147` — BTCUSDT's `PERCENT_PRICE_BY_SIDE`;
    none by default, so every other test is unchanged."""
    return StaticMetadataProvider(
        {
            "BTCUSDT": SymbolOrderMetadata(
                symbol="BTCUSDT",
                status="TRADING",
                step_size=Decimal("0.001"),
                tick_size=Decimal("0.01"),
                min_notional=Decimal(100),
                quantity_precision=3,
                price_precision=2,
                fetched_at=datetime(2026, 8, 27, tzinfo=UTC),
                price_band=price_band,
            ),
            # `EPIC-029A` review — a second symbol, so a test can send a bot's
            # tagged order where its budget does not apply.
            "ETHUSDT": SymbolOrderMetadata(
                symbol="ETHUSDT",
                status="TRADING",
                step_size=Decimal("0.001"),
                tick_size=Decimal("0.01"),
                min_notional=Decimal(5),
                quantity_precision=3,
                price_precision=2,
                fetched_at=datetime(2026, 8, 27, tzinfo=UTC),
            ),
        }
    )


def ready_status() -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=10,
        usdt_balance=Decimal(1000),
        position_mode=PositionMode.ONE_WAY,
        margin_type=None,
        open_position_count=0,
    )


def order_request(**overrides: object) -> PreviewOrderQuery:
    defaults: dict[str, object] = {
        "symbol": "BTCUSDT",
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "quantity": Decimal("0.002"),
        "reference_price": Decimal(64000),
        "venue": TradingVenue.FUTURES_TESTNET,
    }
    defaults.update(overrides)
    return PreviewOrderQuery(**defaults)  # type: ignore[arg-type]


def build_handler(
    *,
    venue: TradingVenue,
    state: TradingSessionState,
    account_reader: Mock,
    metadata_provider: IMarketMetadataProvider,
    trading_client_factory: FuturesTradingClientFactory,
    limits: TradingLimits | None = None,
) -> ExecuteOrderCommandHandler:
    """`EPIC-028B` — the handler over one venue's scope: its account reader,
    client factory and metadata, and the session state the test arranges."""
    context = venue_context(
        venue,
        account_reader=account_reader,
        client_factory=trading_client_factory,
        metadata_provider=metadata_provider,
    )
    return ExecuteOrderCommandHandler(
        single_venue_scopes(context, state),
        PreviewOrderQueryHandler(FakeVenueContexts(context)),
        TradingLimitPolicy(limits or LIMITS),
    )


def make_handler(
    *,
    trading_venue: TradingVenue = TradingVenue.FUTURES_TESTNET,
    enabled: bool = True,
    status: ExchangeConnectionStatus | None = None,
    session_state: TradingSessionState | None = None,
    raw_client: Mock | None = None,
    limits: TradingLimits | None = None,
    price_band: PercentPriceBand | None = None,
) -> tuple[ExecuteOrderCommandHandler, TradingSessionState]:
    state = session_state or TradingSessionState()
    if enabled and not state.enabled:
        state.enable(state.known_open_symbols)

    account_reader = Mock()
    account_reader.check_connection.return_value = status or ready_status()

    session_factory = Mock()
    session_factory.create_trading_client.return_value = raw_client or Mock()
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        CREDENTIALS, CredentialsSource.FILE
    )
    metadata_provider = static_metadata_provider(price_band)
    trading_client_factory = FuturesTradingClientFactory(
        session_factory, credentials_provider, metadata_provider
    )

    handler = build_handler(
        venue=trading_venue,
        state=state,
        account_reader=account_reader,
        metadata_provider=metadata_provider,
        trading_client_factory=trading_client_factory,
        limits=limits,
    )
    return handler, state
