"""`EPIC-047E` (AC4) — the dialog behind `TypedVenueConsent`: type the venue to confirm, or cancel.

@details A stock `QDialog` with a line edit and a `QDialogButtonBox`: the confirming button names what it does ("Send to the
VPS", never OK) and stays disabled until the text equals the venue's identifier exactly, and Cancel is the default, so Enter
on an empty box sends nothing (`ui-presentation-rule.md` §7, `mess-confirm`).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

SEND_TEXT = "Send to the VPS"


def question_for(venue: TradingVenue, action: str) -> str:
    return (
        f"This will {action} with real money on {venue.display_name}, through the VPS host.\n"
        f"Type {venue.confirmation_word} to confirm."
    )


class TypedVenueDialog(QDialog):
    def __init__(
        self, venue: TradingVenue, action: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dlgConfirmRealMoney")
        self.setWindowTitle("Confirm Real Money")
        self._venue = venue
        self.question = plain_label(question_for(venue, action))
        self.question.setWordWrap(True)
        self.typed = QLineEdit()
        self.typed.setObjectName("edtTypedVenue")
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.send = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.send.setText(SEND_TEXT)
        self.send.setEnabled(False)
        self.send.setAutoDefault(False)
        cancel = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel.setDefault(True)
        column = QVBoxLayout(self)
        column.addWidget(self.question)
        column.addWidget(self.typed)
        column.addWidget(self.buttons)
        self.typed.textChanged.connect(self._on_typed)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    def _on_typed(self, text: str) -> None:
        self.send.setEnabled(text.strip() == self._venue.confirmation_word)


def ask_typed_venue(venue: TradingVenue, action: str) -> str | None:
    """Runs the dialog over the active window; the venue typed, or `None` when cancelled."""
    dialog = TypedVenueDialog(venue, action, QApplication.activeWindow())
    accepted = dialog.exec() == QDialog.DialogCode.Accepted
    return dialog.typed.text() if accepted else None
