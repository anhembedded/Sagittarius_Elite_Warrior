from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_exchange_connection_status import (
    GetExchangeConnectionStatusQuery,
    GetExchangeConnectionStatusQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    venue_context,
)


def test_execute_delegates_straight_to_the_reader():
    """Thin CQRS wrapper by design (see the handler's own docstring) — the
    reader already returns the fully-classified VO, so the handler's only
    job is being on the dispatcher's registry, not transforming anything."""
    expected = ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=100,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=0,
    )
    reader = Mock()
    reader.check_connection.return_value = expected
    handler = GetExchangeConnectionStatusQueryHandler(
        FakeVenueContexts(
            venue_context(TradingVenue.FUTURES_TESTNET, account_reader=reader)
        )
    )

    result = handler.execute(
        GetExchangeConnectionStatusQuery(venue=TradingVenue.FUTURES_TESTNET)
    )

    assert result is expected
    reader.check_connection.assert_called_once_with()


def test_execute_returns_a_failure_status_unchanged_too():
    expected = ExchangeConnectionStatus(
        venue=TradingVenue.DISABLED,
        reachable=False,
        failure=ConnectionFailureKind.NOT_CONFIGURED,
        server_time_skew_ms=None,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
    )
    reader = Mock()
    reader.check_connection.return_value = expected
    handler = GetExchangeConnectionStatusQueryHandler(
        FakeVenueContexts(
            venue_context(TradingVenue.FUTURES_TESTNET, account_reader=reader)
        )
    )

    assert (
        handler.execute(
            GetExchangeConnectionStatusQuery(venue=TradingVenue.FUTURES_TESTNET)
        )
        is expected
    )
