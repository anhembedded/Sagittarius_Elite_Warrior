"""`EPIC-021G` — the exact translation this epic's business-acceptance test
(`EPIC-021G` §4) exists to lock: a strategy's `SignalAction` into the
Binance side/`reduceOnly` pair a live order actually needs.

@details The subtlety `Order Side` alone cannot express: Binance Futures
One-way mode has no "SHORT" order side — `SignalAction.SELL` (closing a
LONG) and `SignalAction.SHORT` (opening a SHORT) are **both** a Binance
`SELL`. What tells them apart is `reduceOnly`: `SELL` must close
(`reduceOnly=True`), `SHORT` must open (`reduceOnly=False`). Get this
backwards and a SHORT signal sends an order the exchange reads as "close
my long" — on a flat or long account it does the wrong thing outright; on
a short account it closes the very position the signal meant to open.
`SignalAction.HOLD` is never passed in — `StrategyEngine` already filters
it before a `Signal` ever reaches this app's live path.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)


@dataclass(frozen=True)
class OrderIntent:
    side: OrderSide
    reduce_only: bool


_INTENT_BY_ACTION: dict[SignalAction, OrderIntent] = {
    SignalAction.BUY: OrderIntent(OrderSide.BUY, reduce_only=False),  # open LONG
    SignalAction.SELL: OrderIntent(OrderSide.SELL, reduce_only=True),  # close LONG
    SignalAction.SHORT: OrderIntent(OrderSide.SELL, reduce_only=False),  # open SHORT
    SignalAction.COVER: OrderIntent(OrderSide.BUY, reduce_only=True),  # close SHORT
}


def order_intent_for(action: SignalAction) -> OrderIntent:
    """@raise KeyError `action` is `SignalAction.HOLD` — never a valid
    input; `StrategyEngine.on_tick()`/`run_batch()` already return `None`
    instead of a HOLD signal, so a caller reaching this function with HOLD
    has a bug upstream, not a case to handle gracefully here.
    """
    return _INTENT_BY_ACTION[action]
