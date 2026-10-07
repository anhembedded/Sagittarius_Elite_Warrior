"""`EPIC-029F` — every question the Bots screen asks, injectable as one value.

The defaults are modal dialogs parented to the screen; a test hands in plain
functions, so it drives the screen without a dialog waiting for a click (the
shape `AccountTabConfirmations` set).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QMessageBox, QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.new_bot_dialog import (
    AskNewBot,
    ask_new_bot_with_dialog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.new_bot_symbols import (
    NewBotSymbols,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.stop_bot_dialog import (
    AskStop,
    ask_stop_with_dialog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.arm_strategy_dialog import (
    AskArmStrategy,
    ask_arm_with_dialog,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_real_money_consent import (
    IRealMoneyConsent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

type ConfirmDelete = Callable[[BotSnapshot], bool]
#: `(venue, what)` -> may it go on: the one question that names real money, asked
#: on a mainnet venue's first Start or Arm of the session (`EPIC-034` D3, D11).
type AllowRealMoney = Callable[[TradingVenue, str], bool]


@dataclass(frozen=True)
class BotsDialogs:
    ask_new_bot: AskNewBot
    ask_stop: AskStop
    confirm_delete: ConfirmDelete
    #: Bots → Arm strategy… (`EPIC-033K` stage 3).
    ask_arm_strategy: AskArmStrategy
    allow_real_money: AllowRealMoney


def delete_question(bot: BotSnapshot) -> str:
    return (
        f"Delete {bot.name}? Its definition and its run's record are removed "
        "from this computer. Nothing is sent to the exchange."
    )


def dialogs_for(
    parent: QWidget,
    symbols: NewBotSymbols,
    consent: IRealMoneyConsent,
) -> BotsDialogs:
    """The modal dialogs, parented to `parent`; `symbols` feeds New bot's
    picker; `consent` is asked before a mainnet venue's first Start or Arm."""
    return BotsDialogs(
        ask_new_bot=lambda kinds, venues: ask_new_bot_with_dialog(
            parent, kinds, venues, symbols
        ),
        ask_stop=lambda bot: ask_stop_with_dialog(parent, bot),
        confirm_delete=lambda bot: _ask_delete(parent, bot),
        ask_arm_strategy=lambda venue, form: (
            consent.confirmed(venue, "arm a strategy")
            and ask_arm_with_dialog(parent, venue, form)
        ),
        allow_real_money=consent.confirmed,
    )


def _ask_delete(parent: QWidget, bot: BotSnapshot) -> bool:
    answer = QMessageBox.question(
        parent,
        f"Delete {bot.name}",
        delete_question(bot),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes
