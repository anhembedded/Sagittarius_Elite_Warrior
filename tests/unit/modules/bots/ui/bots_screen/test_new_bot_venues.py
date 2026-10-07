"""`BUG-155` — which venues New bot offers."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .bots_screen_fixtures import VENUE, Answers


def test_new_bot_offers_the_spot_venue_even_when_none_is_enabled(
    open_bots_screen, qtbot
) -> None:
    """`BUG-155` — Venue never blocks New bot. With no Spot venue enabled the
    dialog was given an empty list and Create stayed disabled; the Spot
    venues are offered whether or not they are enabled (Start and the planner
    already refuse a venue that is not enabled)."""
    answers = Answers()
    screen = open_bots_screen(answers=answers, venue_enabled=False)
    screen.settle()

    screen.view.model.new_bot_requested.emit()
    screen.settle()

    assert answers.asked == [
        f"new bot ['grid'] ['{VENUE.value}', '{TradingVenue.SPOT_MAINNET.value}']"
    ]
