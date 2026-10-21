"""`BUG-262` - the pause a banned connection check names reaches the refusal of the order session."""

from __future__ import annotations

from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.trading.application.session.ensure_session_ready import (
    EnsureSessionReadyCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.session.test_ensure_session_ready import (
    _handler,
)


def test_a_banned_connection_check_carries_the_pause_into_the_refusal() -> None:
    banned = ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=False,
        failure=ConnectionFailureKind.RATE_LIMITED,
        server_time_skew_ms=None,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
        retry_after=timedelta(minutes=2),
        banned=True,
    )
    handler, _state, _stream, _reader = _handler(status=banned)

    result = handler.execute(
        EnsureSessionReadyCommand(venue=TradingVenue.FUTURES_TESTNET)
    )

    assert result.connection_failure is ConnectionFailureKind.RATE_LIMITED
    assert result.connection_retry_after == timedelta(minutes=2)
    assert result.connection_banned is True
