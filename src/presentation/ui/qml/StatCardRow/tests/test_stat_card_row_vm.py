"""`StatCardRowVM` — no GUI, no QApplication."""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Tone
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.StatCardRow.stat_card_row_vm import (
    StatCardRowVM,
)


def test_cards_are_empty_until_refreshed():
    vm = StatCardRowVM(get_cards=lambda: [{"title": "x", "value": "1"}])
    assert vm.cards == []


def test_a_card_is_shaped_for_qml():
    vm = StatCardRowVM(
        get_cards=lambda: [
            {
                "title": "Tổng Lãi/Lỗ (Net PnL)",
                "value": "+1,148.19",
                "valueTone": Tone.POSITIVE,
                "suffix": "USD",
                "badgeText": "+11.48%",
                "badgeTone": Tone.POSITIVE,
            }
        ]
    )
    vm.refresh()

    assert vm.cards == [
        {
            "title": "Tổng Lãi/Lỗ (Net PnL)",
            "value": "+1,148.19",
            "suffix": "USD",
            "tone": "positive",
            "badgeText": "+11.48%",
            "badgeTone": "positive",
        }
    ]


def test_title_is_not_uppercased_here():
    """Unlike `StatGridVM`, this VM leaves `title` untouched — `StatCard.qml`
    already calls `toUpperCase()` on it, so upper-casing here too would just
    make `StatCardRowVM.cards` a lossy copy of its own input for no reason."""
    vm = StatCardRowVM(get_cards=lambda: [{"title": "win rate", "value": "62.5"}])
    vm.refresh()

    assert vm.cards[0]["title"] == "win rate"


def test_a_missing_tone_defaults_to_neutral():
    """A stat card with no verdict attached (a plain count, not a win/loss
    signal) must not render in an accidental colour."""
    vm = StatCardRowVM(get_cards=lambda: [{"title": "trades", "value": "40"}])
    vm.refresh()

    assert vm.cards[0]["tone"] == "neutral"
    assert vm.cards[0]["badgeTone"] == "neutral"


def test_a_non_tone_value_defaults_to_neutral_instead_of_raising():
    """Defensive, not just for a missing key — the same fallback covers a
    stray string or `None` some future caller might pass instead of a real
    `Tone` member."""
    vm = StatCardRowVM(
        get_cards=lambda: [{"title": "x", "value": "1", "valueTone": "POSITIVE"}]
    )
    vm.refresh()

    assert vm.cards[0]["tone"] == "neutral"


def test_a_missing_suffix_and_badge_are_empty_not_none():
    """QML reads `modelData.suffix !== ""`/`modelData.badgeText !== ""` —
    `None` would render the string "None" instead of hiding the label."""
    vm = StatCardRowVM(get_cards=lambda: [{"title": "x", "value": "1"}])
    vm.refresh()

    assert vm.cards[0]["suffix"] == ""
    assert vm.cards[0]["badgeText"] == ""


def test_refresh_announces_the_change():
    vm = StatCardRowVM(get_cards=list)
    fired: list[int] = []
    vm.cardsChanged.connect(lambda: fired.append(1))

    vm.refresh()

    assert fired == [1]


def test_refresh_reflects_the_live_source_each_call():
    """`get_cards` is a callback, not a snapshot taken at construction —
    the row must reflect whatever `BackTestViewModel.primaryStatCards` holds
    at the moment of each `refresh()` call."""
    cards: list[dict[str, object]] = []
    vm = StatCardRowVM(get_cards=lambda: cards)

    vm.refresh()
    assert vm.cards == []

    cards.append({"title": "x", "value": "1"})
    vm.refresh()
    assert len(vm.cards) == 1
