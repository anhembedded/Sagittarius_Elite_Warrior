"""`EPIC-028I` — the orders that protect a position once its entry fills:
a take-profit and a stop-loss, each closing at market when its trigger
trades.

@details **The side is the one thing that must not be wrong.** Both orders
sit on the side opposite the entry (a long is protected by sells), are
`reduce_only` so the exchange refuses them if they would open a position,
and carry `OrderPurpose.PROTECTIVE` so the app's own limits pass them.
Built here, without Qt, so the side logic is tested on its own; `EPIC-026K`
builds a strategy's protective orders with the same function.

The take-profit is `TAKE_PROFIT_MARKET` and the stop-loss `STOP_MARKET`,
both sent through Binance's Algo Order API (`EPIC-028R`). Each is judged
against `last_price` before it is sent (`check_trigger_side`): a stop-loss
the market has already crossed is refused, not sent to fill at once.

Plausible extensions, each one function here:
- a partial take-profit (several `take_profit` levels, each a part of the
  quantity);
- `closePosition=true` instead of a quantity, so a later fill on the same
  side is covered too;
- a trailing stop-loss.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.protective_levels import (
    ProtectiveLevels,
)

_OPPOSITE = {OrderSide.BUY: OrderSide.SELL, OrderSide.SELL: OrderSide.BUY}


def protection_problem(
    entry_side: OrderSide, entry_price: Decimal, levels: ProtectiveLevels
) -> str | None:
    """@return Why `levels` cannot protect an entry on `entry_side` at
    `entry_price`, or `None`: a long's take-profit sits above the entry and
    its stop-loss below; a short's the other way round."""
    is_long = entry_side is OrderSide.BUY
    tp, sl = levels.take_profit, levels.stop_loss
    if tp is not None and (tp <= entry_price if is_long else tp >= entry_price):
        where = "above" if is_long else "below"
        return f"The take-profit must be {where} the entry price ({entry_price})."
    if sl is not None and (sl >= entry_price if is_long else sl <= entry_price):
        where = "below" if is_long else "above"
        return f"The stop-loss must be {where} the entry price ({entry_price})."
    return None


def protective_orders_for(
    symbol: str,
    entry_side: OrderSide,
    quantity: Decimal,
    levels: ProtectiveLevels,
    last_price: Decimal,
) -> tuple[OrderRequest, ...]:
    """@return The take-profit then the stop-loss that `levels` names, for
    `quantity` of a position opened on `entry_side`: opposite side,
    reduce-only, protective.
    @param last_price What each trigger is judged against before sending:
    the entry's fill price, or a later last price."""
    if quantity <= 0:
        raise ValueError(f"quantity must be positive, got {quantity}")
    side = _OPPOSITE[entry_side]
    wanted = (
        (OrderType.TAKE_PROFIT_MARKET, levels.take_profit),
        (OrderType.STOP_MARKET, levels.stop_loss),
    )
    return tuple(
        OrderRequest(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            reference_price=trigger,
            reduce_only=True,
            stop_price=trigger,
            last_price=last_price,
            purpose=OrderPurpose.PROTECTIVE,
        )
        for order_type, trigger in wanted
        if trigger is not None
    )
