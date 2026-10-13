"""`EPIC-039D` — how far a Futures owner's position could reach, and whether
an order lets it reach further than its budget allows.

@details Worst case, in One-way mode with the owner's orders filling in the
order least kind to it: every open BUY and none of the SELLs (long case), or
every open SELL and none of the BUYs (short case). The position a case ends
in is valued at the order's own unit price (`order_notional / quantity`),
the price the owner is about to trade at; it is a limit price for a ladder,
the preview's estimate for a market order.

An order is refused for exposure only when it is **the one that raises** the
worst case above the ceiling. One that leaves the worst case where it was (a
reduce-only exit, a sell that only closes) passes even when the owner is
already over, so a position can always be reduced.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    FuturesLimits,
    PositionExposure,
)

_ZERO = Decimal(0)


def worst_case_quantity(held: Decimal, buys: Decimal, sells: Decimal) -> Decimal:
    """@brief The largest absolute position `held` could reach if `buys` more
    were bought and none sold, or `sells` sold and none bought."""
    return max(abs(held + buys), abs(held - sells))


def notional_within_limits(
    exposure: PositionExposure,
    limits: FuturesLimits,
    side: OrderSide,
    quantity: Decimal,
    order_notional: Decimal,
) -> bool:
    """@brief Whether the worst-case position, with this order, is worth no
    more than `limits.max_position_notional`, or is no worse than without it."""
    return _within(
        exposure, side, quantity, order_notional, limits.max_position_notional
    )


def margin_within_limits(
    exposure: PositionExposure,
    limits: FuturesLimits,
    side: OrderSide,
    quantity: Decimal,
    order_notional: Decimal,
) -> bool:
    """@brief Whether the initial margin of the worst-case position, with
    this order, is at most `limits.committed_margin`, or is no worse than
    without it."""
    ceiling = limits.committed_margin * limits.leverage
    return _within(exposure, side, quantity, order_notional, ceiling)


def _within(
    exposure: PositionExposure,
    side: OrderSide,
    quantity: Decimal,
    order_notional: Decimal,
    notional_ceiling: Decimal,
) -> bool:
    held = exposure.position.quantity
    buys, sells = exposure.open_adding_buy_quantity, exposure.open_adding_sell_quantity
    adds = _ZERO if exposure.order_reduce_only else quantity
    before = worst_case_quantity(held, buys, sells)
    after = worst_case_quantity(
        held,
        buys + (adds if side is OrderSide.BUY else _ZERO),
        sells + (adds if side is OrderSide.SELL else _ZERO),
    )
    unit_price = order_notional / quantity if quantity > 0 else _ZERO
    return after * unit_price <= notional_ceiling or after <= before
