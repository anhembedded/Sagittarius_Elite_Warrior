"""`EPIC-035H` review (finding 10) — a read-only copy's leverage and margin-mode
changes come back as an answer, not as an exception through the handler.

The handlers run over the real `ReadOnlyAccountControl`; the inner control is a
spec'd mock that must never be asked to change anything.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.read_only_account_control import (
    ReadOnlyAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.change_leverage import (
    ChangeLeverageCommand,
    ChangeLeverageCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.change_margin_type import (
    ChangeMarginTypeCommand,
    ChangeMarginTypeCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_result import (
    AccountControlRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_futures_account_control import (
    IFuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_account_reader import (
    FakeTradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    single_venue_scopes,
    venue_context,
)

_VENUE = TradingVenue.FUTURES_TESTNET
_REASON = "Another copy is running; this one is read-only."


def _handlers() -> tuple[
    ChangeLeverageCommandHandler, ChangeMarginTypeCommandHandler, Mock
]:
    inner = Mock(spec=IFuturesAccountControl)
    inner.open_position.return_value = Decimal(0)
    status = ExchangeConnectionStatus(
        venue=_VENUE,
        reachable=True,
        failure=None,
        server_time_skew_ms=0,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=0,
    )
    context = venue_context(
        _VENUE,
        account_reader=FakeTradingAccountReader(status),
        account_control=ReadOnlyAccountControl(inner, _REASON),
    )
    state = TradingSessionState()
    state.enable(set())
    scopes = single_venue_scopes(context, state)
    return (
        ChangeLeverageCommandHandler(scopes),
        ChangeMarginTypeCommandHandler(scopes),
        inner,
    )


def test_a_leverage_change_is_answered_read_only() -> None:
    leverage, _margin, inner = _handlers()

    result = leverage.execute(ChangeLeverageCommand("BTCUSDT", 10, venue=_VENUE))

    assert result.blocked_by is AccountControlRefusal.READ_ONLY_INSTANCE
    assert result.detail == _REASON
    inner.change_leverage.assert_not_called()


def test_a_margin_mode_change_is_answered_read_only() -> None:
    _leverage, margin, inner = _handlers()

    result = margin.execute(
        ChangeMarginTypeCommand("BTCUSDT", MarginType.ISOLATED, venue=_VENUE)
    )

    assert result.blocked_by is AccountControlRefusal.READ_ONLY_INSTANCE
    assert result.detail == _REASON
    inner.change_margin_type.assert_not_called()


@pytest.mark.parametrize("which", ["leverage", "margin"])
def test_nothing_escapes_the_handler(which: str) -> None:
    leverage, margin, _inner = _handlers()

    if which == "leverage":
        leverage.execute(ChangeLeverageCommand("BTCUSDT", 5, venue=_VENUE))
    else:
        margin.execute(
            ChangeMarginTypeCommand("BTCUSDT", MarginType.CROSSED, venue=_VENUE)
        )
