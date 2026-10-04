"""`EPIC-028I` — `IFuturesSettingsControl`, implemented over `EPIC-028F`'s
venue-addressed commands.

Same shape as `OrderSubmissionService`: a façade over the dispatcher, one
instance per venue, stamping its own venue on every command. Each answer's
type is checked, so an unbound handler is named instead of handing `None`
to a chip.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.change_leverage.command import (
    ChangeLeverageCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.change_margin_type.command import (
    ChangeMarginTypeCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_result import (
    AccountControlResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_futures_settings_control import (
    IFuturesSettingsControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_setting import (
    LeverageSetting,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class FuturesSettingsService(IFuturesSettingsControl):
    """The leverage and margin-mode control of one venue (`EPIC-028I`)."""

    def __init__(self, dispatcher: ICommandDispatcher, venue: TradingVenue) -> None:
        self._dispatcher = dispatcher
        self._venue = venue

    def change_leverage(
        self, symbol: str, leverage: int
    ) -> AccountControlResult[LeverageSetting]:
        command = ChangeLeverageCommand(symbol, leverage, venue=self._venue)
        return _result(
            command, self._dispatcher.dispatch(ChangeLeverageCommand, command)
        )

    def change_margin_type(
        self, symbol: str, margin_type: MarginType
    ) -> AccountControlResult[MarginType]:
        command = ChangeMarginTypeCommand(symbol, margin_type, venue=self._venue)
        return _result(
            command, self._dispatcher.dispatch(ChangeMarginTypeCommand, command)
        )


def _result[T](command: object, answer: object) -> AccountControlResult[T]:
    if not isinstance(answer, AccountControlResult):
        raise TypeError(
            f"{type(command).__name__} was answered with {type(answer).__name__}, "
            "not AccountControlResult — its handler is not bound"
        )
    return answer
