"""`BUG-231` — the line that opens an order session says the account's position mode and margin type.

A refused reduce-only order is read against what the account was when the session opened, so the
opening line, greppable as `[order-session-open]`, carries both.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client_factory import (
    FuturesTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.session_readiness import (
    SessionReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
    MarginType,
    PositionMode,
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

_VENUE = TradingVenue.FUTURES_TESTNET


def _status(margin_type: MarginType | None) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=_VENUE,
        reachable=True,
        failure=None,
        server_time_skew_ms=10,
        usdt_balance=Decimal(1000),
        position_mode=PositionMode.ONE_WAY,
        margin_type=margin_type,
        open_position_count=0,
    )


def _readiness(status: ExchangeConnectionStatus) -> SessionReadiness:
    account_reader = Mock()
    account_reader.check_connection.return_value = status
    raw_client = Mock()
    raw_client.futures_position_information.return_value = []
    raw_client.futures_get_open_orders.return_value = []
    raw_client.futures_get_open_algo_orders.return_value = []
    session_factory = Mock()
    session_factory.create_trading_client.return_value = raw_client
    credentials = Mock()
    credentials.resolve.return_value = ResolvedCredentials(
        ExchangeCredentials(api_key="key", api_secret="secret"), CredentialsSource.FILE
    )
    factory = FuturesTradingClientFactory(session_factory, credentials, Mock())
    context = venue_context(
        _VENUE,
        account_reader=account_reader,
        client_factory=factory,
        user_data_stream=Mock(),
    )
    return SessionReadiness(
        single_venue_scopes(context, TradingSessionState()), RecordingPublisher()
    )


def _opening_line(readiness: SessionReadiness, caplog: pytest.LogCaptureFixture) -> str:
    with caplog.at_level(logging.INFO, logger="App.TradingSession"):
        assert readiness.ensure_ready(_VENUE).ready
    (record,) = [r for r in caplog.records if "[order-session-open]" in r.getMessage()]
    return record.getMessage()


def test_the_opening_line_says_the_position_mode_and_margin_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    line = _opening_line(_readiness(_status(MarginType.ISOLATED)), caplog)

    assert "position mode=one_way margin type=isolated" in line


def test_a_margin_type_the_account_did_not_report_is_said_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    line = _opening_line(_readiness(_status(None)), caplog)

    assert "position mode=one_way margin type=n/a" in line
