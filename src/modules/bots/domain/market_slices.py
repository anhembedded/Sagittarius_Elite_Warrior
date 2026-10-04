"""`EPIC-029E` — a market order split under the per-order cap (ADR D21, §3.4).

Every market order a bot sends is at most `max_notional_per_order`: the opening
buy, a stop-loss or take-profit exit, and Stop with *sell base*. The cap is
trading's configuration (`trading.max_notional_per_order_usdt`), read when the
order is made, never a literal here.

  · `quote_slices` — a quote amount (the opening buy) as ⌈quote / cap⌉ slices,
    each at most the cap; the last carries the remainder.
  · `base_slices` — a base quantity (an exit) as slices whose value at `price`
    is at most the cap, each rounded **down** to the step so no slice exceeds
    it after rounding. A remainder below one step is not a slice: the exchange
    would refuse it, and the bot reports it as unsold instead of sending it.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)

_ROUNDING = OrderQuantityRoundingPolicy()
_ZERO = Decimal(0)


def quote_slices(quote: Decimal, cap: Decimal) -> tuple[Decimal, ...]:
    """`quote` split into slices of at most `cap`."""
    _require_positive(cap)
    slices: list[Decimal] = []
    remaining = quote
    while remaining > 0:
        piece = min(remaining, cap)
        slices.append(piece)
        remaining -= piece
    return tuple(slices)


def base_slices(
    quantity: Decimal, price: Decimal, cap: Decimal, step_size: Decimal
) -> tuple[Decimal, ...]:
    """`quantity` split into slices worth at most `cap` at `price`."""
    _require_positive(cap)
    per_slice = _ROUNDING.round_quantity_down(cap / price, step_size)
    if per_slice <= 0:
        raise ValueError(f"One step of base is worth more than the cap {cap}")
    slices: list[Decimal] = []
    remaining = _ROUNDING.round_quantity_down(quantity, step_size)
    while remaining > 0:
        piece = min(remaining, per_slice)
        slices.append(piece)
        remaining -= piece
    return tuple(slices)


def _require_positive(cap: Decimal) -> None:
    if cap <= _ZERO:
        raise ValueError(f"The per-order cap must be positive, got {cap}")
