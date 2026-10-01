"""`EPIC-028H` — what one side of the order panel shows, and the first thing
that stops it from submitting.

@details The maximum is `EPIC-028G`'s estimate (`spot_max_buy_quantity`),
so these tests pin that the panel uses it at the right price and step, not
the estimate's arithmetic again. `EPIC-028O` adds the app's notional limit
on every maximum, the quote-sized market buy and the stop-limit's stop."""

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

from .order_entry_fixtures import STEP, TAKER, spot_context

_BUY = EntrySide.BUY
_SELL = EntrySide.SELL
_LIMIT = OrderType.LIMIT
_MARKET = OrderType.MARKET
_STOP = OrderType.STOP_LIMIT


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


def test_a_market_sell_is_sized_at_the_last_price_and_the_market_step() -> None:
    context = spot_context(free_base=Decimal("0.509"))

    figures = spot_side_figures(
        _SELL, _MARKET, _entry("1", "0.5"), context, Decimal(250)
    )

    assert figures.price == 250
    assert figures.max_quantity == Decimal("0.50")
    assert figures.total == 125
    assert not figures.sized_by_quote
    assert figures.can_submit


def test_a_market_buy_is_sized_by_the_quote_it_spends() -> None:
    figures = spot_side_figures(
        _BUY, _MARKET, SideInput(total=Decimal(250)), spot_context(), Decimal(300)
    )

    assert figures.sized_by_quote
    assert figures.price == 300
    assert figures.max_total == 1000
    # What the whole balance buys at the last price, on the market step.
    assert figures.max_quantity == Decimal("3.33")
    assert figures.total == 250
    assert figures.fee == Decimal(250) * TAKER
    assert figures.can_submit


def test_a_quote_buy_can_spend_its_balance_floored_to_a_cent() -> None:
    context = spot_context(available_quote=Decimal("1000.019"))

    figures = spot_side_figures(_BUY, _MARKET, SideInput(), context, Decimal(300))

    assert figures.max_total == Decimal("1000.01")
    at_max = spot_side_figures(
        _BUY, _MARKET, SideInput(total=Decimal("1000.01")), context, Decimal(300)
    )
    over = spot_side_figures(
        _BUY, _MARKET, SideInput(total=Decimal("1000.02")), context, Decimal(300)
    )
    assert at_max.can_submit
    assert over.problem == "Not enough USDT: at most 1000.01."


def test_a_quote_buy_with_an_unknown_balance_shows_no_maximum() -> None:
    context = spot_context(available_quote=None)

    figures = spot_side_figures(_BUY, _MARKET, SideInput(), context, Decimal(300))

    assert figures.max_total is None
    assert figures.max_quantity is None


# -- the app's per-order notional limit ------------------------------------- #


def test_a_limit_buy_maximum_is_capped_by_the_notional_limit() -> None:
    context = spot_context(notional_limit=Decimal(500))

    figures = spot_side_figures(_BUY, _LIMIT, _entry("100"), context, None)

    # The balance would buy 9.99; the limit allows 5.
    assert figures.max_quantity == 5


def test_a_sell_maximum_is_capped_by_the_notional_limit() -> None:
    context = spot_context(free_base=Decimal(10), notional_limit=Decimal(500))

    figures = spot_side_figures(_SELL, _LIMIT, _entry("300"), context, None)

    # 500 / 300 = 1.666..., floored to the lot step.
    assert figures.max_quantity == Decimal("1.666")


def test_a_maximum_under_the_notional_limit_is_left_alone() -> None:
    context = spot_context(notional_limit=Decimal(100_000))

    figures = spot_side_figures(_BUY, _LIMIT, _entry("100"), context, None)

    assert figures.max_quantity == spot_max_buy_quantity(
        Decimal(1000), SpotOrderTerms(Decimal(100), TAKER), STEP
    )


def test_a_quote_buy_maximum_is_capped_by_the_notional_limit() -> None:
    context = spot_context(notional_limit=Decimal(500))

    figures = spot_side_figures(_BUY, _MARKET, SideInput(), context, Decimal(250))

    assert figures.max_total == 500
    assert figures.max_quantity == 2


@pytest.mark.parametrize(
    ("side", "order_type", "entry", "last"),
    [
        (_BUY, _LIMIT, SideInput(Decimal(100), Decimal("5.001")), None),
        (_SELL, _LIMIT, SideInput(Decimal(1000), Decimal("0.501")), None),
        (_BUY, _MARKET, SideInput(total=Decimal("500.01")), Decimal(250)),
    ],
)
def test_an_order_over_the_notional_limit_says_so(
    side, order_type, entry, last
) -> None:
    context = spot_context(free_base=Decimal(10), notional_limit=Decimal(500))

    figures = spot_side_figures(side, order_type, entry, context, last)

    assert figures.problem == (
        "The order is worth more than the app's limit of 500 USDT per order."
    )


def test_an_order_at_the_notional_limit_submits() -> None:
    context = spot_context(notional_limit=Decimal(500))

    figures = spot_side_figures(
        _BUY, _LIMIT, SideInput(Decimal(100), Decimal(5)), context, None
    )

    assert figures.can_submit


# -- stop-limit ------------------------------------------------------------- #


def _stop(price: str, quantity: str, stop: str | None) -> SideInput:
    return SideInput(
        price=Decimal(price),
        quantity=Decimal(quantity),
        stop_price=None if stop is None else Decimal(stop),
    )


@pytest.mark.parametrize(
    ("side", "entry", "last"),
    [
        (_BUY, _stop("110", "1", "105"), Decimal(100)),
        (_SELL, _stop("90", "0.2", "95"), Decimal(100)),
    ],
)
def test_a_stop_on_the_waiting_side_is_a_limit_order_at_its_price(
    side, entry, last
) -> None:
    figures = spot_side_figures(side, _STOP, entry, spot_context(), last)

    assert figures.price == entry.price
    assert figures.total == entry.price * entry.quantity
    assert figures.can_submit


@pytest.mark.parametrize(
    ("side", "entry", "last", "problem"),
    [
        (_BUY, _stop("110", "1", None), Decimal(100), "Enter a stop price."),
        (_BUY, _stop("110", "1", "0"), Decimal(100), "Enter a stop price."),
        (_BUY, _stop("110", "1", "105"), None, "No market price yet. Wait for live data."),
        (_BUY, _stop("110", "1", "95"), Decimal(100), "A buy stop must be above the last price (100); this one would trigger at once."),
        (_BUY, _stop("110", "1", "100"), Decimal(100), "A buy stop must be above the last price (100); this one would trigger at once."),
        (_SELL, _stop("90", "0.2", "105"), Decimal(100), "A sell stop must be below the last price (100); this one would trigger at once."),
    ],
)  # fmt: skip
def test_a_stop_limit_names_its_stop_problem_first(side, entry, last, problem) -> None:
    # A zero-balance account: the stop's problem comes before the balance's.
    context = spot_context(available_quote=Decimal(0))

    figures = spot_side_figures(side, _STOP, entry, context, last)

    assert figures.problem == problem


def test_a_stop_limit_with_a_good_stop_still_checks_the_limit_order() -> None:
    figures = spot_side_figures(
        _BUY, _STOP, _stop("110", "100", "105"), spot_context(), Decimal(100)
    )

    assert figures.problem is not None and "Not enough USDT" in figures.problem


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
        (_SELL, _MARKET, _entry(None, "0.1"), None, spot_context(), "No market price yet"),
        (_BUY, _MARKET, SideInput(), Decimal(100), spot_context(), "Enter a total."),
        (_BUY, _MARKET, SideInput(total=Decimal(0)), Decimal(100), spot_context(), "Enter a total."),
        (_BUY, _MARKET, SideInput(total=Decimal("9.99")), Decimal(100), spot_context(), "minimum of 10 USDT"),
        (_BUY, _MARKET, SideInput(total=Decimal(20)), Decimal(100), spot_context(available_quote=None), "could not be read"),
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


# -- the price that is sent ------------------------------------------------- #


def test_figures_are_judged_at_the_tick_rounded_price_a_sell_up() -> None:
    # PR #305 review: a sell at 125.031 is sent at 125.04 (the preview
    # rounds a sell up), so 3.999 would be worth 500.035, over the limit.
    context = spot_context(free_base=Decimal(10), notional_limit=Decimal(500))

    at_max = spot_side_figures(_SELL, _LIMIT, _entry("125.031"), context, None)
    over = spot_side_figures(_SELL, _LIMIT, _entry("125.031", "3.999"), context, None)

    assert at_max.price == Decimal("125.04")
    assert at_max.max_quantity == Decimal("3.998")
    assert over.problem == (
        "The order is worth more than the app's limit of 500 USDT per order."
    )


def test_a_buy_is_judged_at_its_price_rounded_down() -> None:
    # 0.1 at 100.009 reads as 10.0009, but is sent at 100.00: exactly 10.
    figures = spot_side_figures(
        _BUY, _LIMIT, _entry("100.009", "0.1"), spot_context(), None
    )

    assert figures.price == 100
    assert figures.total == 10
    assert figures.can_submit
