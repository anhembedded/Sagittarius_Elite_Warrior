from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.preview_order.handler import (
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.preview_order.query import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.execute_order.handler import (
    ExecuteOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.execute_order.result import (
    ExecuteOrderNotionalRejection,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.domain.entities.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.trading.policies.trading_limit_policy import (
    TradingLimitPolicy,
    TradingLimits,
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.domain.value_objects.trading_venue import (
    TradingVenue,
)

_CREDENTIALS = ExchangeCredentials(api_key="key", api_secret="secret")

_LIMITS = TradingLimits(
    max_orders_per_session=20,
    max_notional_per_order=Decimal(500),
    max_positions_per_symbol=1,
    min_order_interval=timedelta(seconds=60),
)


class _StaticMetadataProvider(IMarketMetadataProvider):
    def __init__(self, catalog: dict[str, FuturesSymbolMetadata]) -> None:
        self._catalog = catalog

    def get_or_fetch(self, symbol: str) -> FuturesSymbolMetadata | None:
        return self._catalog.get(symbol)

    def refresh(self) -> None:
        raise NotImplementedError


def _metadata_provider() -> IMarketMetadataProvider:
    return _StaticMetadataProvider(
        {
            "BTCUSDT": FuturesSymbolMetadata(
                symbol="BTCUSDT",
                status="TRADING",
                step_size=Decimal("0.001"),
                tick_size=Decimal("0.01"),
                min_notional=Decimal(100),
                quantity_precision=3,
                price_precision=2,
                fetched_at=datetime(2026, 8, 27, tzinfo=UTC),
            )
        }
    )


def _ready_status() -> ExchangeConnectionStatus:
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


def _order_request(**overrides: object) -> PreviewOrderQuery:
    defaults: dict[str, object] = {
        "symbol": "BTCUSDT",
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "quantity": Decimal("0.002"),
        "reference_price": Decimal(64000),
    }
    defaults.update(overrides)
    return PreviewOrderQuery(**defaults)  # type: ignore[arg-type]


def _handler(
    *,
    trading_venue: TradingVenue = TradingVenue.FUTURES_TESTNET,
    enabled: bool = True,
    status: ExchangeConnectionStatus | None = None,
    session_state: TradingSessionState | None = None,
    raw_client: Mock | None = None,
) -> tuple[ExecuteOrderCommandHandler, TradingSessionState]:
    state = session_state or TradingSessionState()
    if enabled and not state.enabled:
        state.enable(state.known_open_symbols)

    account_reader = Mock()
    account_reader.check_connection.return_value = status or _ready_status()

    session_factory = Mock()
    session_factory.create_trading_client.return_value = raw_client or Mock()
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        _CREDENTIALS, CredentialsSource.FILE
    )
    metadata_provider = _metadata_provider()
    preview_handler = PreviewOrderQueryHandler(metadata_provider)

    handler = ExecuteOrderCommandHandler(
        trading_venue,
        state,
        account_reader,
        preview_handler,
        TradingLimitPolicy(_LIMITS),
        session_factory,
        credentials_provider,
        metadata_provider,
    )
    return handler, state


class TestSafetyGates:
    def test_blocked_when_trading_venue_disabled(self) -> None:
        handler, _ = _handler(trading_venue=TradingVenue.DISABLED)
        result = handler.execute(ExecuteOrderCommand(order_request=_order_request()))
        assert result.blocked_by is ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED
        assert result.preview is None

    def test_blocked_when_switch_is_off(self) -> None:
        handler, _ = _handler(enabled=False)
        result = handler.execute(ExecuteOrderCommand(order_request=_order_request()))
        assert result.blocked_by is ExecuteOrderSafetyGate.TRADING_SWITCH_OFF

    def test_blocked_when_connection_not_ready(self) -> None:
        bad_status = ExchangeConnectionStatus(
            venue=TradingVenue.FUTURES_TESTNET,
            reachable=False,
            failure=ConnectionFailureKind.NETWORK,
            server_time_skew_ms=None,
            usdt_balance=None,
            position_mode=None,
            margin_type=None,
            open_position_count=None,
        )
        handler, _ = _handler(status=bad_status)
        result = handler.execute(ExecuteOrderCommand(order_request=_order_request()))
        assert result.blocked_by is ExecuteOrderSafetyGate.CONNECTION_NOT_READY

    def test_each_gate_blocks_independently_of_the_other_two(self) -> None:
        """`EPIC-021G` §4: each of the three safety gates must block on its
        own — turning off exactly one at a time, the other two passing."""
        # Venue off, switch on, connection ready.
        handler, _ = _handler(trading_venue=TradingVenue.DISABLED, enabled=True)
        assert (
            handler.execute(
                ExecuteOrderCommand(order_request=_order_request())
            ).blocked_by
            is ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED
        )

        # Venue ready, switch off, connection ready.
        handler, _ = _handler(trading_venue=TradingVenue.FUTURES_TESTNET, enabled=False)
        assert (
            handler.execute(
                ExecuteOrderCommand(order_request=_order_request())
            ).blocked_by
            is ExecuteOrderSafetyGate.TRADING_SWITCH_OFF
        )

        # Venue ready, switch on, connection not ready.
        bad_status = ExchangeConnectionStatus(
            venue=TradingVenue.FUTURES_TESTNET,
            reachable=False,
            failure=ConnectionFailureKind.NETWORK,
            server_time_skew_ms=None,
            usdt_balance=None,
            position_mode=None,
            margin_type=None,
            open_position_count=None,
        )
        handler, _ = _handler(enabled=True, status=bad_status)
        assert (
            handler.execute(
                ExecuteOrderCommand(order_request=_order_request())
            ).blocked_by
            is ExecuteOrderSafetyGate.CONNECTION_NOT_READY
        )


class TestTradingLimits:
    def test_blocked_by_max_positions_per_symbol(self) -> None:
        """`EPIC-021G`'s own worked rejected example: an existing open
        position on the symbol blocks a second order."""
        state = TradingSessionState()
        state.enable({"BTCUSDT"})
        handler, _ = _handler(session_state=state, enabled=True)

        result = handler.execute(ExecuteOrderCommand(order_request=_order_request()))

        assert result.blocked_by is TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL
        assert result.preview is not None
        assert len(result.limit_checks) == 4

    def test_dry_run_does_not_submit_even_when_everything_passes(self) -> None:
        handler, state = _handler()

        result = handler.execute(
            ExecuteOrderCommand(order_request=_order_request(), live=False)
        )

        assert result.blocked_by is None
        assert result.submitted_order is None
        assert state.orders_sent_this_session == 0


class TestNotionalRejection:
    def test_blocked_by_min_notional_before_any_network_order_call(self) -> None:
        """`BUG-090` — `EPIC-021`'s own §1 finding 6: the rounding/notional
        policy existed since `BOT-095E1` and was never wired into the live
        order path, so an order sized under `minNotional` used to sail
        through every check here and get rejected by the exchange itself.
        BTCUSDT's `min_notional` is 100 (`_metadata_provider()`); this
        order's notional is 0.001 * 50 = 0.05."""
        raw_client = Mock()
        handler, state = _handler(raw_client=raw_client)

        result = handler.execute(
            ExecuteOrderCommand(
                order_request=_order_request(
                    quantity=Decimal("0.001"), reference_price=Decimal(50)
                ),
                live=True,
            )
        )

        assert result.blocked_by is ExecuteOrderNotionalRejection.MIN_NOTIONAL
        assert result.preview is not None
        assert result.limit_checks == ()
        assert result.submitted_order is None
        raw_client.futures_create_order.assert_not_called()
        assert state.orders_sent_this_session == 0


class TestLiveSubmission:
    def test_live_submits_and_records_the_order(self) -> None:
        raw_client = Mock()
        raw_client.futures_create_order.return_value = {}
        handler, state = _handler(raw_client=raw_client)

        result = handler.execute(
            ExecuteOrderCommand(order_request=_order_request(), live=True)
        )

        assert result.blocked_by is None
        assert result.submitted_order is not None
        raw_client.futures_create_order.assert_called_once()
        raw_client.futures_create_test_order.assert_not_called()
        assert state.orders_sent_this_session == 1
        assert state.open_position_count("BTCUSDT") == 1

    def test_unknown_symbol_raises_value_error_before_any_network_order_call(
        self,
    ) -> None:
        raw_client = Mock()
        handler, _ = _handler(raw_client=raw_client)

        with pytest.raises(ValueError, match="Unknown futures symbol"):
            handler.execute(
                ExecuteOrderCommand(
                    order_request=_order_request(symbol="UNKNOWNUSDT"), live=True
                )
            )
        raw_client.futures_create_order.assert_not_called()
