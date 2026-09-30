"""`EPIC-028F` — `ChangeMarginTypeCommandHandler`: sets one Futures symbol's
margin mode on the addressed venue, after `clear_account_control`'s
checks."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.account_control_gate import (
    AccountControlRefused,
    clear_account_control,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.change_margin_type.command import (
    ChangeMarginTypeCommand,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)

logger = logging.getLogger("App.CommandHandler")


class ChangeMarginTypeCommandHandler(
    ICommandHandler[ChangeMarginTypeCommand, AccountControlResult[MarginType]]
):
    """@details Refuses and reports as `ChangeLeverageCommandHandler` does.
    Binance also refuses a change while the symbol has open orders; that
    refusal comes back as `EXCHANGE_REJECTED` with the exchange's own
    message."""

    def __init__(self, scopes: VenueTradingScopes) -> None:
        self._scopes = scopes

    def execute(
        self, command: ChangeMarginTypeCommand
    ) -> AccountControlResult[MarginType]:
        logger.debug(
            "Handling ChangeMarginTypeCommand: %s to %s on %s",
            command.symbol,
            command.margin_type.value,
            command.venue.value,
        )
        cleared = clear_account_control(self._scopes, command.venue, command.symbol)
        if isinstance(cleared, AccountControlRefused):
            logger.info(
                "[account-control] margin-mode change on %s %s refused: %s",
                command.venue.value,
                command.symbol,
                cleared.blocked_by.value,
            )
            return AccountControlResult(cleared.blocked_by, None, cleared.detail)
        try:
            applied = cleared.control.change_margin_type(
                command.symbol, command.margin_type
            )
        except AccountControlRejectedError as refusal:
            logger.info(
                "[account-control] exchange refused margin mode %s on %s %s: %s",
                command.margin_type.value,
                command.venue.value,
                command.symbol,
                refusal,
            )
            return AccountControlResult(
                AccountControlRefusal.EXCHANGE_REJECTED, None, str(refusal)
            )
        logger.info(
            "[account-control] %s %s margin mode is now %s",
            command.venue.value,
            command.symbol,
            applied.value,
        )
        return AccountControlResult(None, applied)
