"""`EPIC-029F` — what Stop asks before it acts (ADR O3).

Stopping cancels every resting order the bot placed, at the exchange; that
much is not a choice, and the dialog says so first. The choice is what the
bot holds: keep it (preselected on Spot, per O3) or end it at market. A venue
that cannot keep it (`keep_on_stop_closed_reason`, the question the use case
asks too) shows "keep" disabled with its reason and preselects the close
(`BUG-219`).
Injectable (`AskStop`) so a test stops a bot without a modal dialog.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    SPOT_PROFILE,
    VenueProfile,
    keep_on_stop_closed_reason,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

#: The answer, or `None` when the user cancelled.
type AskStop = Callable[[BotSnapshot], ExposureHandling | None]

STOP_BUTTON_TEXT = "Stop bot"


def _profile_of(bot: BotSnapshot) -> VenueProfile:
    """The venue's profile; a venue that trades no market is described as Spot."""
    return venue_profile_of(bot.venue) or SPOT_PROFILE


def stop_question(bot: BotSnapshot) -> str:
    held = bot.progress.inventory if bot.progress is not None else None
    word = _profile_of(bot).held_word
    if held is not None and held > 0:
        quantity = write_value(ColumnKind.QUANTITY, held)
        holding = (
            f"It holds a {quantity} {bot.symbol} {word}."
            if word == "position"
            else f"It holds {quantity} {bot.symbol} {word}."
        )
    else:
        holding = (
            f"It holds no {word}."
            if word == "position"
            else f"It holds no {word} the run bought."
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
        profile = _profile_of(bot)
        self.keep = QRadioButton(f"Keep the {profile.held_word} in the account")
        self.keep.setObjectName("radioStopKeepBase")
        self.sell = QRadioButton(profile.close_at_market_label)
        self.sell.setObjectName("radioStopSellBase")
        self.keep_reason = plain_label("")
        self.keep_reason.setObjectName("lblStopKeepReason")
        group = QButtonGroup(self)
        group.addButton(self.keep)
        group.addButton(self.sell)
        closed = keep_on_stop_closed_reason(profile)
        if closed is None:
            self.keep.setChecked(True)
        else:
            self.keep.setEnabled(False)
            self.keep.setToolTip(closed)
            self.keep_reason.setText(closed)
            self.sell.setChecked(True)
        keep_row = QHBoxLayout()
        keep_row.addWidget(self.keep)
        keep_row.addWidget(self.keep_reason, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        stop = buttons.addButton(
            STOP_BUTTON_TEXT, QDialogButtonBox.ButtonRole.AcceptRole
        )
        stop.setObjectName("btnConfirmStop")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(text)
        layout.addLayout(keep_row)
        layout.addWidget(self.sell)
        layout.addWidget(buttons)

    def choice(self) -> ExposureHandling:
        return (
            ExposureHandling.CLOSE_AT_MARKET
            if self.sell.isChecked()
            else ExposureHandling.KEEP
        )


def ask_stop_with_dialog(parent: QWidget, bot: BotSnapshot) -> ExposureHandling | None:
    dialog = StopBotDialog(bot, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.choice()
