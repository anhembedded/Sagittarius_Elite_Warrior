"""`EPIC-028I` — `FuturesSettingsService` sends `EPIC-028F`'s commands,
addressed to its own venue, and hands back the exchange's answer."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.change_leverage.command import (
    ChangeLeverageCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.change_margin_type.command import (
    ChangeMarginTypeCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.futures_settings_service import (
    FuturesSettingsService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_result import (
    AccountControlResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_setting import (
    LeverageSetting,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_FUTURES = TradingVenue.FUTURES_TESTNET


class _AnsweringDispatcher(ICommandDispatcher):
    def __init__(self, answers: dict[type, object]) -> None:
        self._answers = answers
        self.dispatched: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.dispatched.append(input_dto)
        return self._answers.get(handler_class)


def test_both_changes_are_addressed_to_the_services_venue() -> None:
    leverage = AccountControlResult(None, LeverageSetting("BTCUSDT", 5, Decimal(10**6)))
    margin = AccountControlResult(None, MarginType.ISOLATED)
    dispatcher = _AnsweringDispatcher(
        {ChangeLeverageCommand: leverage, ChangeMarginTypeCommand: margin}
    )
    service = FuturesSettingsService(dispatcher, _FUTURES)

    assert service.change_leverage("BTCUSDT", 5) is leverage
    assert service.change_margin_type("BTCUSDT", MarginType.ISOLATED) is margin
    assert dispatcher.dispatched == [
        ChangeLeverageCommand("BTCUSDT", 5, venue=_FUTURES),
        ChangeMarginTypeCommand("BTCUSDT", MarginType.ISOLATED, venue=_FUTURES),
    ]


def test_an_unbound_handler_is_named() -> None:
    service = FuturesSettingsService(_AnsweringDispatcher({}), _FUTURES)

    with pytest.raises(TypeError, match="ChangeLeverageCommand .* not bound"):
        service.change_leverage("BTCUSDT", 5)
