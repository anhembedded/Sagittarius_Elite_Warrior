from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.domain.trading.policies.signal_action_to_order_intent import (
    order_intent_for,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)


def test_buy_opens_long_not_reduce_only() -> None:
    intent = order_intent_for(SignalAction.BUY)
    assert intent.side is OrderSide.BUY
    assert intent.reduce_only is False


def test_sell_closes_long_reduce_only() -> None:
    intent = order_intent_for(SignalAction.SELL)
    assert intent.side is OrderSide.SELL
    assert intent.reduce_only is True


def test_short_opens_short_not_reduce_only() -> None:
    """This epic's own business-acceptance requirement (`EPIC-021G` §4):
    a SHORT signal must generate a SELL order that OPENS a short, not one
    that looks like closing a long — `reduce_only` is what tells them
    apart, since Binance One-way mode has no separate SHORT order side."""
    intent = order_intent_for(SignalAction.SHORT)
    assert intent.side is OrderSide.SELL
    assert intent.reduce_only is False


def test_cover_closes_short_reduce_only() -> None:
    intent = order_intent_for(SignalAction.COVER)
    assert intent.side is OrderSide.BUY
    assert intent.reduce_only is True


def test_sell_and_short_share_the_same_side_but_differ_on_reduce_only() -> None:
    """The exact ambiguity this module exists to resolve."""
    sell = order_intent_for(SignalAction.SELL)
    short = order_intent_for(SignalAction.SHORT)
    assert sell.side is short.side
    assert sell.reduce_only != short.reduce_only


def test_hold_is_not_a_valid_input() -> None:
    with pytest.raises(KeyError):
        order_intent_for(SignalAction.HOLD)
