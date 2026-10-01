"""`EPIC-028H` — what one side of the order panel shows, and the first thing
that stops it from submitting.

@details The maximum is `EPIC-028G`'s estimate (`spot_max_buy_quantity`),
so these tests pin that the panel uses it at the right price and step, not
the estimate's arithmetic again."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_order_estimates import (
    SpotOrderTerms,
    spot_max_buy_quantity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
    SideInput,
    percent_of_max,
    quantity_at_percent,
    spot_side_figures,
)

from .order_entry_fixtures import MARKET_STEP, STEP, TAKER, spot_context

_BUY = EntrySide.BUY
_SELL = EntrySide.SELL
_LIMIT = OrderType.LIMIT
_MARKET = OrderType.MARKET


def _entry(price: str | None = None, quantity: str | None = None) -> SideInput:
    return SideInput(
        price=None if price is None else Decimal(price),
        quantity=None if quantity is None else Decimal(quantity),
    )


def test_a_limit_buy_is_sized_at_its_own_price_and_the_lot_step() -> None:
    figures = spot_side_figures(
        _BUY, _LIMIT, _entry("100", "2"), spot_context(), Decimal(999)
    )

    assert figures.price == 100
    assert figures.available == 1000
    assert figures.available_asset == "USDT"
    assert figures.max_quantity == spot_max_buy_quantity(
        Decimal(1000), SpotOrderTerms(Decimal(100), TAKER), STEP
    )
    assert figures.total == 200
    assert figures.fee == Decimal(200) * TAKER
    assert figures.can_submit


def test_a_market_buy_is_sized_at_the_last_price_and_the_market_step() -> None:
    figures = spot_side_figures(
        _BUY, _MARKET, _entry("1", "1"), spot_context(), Decimal(250)
    )

    assert figures.price == 250
    assert figures.max_quantity == spot_max_buy_quantity(
        Decimal(1000), SpotOrderTerms(Decimal(250), TAKER), MARKET_STEP
    )
    assert figures.total == 250


def test_a_sell_can_sell_its_free_base_floored_to_the_step() -> None:
    context = spot_context(free_base=Decimal("0.5009"))

    figures = spot_side_figures(_SELL, _LIMIT, _entry("100"), context, None)

    assert figures.available == Decimal("0.5009")
    assert figures.available_asset == "BTC"
    assert figures.max_quantity == Decimal("0.500")


@pytest.mark.parametrize(
    ("side", "order_type", "entry", "last", "context", "problem"),
    [
        (_SELL, _LIMIT, _entry("100", "1"), None, spot_context(free_base=Decimal(0)), "No BTC to sell."),
        (_SELL, _LIMIT, _entry("100", "1"), None, spot_context(free_base=None), "No BTC to sell."),
        (_BUY, _LIMIT, _entry(None, "1"), None, spot_context(), "Enter a price."),
        (_BUY, _LIMIT, _entry("0", "1"), None, spot_context(), "Enter a price."),
        (_BUY, _MARKET, _entry(None, "1"), None, spot_context(), "No market price yet"),
        (_BUY, _LIMIT, _entry("100"), None, spot_context(), "Enter an amount."),
        (_BUY, _LIMIT, _entry("100", "0.0009"), None, spot_context(), "below one lot of 0.001"),
        (_BUY, _LIMIT, _entry("100", "0.05"), None, spot_context(), "minimum of 10 USDT"),
        (_BUY, _LIMIT, _entry("100", "1"), None, spot_context(available_quote=None), "could not be read"),
        (_BUY, _LIMIT, _entry("100", "10"), None, spot_context(), "Not enough USDT"),
        (_SELL, _LIMIT, _entry("100", "0.6"), None, spot_context(), "Not enough BTC"),
    ],
)  # fmt: skip
def test_the_first_problem_is_named(
    side, order_type, entry, last, context, problem
) -> None:
    figures = spot_side_figures(side, order_type, entry, context, last)

    assert figures.problem is not None
    assert problem in figures.problem
    assert not figures.can_submit


def test_the_amount_is_judged_after_rounding_to_the_step() -> None:
    # 0.1009 rounds down to 0.100, worth exactly the 10 USDT minimum.
    figures = spot_side_figures(
        _BUY, _LIMIT, _entry("100", "0.1009"), spot_context(), None
    )

    assert figures.can_submit


def test_the_whole_balance_fits_and_one_step_more_does_not() -> None:
    maximum = spot_side_figures(
        _BUY, _LIMIT, _entry("100"), spot_context(), None
    ).max_quantity
    assert maximum is not None

    at_max = spot_side_figures(
        _BUY, _LIMIT, SideInput(Decimal(100), maximum), spot_context(), None
    )
    over = spot_side_figures(
        _BUY, _LIMIT, SideInput(Decimal(100), maximum + STEP), spot_context(), None
    )

    assert at_max.can_submit
    assert over.problem is not None and "Not enough USDT" in over.problem


def test_no_figures_are_invented_without_an_amount_or_a_price() -> None:
    figures = spot_side_figures(_BUY, _LIMIT, _entry(), spot_context(), None)

    assert figures.total is None
    assert figures.fee is None
    assert figures.max_quantity is None


@pytest.mark.parametrize(
    ("percent", "expected"), [(0, "0"), (25, "0.125"), (33, "0.165"), (100, "0.5")]
)
def test_a_slider_percent_is_floored_to_the_step(percent: int, expected: str) -> None:
    assert quantity_at_percent(percent, Decimal("0.5"), STEP) == Decimal(expected)


@pytest.mark.parametrize("percent", [-1, 101])
def test_a_percent_outside_the_slider_is_refused(percent: int) -> None:
    with pytest.raises(ValueError, match="percent"):
        quantity_at_percent(percent, Decimal(1), STEP)


@pytest.mark.parametrize(
    ("quantity", "maximum", "expected"),
    [
        ("0.25", "0.5", 50),
        ("1", "0.5", 100),
        (None, "0.5", 0),
        ("0.25", None, 0),
        ("0.25", "0", 0),
    ],
)
def test_the_slider_follows_a_typed_amount(
    quantity: str | None, maximum: str | None, expected: int
) -> None:
    to_decimal = lambda text: None if text is None else Decimal(text)
    assert percent_of_max(to_decimal(quantity), to_decimal(maximum)) == expected
