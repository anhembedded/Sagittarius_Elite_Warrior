"""`EPIC-029F` — what Stop asks before it acts (ADR O3).

Stopping cancels every resting order the bot placed, at the exchange; that
much is not a choice, and the dialog says so first. The choice is the base the
bot holds: keep it (preselected, every time, per O3) or sell it at market.
Injectable (`AskStop`) so a test stops a bot without a modal dialog.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

#: The answer, or `None` when the user cancelled.
type AskStop = Callable[[BotSnapshot], BaseHandling | None]

STOP_BUTTON_TEXT = "Stop bot"


def stop_question(bot: BotSnapshot) -> str:
    held = bot.progress.inventory if bot.progress is not None else None
    holding = (
        f"It holds {write_value(ColumnKind.QUANTITY, held)} {bot.symbol} base."
        if held is not None and held > 0
        else "It holds no base the run bought."
    )
    return (
        f"Stop {bot.name}? Every resting order it placed on {bot.venue.display_name} is "
        f"cancelled at the exchange. {holding}"
    )


class StopBotDialog(QDialog):
    """@brief Asks how to stop one bot."""

    def __init__(self, bot: BotSnapshot, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Stop {bot.name}")
        text = plain_label(stop_question(bot))
        text.setWordWrap(True)
        self.keep = QRadioButton("Keep the base in the account")
        self.keep.setObjectName("radioStopKeepBase")
        self.sell = QRadioButton("Sell the base at market")
        self.sell.setObjectName("radioStopSellBase")
        group = QButtonGroup(self)
        group.addButton(self.keep)
        group.addButton(self.sell)
        self.keep.setChecked(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        stop = buttons.addButton(
            STOP_BUTTON_TEXT, QDialogButtonBox.ButtonRole.AcceptRole
        )
        stop.setObjectName("btnConfirmStop")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(text)
        layout.addWidget(self.keep)
        layout.addWidget(self.sell)
        layout.addWidget(buttons)

    def choice(self) -> BaseHandling:
        return (
            BaseHandling.SELL_AT_MARKET if self.sell.isChecked() else BaseHandling.KEEP
        )


def ask_stop_with_dialog(parent: QWidget, bot: BotSnapshot) -> BaseHandling | None:
    dialog = StopBotDialog(bot, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.choice()
