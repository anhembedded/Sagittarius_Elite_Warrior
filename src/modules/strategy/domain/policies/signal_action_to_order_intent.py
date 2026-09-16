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

@par This file is `strategy`'s, and is sitting in `trading`
The pair it returns is trading's own (`contracts/order_intent.py`); the
mapping *from* a `SignalAction` is the Customer/Supplier bridge HLD §02 calls
*"strategy only (plus trading through the bridge)"*, and `strategy` is the
customer. Measured before splitting the file: `order_intent_for()` has **two**
callers, `presentation/cli/trade_once_cmd.py` and
`application/services/live_trading_coordinator.py`, and **neither is inside
`modules/trading`** — nothing in this module calls it. It moves to
`modules/strategy/` with those callers in Phase 2 (`EPIC-025C`), which is what
lets `trading` stop naming `SignalAction` at all; the done-when of that phase
is that `trading` imports nothing from `strategy`, not even its contracts.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_intent import (
    OrderIntent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

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
