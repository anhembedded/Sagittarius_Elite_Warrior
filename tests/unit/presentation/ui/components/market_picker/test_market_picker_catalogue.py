"""Tests for the market catalogue — pure, no QApplication needed."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.domain.value_objects.market_type import MarketType
from Sagittarius_Elite_Warrior.src.presentation.ui.components.market_picker import (
    MARKET_OPTIONS,
)


def test_every_market_type_is_offered():
    ids = [option["id"] for option in MARKET_OPTIONS]

    assert sorted(ids) == sorted(member.value for member in MarketType)


def test_spot_is_offered_first():
    """Matches the mockup: Spot, then the two futures markets."""
    assert MARKET_OPTIONS[0]["id"] == MarketType.SPOT.value


def test_every_market_has_a_non_empty_label():
    for option in MARKET_OPTIONS:
        assert option["label"].strip() != ""
