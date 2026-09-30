"""`EPIC-028G` — what an order would cost, before it is sent.

@details The desks show *Max*, *Cost* and *Est. fee* beside the order form;
these three pure functions compute them, one set for both venues ("share
what can be shared", ADR D1). Spot is leverage 1, so the same formulas give
Spot's numbers:

- `estimated_fee`: notional × fee rate;
- `order_cost`: notional ÷ leverage + fee. On Futures that is the initial
  margin plus the fee; on Spot, the notional plus the fee;
- `max_order_quantity`: the largest quantity whose cost the available
  balance pays, floored to the lot step, so it never overshoots.

**Deliberately conservative.** A Spot buy is charged its fee in the base
asset it receives, not in the quote it spends, so counting the fee in the
cost understates the Spot maximum by at most one fee. That is the side to
err on: a maximum that is slightly low is still accepted; one that is too
high is rejected by the exchange. The fee rate is the taker rate (a market
order pays it); a maker rebate is never promised in advance, so a negative
rate is refused.

`Decimal` throughout, and every input is checked: NaN, infinity and a
negative (or, for price and leverage, zero) value raise `ValueError`, never
a number that looks exact.

Plausible extensions, each one function here: Binance's "open loss" term in
the Futures cost of a limit order priced through the mark; a reduce-only
maximum from the open position; the cost of a Spot sell in the base asset.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.estimate_inputs import (
    require_not_negative,
    require_positive,
)


@dataclass(frozen=True)
class OrderTerms:
    """The terms an order would be placed on: its price, the symbol's
    leverage (1 on Spot) and the fee rate as a fraction (`0.0005` is
    0.05 %)."""

    price: Decimal
    leverage: int
    fee_rate: Decimal

    def __post_init__(self) -> None:
        require_positive("price", self.price)
        if self.leverage < 1:
            raise ValueError(f"leverage must be 1 or more, got {self.leverage}")
        require_not_negative("fee_rate", self.fee_rate)


def estimated_fee(quantity: Decimal, terms: OrderTerms) -> Decimal:
    """@return The fee an order of `quantity` would pay, in the quote
    asset."""
    require_not_negative("quantity", quantity)
    return quantity * terms.price * terms.fee_rate


def order_cost(quantity: Decimal, terms: OrderTerms) -> Decimal:
    """@return What placing `quantity` takes from the available balance:
    the margin it locks (the whole notional on Spot) plus its fee."""
    require_not_negative("quantity", quantity)
    notional = quantity * terms.price
    return notional / terms.leverage + estimated_fee(quantity, terms)


def max_order_quantity(
    available: Decimal, terms: OrderTerms, step_size: Decimal
) -> Decimal:
    """@return The largest multiple of `step_size` whose `order_cost` does
    not exceed `available`; zero when not even one step fits."""
    require_not_negative("available", available)
    require_positive("step_size", step_size)
    cost_per_unit = terms.price / terms.leverage + terms.price * terms.fee_rate
    steps = (available / cost_per_unit / step_size).to_integral_value(ROUND_FLOOR)
    return steps * step_size
