"""`EPIC-028O` — the manual order panels name a crossed stop in words."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderPriceRejection,
    ExecuteOrderStopRejection,
    ExecuteOrderTypeRejection,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.execute_order_block_reason import (
    format_execute_order_block_reason,
)


def test_a_crossed_stop_is_explained_with_the_rule_it_broke() -> None:
    text = format_execute_order_block_reason(
        ExecuteOrderStopRejection.STOP_ON_WRONG_SIDE
    )

    assert "buy stop must be above" in text
    assert "sell stop below" in text


def test_an_order_type_the_venue_cannot_send_is_named() -> None:
    text = format_execute_order_block_reason(
        ExecuteOrderTypeRejection.NOT_SENDABLE_ON_VENUE
    )

    assert "cannot be sent on this venue" in text


def test_a_price_outside_the_band_is_explained_not_coded() -> None:
    """`BUG-147` — the user saw `-1013 Filter failure: PERCENT_PRICE_BY_SIDE`;
    the panel says what is wrong in words."""
    text = format_execute_order_block_reason(
        ExecuteOrderPriceRejection.OUTSIDE_PRICE_BAND
    )

    assert "too far from the market" in text
    assert "1013" not in text
