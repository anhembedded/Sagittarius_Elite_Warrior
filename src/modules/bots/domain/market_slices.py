"""`EPIC-029E` — a market order split under the per-order cap (ADR D21, §3.4).

Every market order a bot sends is at most `max_notional_per_order`: the opening
buy, a stop-loss or take-profit exit, and Stop with *sell base*. The cap is
trading's configuration (`trading.max_notional_per_order_usdt`), read when the
order is made, never a literal here.

  · `quote_slices` — a quote amount (the opening buy) as ⌈quote / cap⌉ slices,
    each at most the cap, to the quote's eighth decimal.
  · `base_slices` — a base quantity (an exit) as slices whose value at `price`
    is at most the cap, each a whole number of steps so no slice exceeds it
    after rounding. A remainder below one step is not a slice: the exchange
    would refuse it, and the bot reports it as unsold instead of sending it.

**Even, never greedy.** Binance refuses an order worth less than the symbol's
NOTIONAL minimum. Cut greedily, 500.01 USDT at a 500 cap is 500 and a 0.01
tail the exchange refuses, halting the bot mid-exit. Cut evenly, the slices
differ by one unit and, when there are two or more, each is worth at least
half the cap less one unit, which the configuration keeps far above any
minimum.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)

_ROUNDING = OrderQuantityRoundingPolicy()
_ZERO = Decimal(0)
#: The finest quote amount a market order is sized in (`quoteOrderQty`).
QUOTE_UNIT = Decimal("0.00000001")


def quote_slices(quote: Decimal, cap: Decimal) -> tuple[Decimal, ...]:
    """`quote` split evenly into ⌈quote / cap⌉ slices of at most `cap`."""
    _require_positive(cap)
    most = int(cap / QUOTE_UNIT)
    if most < 1:
        raise ValueError(f"The per-order cap {cap} is below one quote unit")
    units = int(quote / QUOTE_UNIT)
    return tuple(n * QUOTE_UNIT for n in _even(units, most))


def base_slices(
    quantity: Decimal, price: Decimal, cap: Decimal, step_size: Decimal
) -> tuple[Decimal, ...]:
    """`quantity` split evenly into slices worth at most `cap` at `price`."""
    _require_positive(cap)
    per_slice = _ROUNDING.round_quantity_down(cap / price, step_size)
    if per_slice <= 0:
        raise ValueError(f"One step of base is worth more than the cap {cap}")
    units = int(_ROUNDING.round_quantity_down(quantity, step_size) / step_size)
    return tuple(n * step_size for n in _even(units, int(per_slice / step_size)))


def _even(units: int, most: int) -> tuple[int, ...]:
    """`units` in ⌈units / most⌉ parts that differ by at most one, largest
    first: none exceeds `most`, and with two or more parts each is at least
    half of it, less one."""
    if units <= 0:
        return ()
    count = -(-units // most)
    size, extra = divmod(units, count)
    return tuple(size + 1 if index < extra else size for index in range(count))


def _require_positive(cap: Decimal) -> None:
    if cap <= _ZERO:
        raise ValueError(f"The per-order cap must be positive, got {cap}")
