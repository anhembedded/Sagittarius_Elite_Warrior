"""`EPIC-028F` — `ChangeLeverageCommandHandler`: sets one Futures symbol's
leverage on the addressed venue, after `clear_account_control`'s checks."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.account_control_gate import (
    AccountControlRefused,
    clear_account_control,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.change_leverage.command import (
    ChangeLeverageCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_rejected_error import (
    AccountControlRejectedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_result import (
    AccountControlRefusal,
    AccountControlResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_setting import (
    LeverageSetting,
)

logger = logging.getLogger("App.CommandHandler")


class ChangeLeverageCommandHandler(
    ICommandHandler[ChangeLeverageCommand, AccountControlResult[LeverageSetting]]
):
    """@details An exchange refusal is an answer, returned as
    `EXCHANGE_REJECTED`; an exchange that never answered raises
    `AccountControlUnavailableError`, because nothing is known to have
    changed."""

    def __init__(self, scopes: VenueTradingScopes) -> None:
        self._scopes = scopes

    def execute(
        self, command: ChangeLeverageCommand
    ) -> AccountControlResult[LeverageSetting]:
        logger.debug(
            "Handling ChangeLeverageCommand: %s to %dx on %s",
            command.symbol,
            command.leverage,
            command.venue.value,
        )
        cleared = clear_account_control(self._scopes, command.venue, command.symbol)
        if isinstance(cleared, AccountControlRefused):
            logger.info(
                "[account-control] leverage change on %s %s refused: %s",
                command.venue.value,
                command.symbol,
                cleared.blocked_by.value,
            )
            return AccountControlResult(cleared.blocked_by, None, cleared.detail)
        try:
            applied = cleared.control.change_leverage(command.symbol, command.leverage)
        except AccountControlRejectedError as refusal:
            logger.info(
                "[account-control] exchange refused leverage %dx on %s %s: %s",
                command.leverage,
                command.venue.value,
                command.symbol,
                refusal,
            )
            return AccountControlResult(
                AccountControlRefusal.EXCHANGE_REJECTED, None, str(refusal)
            )
        logger.info(
            "[account-control] %s %s leverage is now %dx (max notional %s)",
            command.venue.value,
            applied.symbol,
            applied.leverage,
            applied.max_notional,
        )
        return AccountControlResult(None, applied)
