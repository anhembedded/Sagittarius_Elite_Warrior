"""`EPIC-029F` — every question the Bots screen asks, injectable as one value.

The defaults are modal dialogs parented to the screen; a test hands in plain
functions, so it drives the screen without a dialog waiting for a click (the
shape `AccountTabConfirmations` set).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.export_plan_dialog import (
    AskExportPlan,
    ask_export_plan_with_dialog,
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
    ArmQuestion,
    AskArmStrategy,
    ask_arm_with_dialog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.disarm_choice import (
    ChooseVenue,
    choose_venue_with_dialog,
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
#: The suggested file name -> the path the person chose, `""` when they cancelled
#: (`BOT-176`).
type AskPlanSavePath = Callable[[str], str]


@dataclass(frozen=True)
class BotsDialogs:
    ask_new_bot: AskNewBot
    ask_stop: AskStop
    confirm_delete: ConfirmDelete
    #: Bots → Arm strategy… (`EPIC-033K` stage 3, `BOT-219`: what to arm and on which venue).
    ask_arm_strategy: AskArmStrategy
    #: Bots → Disarm strategy…: which armed venue (`BOT-219`).
    choose_venue: ChooseVenue
    allow_real_money: AllowRealMoney
    #: Bots → Export plan… (`BOT-176`): which bots and how, then where to save.
    ask_export_plan: AskExportPlan
    ask_plan_save_path: AskPlanSavePath


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
        ask_arm_strategy=lambda question: _ask_arm(parent, question, consent),
        choose_venue=lambda choice: choose_venue_with_dialog(parent, choice),
        allow_real_money=consent.confirmed,
        ask_export_plan=lambda bots, selected: ask_export_plan_with_dialog(
            parent, bots, selected
        ),
        ask_plan_save_path=lambda suggested: _ask_plan_save_path(parent, suggested),
    )


def _ask_arm(
    parent: QWidget, question: ArmQuestion, consent: IRealMoneyConsent
) -> TradingVenue | None:
    """The dialog first, then the real-money question for the venue it chose: a mainnet venue's
    first Arm of the session asks (`EPIC-034` D3, D11), and a refusal arms nothing."""
    venue = ask_arm_with_dialog(parent, question)
    if venue is None or not consent.confirmed(venue, "arm a strategy"):
        return None
    return venue


def _ask_plan_save_path(parent: QWidget, suggested: str) -> str:
    """A native save dialog that does not ask "replace?": the writer never overwrites,
    so the question would be asked about a file it refuses anyway."""
    path, _selected_filter = QFileDialog.getSaveFileName(
        parent,
        "Export plan",
        suggested,
        "Bot plan (*.json)",
        options=QFileDialog.Option.DontConfirmOverwrite,
    )
    return path


def _ask_delete(parent: QWidget, bot: BotSnapshot) -> bool:
    answer = QMessageBox.question(
        parent,
        f"Delete {bot.name}",
        delete_question(bot),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes
