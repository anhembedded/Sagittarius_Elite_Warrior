"""`EPIC-039D` — one fill moves a signed position: add, reduce, close, flip."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from fractions import Fraction

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    EMPTY_POSITION,
    OwnerPosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.owner_position_policy import (
    PositionFill,
    position_after,
)

BUY, SELL = OrderSide.BUY, OrderSide.SELL


def _fill(side: OrderSide, quantity: str, price: str, fee: str = "0") -> PositionFill:
    return PositionFill(side, Decimal(quantity), Decimal(price), Decimal(fee))


def _replay(*fills: PositionFill) -> OwnerPosition:
    position = EMPTY_POSITION
    for fill in fills:
        position = position_after(position, fill)
    return position


def test_a_long_then_partial_close_then_flip_derives_the_signed_position_and_entry() -> (
    None
):
    opened = _replay(_fill(BUY, "2", "100"), _fill(BUY, "2", "110"))
    assert (opened.quantity, opened.average_entry) == (Decimal(4), Decimal(105))

    reduced = position_after(opened, _fill(SELL, "1", "120"))
    assert (reduced.quantity, reduced.average_entry) == (Decimal(3), Decimal(105))
    assert reduced.realized_pnl == Decimal(15)

    flipped = position_after(reduced, _fill(SELL, "5", "90"))
    assert (flipped.quantity, flipped.average_entry) == (Decimal(-2), Decimal(90))
    assert flipped.realized_pnl == Decimal(15) + 3 * (Decimal(90) - Decimal(105))


def test_a_short_gains_when_the_price_falls_and_a_cover_leaves_the_entry() -> None:
    short = _replay(_fill(SELL, "3", "200"), _fill(BUY, "1", "180"))

    assert (short.quantity, short.average_entry) == (Decimal(-2), Decimal(200))
    assert short.realized_pnl == Decimal(20)


def test_closing_everything_leaves_no_entry_and_no_quantity() -> None:
    flat = _replay(_fill(BUY, "2", "100"), _fill(SELL, "2", "101"))

    assert (flat.quantity, flat.average_entry) == (Decimal(0), None)
    assert flat.realized_pnl == Decimal(2)


def test_fees_in_the_quote_asset_add_up_and_never_touch_the_entry() -> None:
    position = _replay(_fill(BUY, "1", "100", "0.04"), _fill(SELL, "1", "100", "0.04"))

    assert position.fees == Decimal("0.08")
    assert position.realized_pnl == Decimal(0)


def test_a_position_with_a_quantity_but_no_entry_cannot_exist() -> None:
    with pytest.raises(ValueError, match="average entry"):
        OwnerPosition(Decimal(1), None, Decimal(0), Decimal(0))


class _Lots:
    """A naive oracle in a different shape from the policy, in exact fractions:
    a list of lots of one side; a reduce takes the same share from every lot,
    an add appends one."""

    def __init__(self) -> None:
        self.lots: list[tuple[Fraction, Fraction]] = []  # (signed quantity, price)
        self.realized = Fraction(0)

    def apply(self, side: OrderSide, quantity: Fraction, price: Fraction) -> None:
        signed = quantity if side is BUY else -quantity
        held = self.quantity()
        if held == 0 or (held > 0) == (signed > 0):
            self.lots.append((signed, price))
            return
        closing = min(abs(held), quantity)
        entry = self.entry()
        self.realized += closing * ((price - entry) if held > 0 else (entry - price))
        keep = (abs(held) - closing) / abs(held)
        self.lots = [(q * keep, p) for q, p in self.lots] if keep > 0 else []
        left = quantity - closing
        if left > 0:
            self.lots = [(left if signed > 0 else -left, price)]

    def quantity(self) -> Fraction:
        return sum((q for q, _ in self.lots), Fraction(0))

    def entry(self) -> Fraction:
        held = abs(self.quantity())
        return sum((abs(q) * p for q, p in self.lots), Fraction(0)) / held


def _draws(seed: int) -> Callable[[int], int]:
    """A deterministic stream of small integers (a linear congruential generator)."""
    state = seed + 1

    def draw(bound: int) -> int:
        nonlocal state
        state = (state * 1103515245 + 12345) % 2**31
        return (state >> 8) % bound

    return draw


@pytest.mark.parametrize("seed", range(40))
def test_the_position_equals_a_naive_lot_replay_over_random_fills(seed: int) -> None:
    draw = _draws(seed)
    oracle = _Lots()
    position = EMPTY_POSITION
    for _ in range(25):
        side = BUY if draw(2) == 0 else SELL
        quantity = Fraction(1 + draw(9), 4)
        price = Fraction(80 + draw(41))
        oracle.apply(side, quantity, price)
        position = position_after(
            position,
            PositionFill(
                side,
                Decimal(quantity.numerator) / quantity.denominator,
                Decimal(price.numerator),
            ),
        )

        assert Fraction(position.quantity) == oracle.quantity()
        assert abs(Fraction(position.realized_pnl) - oracle.realized) < Fraction(
            1, 10**18
        )
        if oracle.quantity() == 0:
            assert position.average_entry is None
        else:
            assert position.average_entry is not None
            assert abs(Fraction(position.average_entry) - oracle.entry()) < Fraction(
                1, 10**18
            )
