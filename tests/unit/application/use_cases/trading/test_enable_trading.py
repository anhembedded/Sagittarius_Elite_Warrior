from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.enable_trading import (
    EnableTradingBlockReason,
    EnableTradingCommand,
    EnableTradingCommandHandler,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.trading_venue import (
    TradingVenue,
)

_CREDENTIALS = ExchangeCredentials(api_key="key", api_secret="secret")


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


def _position_payload(symbol: str = "BTCUSDT") -> dict:
    return {
        "symbol": symbol,
        "positionAmt": "0.5",
        "entryPrice": "60000",
        "markPrice": "60100",
        "unRealizedProfit": "50",
        "leverage": "10",
        "marginType": "cross",
        "liquidationPrice": "45000",
    }


def _handler(
    trading_venue: TradingVenue = TradingVenue.FUTURES_TESTNET,
    status: ExchangeConnectionStatus | None = None,
    position_payloads: list[dict] | None = None,
    open_order_payloads: list[dict] | None = None,
) -> tuple[EnableTradingCommandHandler, TradingSessionState, Mock]:
    account_reader = Mock()
    account_reader.check_connection.return_value = status or _ready_status()

    raw_client = Mock()
    raw_client.futures_position_information.return_value = position_payloads or []
    raw_client.futures_get_open_orders.return_value = open_order_payloads or []
    session_factory = Mock()
    session_factory.create_trading_client.return_value = raw_client
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        _CREDENTIALS, CredentialsSource.FILE
    )
    metadata_provider = Mock()
    session_state = TradingSessionState()
    user_data_stream = Mock()

    return (
        EnableTradingCommandHandler(
            trading_venue,
            account_reader,
            session_factory,
            credentials_provider,
            metadata_provider,
            session_state,
            user_data_stream,
        ),
        session_state,
        user_data_stream,
    )


def test_enables_when_account_is_flat() -> None:
    handler, session_state, user_data_stream = _handler()

    result = handler.execute(EnableTradingCommand())

    assert result.enabled is True
    assert result.block_reason is None
    assert session_state.enabled is True
    user_data_stream.start.assert_called_once()


def test_blocked_when_trading_venue_disabled() -> None:
    handler, session_state, user_data_stream = _handler(
        trading_venue=TradingVenue.DISABLED
    )

    result = handler.execute(EnableTradingCommand())

    assert result.enabled is False
    assert result.block_reason is EnableTradingBlockReason.TRADING_VENUE_DISABLED
    assert session_state.enabled is False
    user_data_stream.start.assert_not_called()


def test_blocked_when_connection_not_reachable() -> None:
    unreachable = ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=False,
        failure=ConnectionFailureKind.NETWORK,
        server_time_skew_ms=None,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
    )
    handler, session_state, user_data_stream = _handler(status=unreachable)

    result = handler.execute(EnableTradingCommand())

    assert result.block_reason is EnableTradingBlockReason.CONNECTION_NOT_READY
    assert session_state.enabled is False
    user_data_stream.start.assert_not_called()


def test_blocked_when_hedge_mode() -> None:
    hedge_mode = ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=True,
        failure=ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED,
        server_time_skew_ms=10,
        usdt_balance=Decimal(1000),
        position_mode=PositionMode.HEDGE,
        margin_type=None,
        open_position_count=0,
    )
    handler, session_state, user_data_stream = _handler(status=hedge_mode)

    result = handler.execute(EnableTradingCommand())

    assert result.block_reason is EnableTradingBlockReason.CONNECTION_NOT_READY
    assert session_state.enabled is False
    user_data_stream.start.assert_not_called()


def test_refuses_and_does_not_enable_when_unexpected_position_exists() -> None:
    """`EPIC-021G` §2.4: an existing position the app has no record of
    refuses the enable — it is never auto-adopted, never auto-closed."""
    handler, session_state, user_data_stream = _handler(
        position_payloads=[_position_payload()]
    )

    result = handler.execute(EnableTradingCommand())

    assert result.enabled is False
    assert result.block_reason is EnableTradingBlockReason.UNEXPECTED_POSITIONS
    assert len(result.reconciled_positions) == 1
    assert result.reconciled_positions[0].symbol == "BTCUSDT"
    assert session_state.enabled is False
    user_data_stream.start.assert_not_called()
