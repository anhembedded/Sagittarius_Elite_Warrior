"""`BOT-219` — which venue's strategy a command acts on, asked in a small dialog.

Bots → Disarm strategy… asks it when more than one venue has a strategy armed; it is skipped when
one has. A stock `QInputDialog` with a drop-down, titled with the command and with the command's own
verb on its commit button (`ui-presentation-rule.md` §7); Cancel leaves everything as it was.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QDialog, QInputDialog, QWidget
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class VenueQuestion:
    """What is asked: the dialog's title, its question, its commit verb, and each venue with the
    words that describe it."""

    title: str
    prompt: str
    ok_text: str
    options: tuple[tuple[TradingVenue, str], ...]


#: Asks which venue; the venue chosen, or `None` when cancelled.
type ChooseVenue = Callable[[VenueQuestion], TradingVenue | None]


def venue_chooser(parent: QWidget | None, question: VenueQuestion) -> QInputDialog:
    """The chooser, built and not yet shown (a test pictures it)."""
    dialog = QInputDialog(parent.window() if parent is not None else None)
    dialog.setObjectName("dlgChooseVenue")
    dialog.setWindowTitle(question.title)
    dialog.setLabelText(question.prompt)
    dialog.setOkButtonText(question.ok_text)
    dialog.setComboBoxEditable(False)
    dialog.setComboBoxItems([words for _venue, words in question.options])
    return dialog


def choose_venue_with_dialog(
    parent: QWidget, question: VenueQuestion
) -> TradingVenue | None:
    """The modal chooser, parented to `parent`'s window."""
    dialog = venue_chooser(parent, question)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    index = dialog.comboBoxItems().index(dialog.textValue())
    return question.options[index][0]
