"""`EPIC-039H` - the holder of a symbol's lease may change its own symbol's leverage and margin mode.

@details A bot holds its symbol's lease for the whole run and makes the symbol match its leverage and
margin mode before its first order (`IVenueSettingsGate`). The gate refused every holder, because
it was written for a strategy whose next order would lock a different margin than it sized for;
the first Futures Grid on the fake exchange was refused by its own lease (`symbol_leased`). The
holder asking is let through, and anyone else is still refused while the symbol is leased.
"""

from __future__ import annotations

from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.change_leverage import (
    ChangeLeverageCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.change_margin_type import (
    ChangeMarginTypeCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_result import (
    AccountControlResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    MANUAL_OWNER,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.account_control.test_account_control_commands import (
    _EITHER_COMMAND,
    _desk,
)

_FUTURES = TradingVenue.FUTURES_TESTNET
_BOT = "bot.a3f9c1"


def _leverage_by(desk: Any, owner_id: str) -> AccountControlResult[Any]:
    return desk.leverage.execute(
        ChangeLeverageCommand("BTCUSDT", 10, venue=_FUTURES, owner_id=owner_id)
    )


def _margin_by(desk: Any, owner_id: str) -> AccountControlResult[Any]:
    return desk.margin.execute(
        ChangeMarginTypeCommand(
            "BTCUSDT", MarginType.ISOLATED, venue=_FUTURES, owner_id=owner_id
        )
    )


@pytest.mark.parametrize(
    "change", [_leverage_by, _margin_by], ids=["leverage", "margin"]
)
def test_the_holder_of_the_lease_changes_its_own_symbol(change: Any) -> None:
    desk = _desk()
    desk.raw.futures_change_leverage.return_value = {
        "symbol": "BTCUSDT",
        "leverage": 10,
        "maxNotionalValue": "10000000",
    }
    desk.raw.futures_change_margin_type.return_value = {"code": 200, "msg": "success"}
    desk.state.claim_symbol("BTCUSDT", _BOT)

    result = change(desk, _BOT)

    assert result.blocked_by is None, result.detail


@pytest.mark.parametrize(
    "change", [_leverage_by, _margin_by], ids=["leverage", "margin"]
)
def test_another_owner_is_still_refused_while_the_symbol_is_leased(change: Any) -> None:
    desk = _desk()
    desk.state.claim_symbol("BTCUSDT", _BOT)

    result = change(desk, "bot.other")

    assert result.blocked_by is ExecuteOrderSafetyGate.SYMBOL_LEASED
    assert desk.sessions.opened == 0


@_EITHER_COMMAND
def test_a_human_at_the_desk_is_refused_while_a_bot_holds_the_symbol(
    change: Any,
) -> None:
    """The commands default to the unprivileged owner, so a caller that forgets to say who
    it is is refused on a leased symbol, as the order path refuses it."""
    desk = _desk()
    desk.state.claim_symbol("BTCUSDT", _BOT)

    result = change(desk)

    assert result.blocked_by is ExecuteOrderSafetyGate.SYMBOL_LEASED
    assert ChangeLeverageCommand("BTCUSDT", 10, venue=_FUTURES).owner_id == MANUAL_OWNER
