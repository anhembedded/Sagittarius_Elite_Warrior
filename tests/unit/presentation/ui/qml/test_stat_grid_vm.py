"""`StatGridVM` — no GUI."""

from __future__ import annotations

from enum import Enum

from Sagittarius_Elite_Warrior.src.presentation.ui.qml.StatGrid.stat_grid_vm import (
    StatGridVM,
)


class _Tone(Enum):
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    NEGATIVE = "negative"


def test_cards_are_empty_until_refreshed():
    vm = StatGridVM(get_cards=lambda: [{"title": "x", "value": "1"}])
    assert vm.cards == []


def test_a_card_is_shaped_for_qml():
    vm = StatGridVM(
        get_cards=lambda: [
            {
                "title": "win rate",
                "value": "62.5",
                "suffix": "%",
                "valueTone": _Tone.POSITIVE,
            }
        ]
    )
    vm.refresh()

    assert vm.cards == [
        {"title": "WIN RATE", "value": "62.5", "suffix": "%", "tone": "POSITIVE"}
    ]


def test_a_missing_tone_defaults_to_neutral():
    """A stat card with no verdict attached (a plain count, not a win/loss
    signal) must not render in an accidental colour."""
    vm = StatGridVM(get_cards=lambda: [{"title": "trades", "value": "40"}])
    vm.refresh()

    assert vm.cards[0]["tone"] == "NEUTRAL"


def test_a_missing_suffix_is_empty_not_none():
    """QML reads `modelData.suffix !== ""` — `None` would render the string
    "None" instead of hiding the suffix label."""
    vm = StatGridVM(get_cards=lambda: [{"title": "x", "value": "1"}])
    vm.refresh()

    assert vm.cards[0]["suffix"] == ""


def test_refresh_announces_the_change():
    vm = StatGridVM(get_cards=list)
    fired: list[int] = []
    vm.cardsChanged.connect(lambda: fired.append(1))

    vm.refresh()

    assert fired == [1]
