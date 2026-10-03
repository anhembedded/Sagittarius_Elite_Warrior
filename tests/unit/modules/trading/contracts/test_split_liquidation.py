"""`EPIC-029` ADR D6 r2 — one asset's liquidation, split per bot."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holdings_close_policy import (
    LiquidationPart,
    split_liquidation,
)

_STEP = Decimal("0.001")


def test_each_bot_takes_up_to_its_inventory_in_order() -> None:
    parts = split_liquidation(
        Decimal("0.5"), [("a", Decimal("0.2")), ("b", Decimal("0.1"))], _STEP
    )
    assert parts == (
        LiquidationPart("a", Decimal("0.2")),
        LiquidationPart("b", Decimal("0.1")),
        LiquidationPart(None, Decimal("0.2")),
    )


def test_a_share_is_floored_to_the_lot_step_and_the_rest_is_untagged() -> None:
    """0.2005 floors to 0.200 and the rest is untagged. Emergency Stop hands
    in a quantity already floored to the step, so there the remainder is a
    whole number of steps; this shows the share's own flooring."""
    parts = split_liquidation(Decimal("0.2005"), [("a", Decimal("0.2005"))], _STEP)
    assert parts == (
        LiquidationPart("a", Decimal("0.200")),
        LiquidationPart(None, Decimal("0.0005")),
    )


def test_a_bot_never_takes_more_than_there_is() -> None:
    parts = split_liquidation(
        Decimal("0.1"), [("a", Decimal("0.2")), ("b", Decimal("0.2"))], _STEP
    )
    assert parts == (LiquidationPart("a", Decimal("0.1")),)


def test_nothing_to_sell_is_no_part() -> None:
    assert split_liquidation(Decimal(0), [("a", Decimal(1))], _STEP) == ()
