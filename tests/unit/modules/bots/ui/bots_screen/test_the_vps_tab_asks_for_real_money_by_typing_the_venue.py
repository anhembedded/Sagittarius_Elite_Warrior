"""`EPIC-047E` (AC4) - a command to the VPS host that puts orders on a mainnet venue needs the venue typed, every time.

The business promise: the host cannot ask, so the desktop asks as the command line does; a testnet is never asked; nothing is
remembered between two commands; a wrong word or a cancel sends nothing.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialogButtonBox
from pytestqt.qtbot import QtBot
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.typed_venue_consent import (
    TypedVenueConsent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.typed_venue_dialog import (
    SEND_TEXT,
    TypedVenueDialog,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

MAINNET = TradingVenue.FUTURES_MAINNET


class _Typing:
    def __init__(self, *answers: str | None) -> None:
        self._answers = list(answers)
        self.asked: list[tuple[TradingVenue, str]] = []

    def __call__(self, venue: TradingVenue, action: str) -> str | None:
        self.asked.append((venue, action))
        return self._answers.pop(0)


def test_a_testnet_is_never_asked() -> None:
    typing = _Typing()

    assert TypedVenueConsent(typing).confirmed(TradingVenue.FUTURES_TESTNET, "start")
    assert typing.asked == []


def test_the_venue_typed_exactly_confirms() -> None:
    typing = _Typing(MAINNET.confirmation_word)

    assert TypedVenueConsent(typing).confirmed(MAINNET, "start this bot")
    assert typing.asked == [(MAINNET, "start this bot")]


@pytest.mark.parametrize("typed", ["", "futures", "FUTURES_MAINNET", "yes", None])
def test_anything_but_the_venue_sends_nothing(typed: str | None) -> None:
    assert not TypedVenueConsent(_Typing(typed)).confirmed(MAINNET, "start")


def test_the_answer_is_not_remembered_for_the_next_command() -> None:
    typing = _Typing(MAINNET.confirmation_word, MAINNET.confirmation_word)
    consent = TypedVenueConsent(typing)

    consent.confirmed(MAINNET, "start")
    consent.confirmed(MAINNET, "resume")

    assert [action for _, action in typing.asked] == ["start", "resume"]


def test_the_dialog_enables_its_button_only_for_the_exact_word(qtbot: QtBot) -> None:
    dialog = TypedVenueDialog(MAINNET, "start")
    qtbot.addWidget(dialog)

    assert dialog.send.text() == SEND_TEXT
    assert not dialog.send.isEnabled()
    dialog.typed.setText("futures")
    assert not dialog.send.isEnabled()
    dialog.typed.setText(MAINNET.confirmation_word)
    assert dialog.send.isEnabled()


def test_cancel_is_the_default_so_enter_on_an_empty_box_sends_nothing(
    qtbot: QtBot,
) -> None:
    dialog = TypedVenueDialog(MAINNET, "start")
    qtbot.addWidget(dialog)

    cancel = dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)

    assert cancel.isDefault()
    assert not dialog.send.isDefault()
