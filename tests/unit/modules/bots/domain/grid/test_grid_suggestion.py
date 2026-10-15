"""`BUG-211` — a suggested plan passes every blocking check, whatever the exits were.

The owner's Spot ETHUSDT grid (6 arithmetic grids, 35 capital, stop loss 2259, take profit 2805,
price 2368.155): the ATR and the Bollinger suggestions wrote only the range, so the plan kept an
exit the new range made invalid (`STOP_LOSS_INSIDE_RANGE`, `TAKE_PROFIT_INSIDE_RANGE`) and the
Bollinger band, entirely above the price, refused Start (`PRICE_BELOW_RANGE`).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
    ExchangeTerms,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_suggestion import (
    PlanSuggestion,
    SuggestionRequest,
    suggest_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)

_PRICE = Decimal("2368.155")
_TERMS = ExchangeTerms(
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.0001"),
    min_notional=Decimal(5),
    maker_fee=Decimal("0.001"),
    taker_fee=Decimal("0.001"),
    max_notional_per_order=Decimal(5000),
    max_open_orders=100,
)
_OWNER = {
    "lower": "2000",
    "upper": "3000",
    "grid_count": "6",
    "spacing": "ARITHMETIC",
    "capital_quote": "35",
    "stop_loss": "price:2259",
    "take_profit": "price:2805",
}


def _suggest(
    source: str,
    band: tuple[str, str],
    price: Decimal = _PRICE,
    **config: str,
) -> PlanSuggestion:
    inputs = BotKindInputs(
        {**_OWNER, **config},
        _TERMS,
        MarketView(price, Decimal(160), base_asset="ETH", quote_asset="USDT"),
    )
    return suggest_plan(
        SuggestionRequest(
            source, Decimal(band[0]), Decimal(band[1]), inputs, GridThresholds()
        )
    )


@pytest.mark.parametrize(
    ("source", "band"),
    [("ATR", ("2227.92", "2515.54")), ("Bollinger", ("2370", "2825.29"))],
)
def test_the_owners_plan_has_no_blocking_verdict_from_either_source(
    source: str, band: tuple[str, str]
) -> None:
    suggestion = _suggest(source, band)

    assert suggestion.blocking == ()
    assert suggestion.lower <= _PRICE <= suggestion.upper
    assert {move.key for move in suggestion.moves} == {"stop_loss", "take_profit"}


def test_an_exit_outside_the_new_range_moves_to_the_middle_of_the_advised_distance() -> (
    None
):
    suggestion = _suggest("ATR", ("2227.92", "2515.54"))

    # 5.5% (the middle of 3%–8%) beyond each limit, on the tick.
    assert suggestion.exits == {
        "stop_loss": "price:2105.38",
        "take_profit": "price:2653.89",
    }
    stop = suggestion.moves[0]
    assert (stop.old, stop.new) == (Decimal(2259), Decimal("2105.38"))
    assert "2259" in suggestion.panel_line and "2105.38" in suggestion.panel_line
    assert "stop loss" in suggestion.panel_line
    assert "take profit" in suggestion.panel_line


@pytest.mark.parametrize(
    ("band", "price"),
    [
        (("2370", "2825.29"), _PRICE),  # the band is above the price
        (("1900", "2300"), _PRICE),  # the band is below the price
    ],
)
def test_a_band_that_misses_the_price_is_recentred_at_the_same_width(
    band: tuple[str, str], price: Decimal
) -> None:
    suggestion = _suggest("Bollinger", band, price)

    assert suggestion.lower <= price <= suggestion.upper
    width = Decimal(band[1]) - Decimal(band[0])
    assert abs((suggestion.upper - suggestion.lower) - width) <= Decimal("0.02")
    assert "recentred" in suggestion.range_note
    assert "Bollinger" in suggestion.range_note
    assert suggestion.blocking == ()


def test_a_band_that_holds_the_price_is_written_as_it_is() -> None:
    suggestion = _suggest("ATR", ("2227.92", "2515.54"))

    assert (suggestion.lower, suggestion.upper) == (
        Decimal("2227.92"),
        Decimal("2515.54"),
    )
    assert suggestion.range_note == ""


def test_an_exit_that_is_off_stays_off_and_a_percentage_follows_its_edge() -> None:
    suggestion = _suggest(
        "ATR", ("2227.92", "2515.54"), stop_loss="off", take_profit="percent:5"
    )

    assert suggestion.exits == {}
    assert suggestion.moves == ()
    assert suggestion.panel_line == ""
    assert suggestion.blocking == ()


def test_an_exit_already_at_an_advised_distance_is_not_touched() -> None:
    # 4% below 2227.92 is 2138.80; 6% above 2515.54 is 2666.47.
    suggestion = _suggest(
        "ATR",
        ("2227.92", "2515.54"),
        stop_loss="price:2138.80",
        take_profit="price:2666.47",
    )

    assert suggestion.exits == {}


def test_a_blocking_check_the_suggestion_cannot_clear_is_named() -> None:
    suggestion = _suggest("ATR", ("2227.92", "2515.54"), capital_quote="3")

    assert suggestion.blocking
