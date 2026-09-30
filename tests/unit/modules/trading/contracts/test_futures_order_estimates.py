"""`EPIC-028G` — a Futures order's cost and maximum, by Binance's rules.

@details The oracle is Binance's cost FAQ, transcribed here on its own
(`_binance_cost`) rather than shared with the code under test, plus the
FAQ's worked BTC short. The maximum is then held to what the exchange
checks: its cost and fee fit the balance, its notional fits the headroom,
and one more step breaks one of the two. The first version of this module
failed exactly this for the PR #300 review's cases (a market order at 1× and
2×, a long priced above the mark, a cap past the bracket); they are the
parameters below.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_order_estimates import (
    FuturesOrderTerms,
    assuming_price,
    futures_max_quantity,
    futures_order_cost,
    futures_order_fee,
    open_loss,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

_BUY = OrderSide.BUY
_SELL = OrderSide.SELL
_CENT = Decimal("0.01")
_STEP = Decimal("0.001")
_UNCAPPED = Decimal(10) ** 12


def _terms(
    side: OrderSide,
    order_price: str | None,
    *,
    last: str = "100",
    mark: str = "100",
    leverage: int = 10,
    headroom: Decimal = _UNCAPPED,
) -> FuturesOrderTerms:
    return FuturesOrderTerms(
        side=side,
        order_price=None if order_price is None else Decimal(order_price),
        last_price=Decimal(last),
        mark_price=Decimal(mark),
        leverage=leverage,
        fee_rate=Decimal("0.0005"),
        notional_headroom=headroom,
    )


def _binance_cost(quantity: Decimal, terms: FuturesOrderTerms) -> Decimal:
    """Binance's FAQ, word for word: IM at the assuming price + open loss."""
    buffered = terms.last_price * Decimal("1.0015")
    if terms.order_price is None:
        assumed, loss = buffered, Decimal(0)
    else:
        if terms.side is _BUY:
            assumed = terms.order_price
            direction = 1
        else:
            assumed = max(buffered, terms.mark_price, terms.order_price)
            direction = -1
        loss = quantity * abs(
            min(Decimal(0), direction * (terms.mark_price - terms.order_price))
        )
    return quantity * assumed / terms.leverage + loss


def test_the_same_order_as_a_limit_long_costs_only_its_initial_margin() -> None:
    # Derived from the FAQ's short below, not a FAQ figure: a long at
    # 9 253.30 is below the mark, so no open loss; 9 253.30 ÷ 20 = 462.665.
    terms = _terms(_BUY, "9253.30", last="9258.99", mark="9259.84", leverage=20)

    cost = futures_order_cost(Decimal(1), terms)

    assert cost.quantize(_CENT, ROUND_HALF_UP) == Decimal("462.67")
    assert open_loss(Decimal(1), terms) == 0


def test_binances_worked_limit_short_adds_the_open_loss() -> None:
    # The FAQ's worked example: BTC at 20×, a short of one contract at
    # 9 253.30, last 9 258.99, mark 9 259.84 → initial margin 463.64, open
    # loss 6.54, cost 470.18.
    terms = _terms(_SELL, "9253.30", last="9258.99", mark="9259.84", leverage=20)

    assert open_loss(Decimal(1), terms) == Decimal("6.54")
    assert futures_order_cost(Decimal(1), terms).quantize(_CENT) == Decimal("470.18")


@pytest.mark.parametrize("side", [_BUY, _SELL])
def test_a_market_order_is_margined_at_the_buffered_last_price(
    side: OrderSide,
) -> None:
    terms = _terms(side, None, last="100", mark="120")

    assert assuming_price(terms) == Decimal("100.15")
    assert open_loss(Decimal(5), terms) == 0


def test_a_limit_long_is_margined_at_its_own_price() -> None:
    assert assuming_price(_terms(_BUY, "95", last="100", mark="120")) == 95


@pytest.mark.parametrize(
    ("order_price", "last", "mark", "expected"),
    [
        ("100", "100", "100", "100.15"),  # the buffered last is highest
        ("100", "100", "101", "101"),  # the mark is highest
        ("105", "100", "101", "105"),  # the order's price is highest
    ],
)
def test_a_limit_short_is_margined_at_the_highest_of_the_three(
    order_price: str, last: str, mark: str, expected: str
) -> None:
    terms = _terms(_SELL, order_price, last=last, mark=mark)

    assert assuming_price(terms) == Decimal(expected)


@pytest.mark.parametrize(
    ("side", "order_price", "mark", "loss_per_unit"),
    [
        (_BUY, "100", "98", "2"),  # a long above the mark opens at a loss
        (_BUY, "98", "100", "0"),
        (_SELL, "98", "100", "2"),  # a short below the mark opens at a loss
        (_SELL, "100", "98", "0"),
    ],
)
def test_the_open_loss_is_counted_only_when_the_price_is_against_the_mark(
    side: OrderSide, order_price: str, mark: str, loss_per_unit: str
) -> None:
    terms = _terms(side, order_price, mark=mark)

    assert open_loss(Decimal(3), terms) == 3 * Decimal(loss_per_unit)


def test_the_fee_is_charged_at_the_assuming_price() -> None:
    terms = _terms(_BUY, None, last="100")

    assert futures_order_fee(Decimal(10), terms) == Decimal(10) * Decimal(
        "100.15"
    ) * Decimal("0.0005")


@pytest.mark.parametrize(
    ("available", "terms"),
    [
        (Decimal(1000), _terms(_BUY, None, leverage=1)),
        (Decimal(1000), _terms(_BUY, None, leverage=2)),
        (Decimal(1000), _terms(_SELL, None, leverage=5)),
        (Decimal(1000), _terms(_BUY, "100", mark="98", leverage=10)),
        (Decimal(1000), _terms(_SELL, "98", mark="100", leverage=10)),
        (Decimal(10000), _terms(_BUY, "40000", mark="40000", leverage=125)),
        (
            Decimal(10000),
            _terms(_BUY, "40000", mark="40000", leverage=125, headroom=Decimal(50000)),
        ),
        # The cap is measured at the mark when a long is priced below it,
        (
            Decimal(10000),
            _terms(_BUY, "95", mark="100", leverage=125, headroom=Decimal(5000)),
        ),
        # and at the buffered last when a market order is margined above it.
        (
            Decimal(10000),
            _terms(_BUY, None, mark="100", leverage=125, headroom=Decimal(5000)),
        ),
        (Decimal("48977.9423709833"), _terms(_SELL, "53807.3", leverage=75)),
    ],
)
def test_the_maximum_is_one_binance_accepts_and_one_more_step_is_not(
    available: Decimal, terms: FuturesOrderTerms
) -> None:
    def accepted(quantity: Decimal) -> bool:
        fee = futures_order_fee(quantity, terms)
        notional = quantity * max(assuming_price(terms), terms.mark_price)
        return (
            _binance_cost(quantity, terms) + fee <= available
            and notional <= terms.notional_headroom
        )

    maximum = futures_max_quantity(available, terms, _STEP)

    assert maximum % _STEP == 0
    assert accepted(maximum)
    assert not accepted(maximum + _STEP)


def test_the_notional_headroom_caps_the_maximum_below_what_the_balance_pays() -> None:
    # 10 000 at 125× would pay for about 31 BTC; the bracket leaves 50 000 of
    # notional, which is 1.25 BTC at 40 000.
    terms = _terms(_BUY, "40000", mark="40000", leverage=125, headroom=Decimal(50000))

    assert futures_max_quantity(Decimal(10000), terms, _STEP) == Decimal("1.25")


def test_no_headroom_means_no_order() -> None:
    terms = _terms(_BUY, "100", headroom=Decimal(0))

    assert futures_max_quantity(Decimal(10000), terms, _STEP) == 0


@pytest.mark.parametrize("field", ["order_price", "last_price", "mark_price"])
@pytest.mark.parametrize("bad", [Decimal(0), Decimal(-1), Decimal("NaN")])
def test_a_price_that_is_not_positive_is_refused(field: str, bad: Decimal) -> None:
    with pytest.raises(ValueError, match=field):
        replace(_terms(_BUY, "100"), **{field: bad})


@pytest.mark.parametrize("field", ["fee_rate", "notional_headroom"])
@pytest.mark.parametrize("bad", [Decimal(-1), Decimal("Infinity")])
def test_a_rate_or_headroom_that_is_not_a_real_non_negative_number_is_refused(
    field: str, bad: Decimal
) -> None:
    with pytest.raises(ValueError, match=field):
        replace(_terms(_BUY, "100"), **{field: bad})


def test_a_leverage_below_one_is_refused() -> None:
    with pytest.raises(ValueError, match="leverage"):
        replace(_terms(_BUY, "100"), leverage=0)
