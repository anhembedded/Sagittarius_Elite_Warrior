"""`EPIC-028G` — what a USD-M Futures order costs and how large it may be,
by Binance's own rules.

@details Binance's cost FAQ ("How to calculate the cost required to open a
position"):
- **Cost = initial margin + open loss.** The fee is not in it;
- **initial margin = assuming price × quantity ÷ leverage**, where the
  assuming price is:
  - a market order: last × (1 + 0.15 %);
  - a limit long: the order's price;
  - a limit short: max(last × (1 + 0.15 %), mark, the order's price);
- **open loss = quantity × |min(0, direction × (mark − order price))|**, with
  direction +1 for a long and −1 for a short.

Its margin FAQ adds the notional cap: **the notional after the order may not
exceed the limit for the leverage**. `FuturesOrderTerms.notional_headroom`
is that limit less what is already open on the symbol, and the caller works
it out from the bracket (`LeverageSetting.max_notional`) and the position.

**What `futures_max_quantity` guarantees.** It sizes an order that opens or
increases a position (a reducing order costs nothing in one-way mode, so this
reads low for one). It sizes against Binance's cost plus the taker fee (the
fee is charged from the same balance at the fill), and against the headroom
at the higher of the assuming and the mark price; the FAQ does not say which
price the cap uses, so this is the conservative choice. Given the balance,
prices and headroom it is handed:
- **a limit order** at the maximum is never refused for margin or notional,
  and the maximum reads at most one fee below Binance's own;
- **a market order**'s open loss is **not modelled**. The FAQ does not say
  what "order price" means for a market order, and a secondary source (a
  Binance developer-forum thread, not verified here) says Binance charges it
  against the best ask for a long (the best bid for a short). A market order
  at the maximum can therefore be refused when the mark sits below the best
  ask for a long, or above the best bid for a short. `EPIC-028I` must read
  the book or leave that margin before offering a market maximum.

The PR #300 review found the first version (cost = notional ÷ leverage + fee)
overshooting at 1× and 2×, under open loss and past the cap.

Payload-free and `Decimal` throughout; rules as Binance publishes them, not
re-verified against a live order (egress to Binance is blocked here).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.estimate_inputs import (
    require_not_negative,
    require_positive,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_estimates import (
    estimated_fee,
    largest_fitting_quantity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

#: Binance's buffer over the last price for a market order's (and a limit
#: short's) assuming price.
MARKET_PRICE_BUFFER = Decimal("0.0015")


@dataclass(frozen=True)
class FuturesOrderTerms:
    """Everything Binance's cost of one Futures order depends on."""

    side: OrderSide
    #: A limit order's price; `None` for a market order.
    order_price: Decimal | None
    last_price: Decimal
    mark_price: Decimal
    leverage: int
    #: The taker rate, as a fraction (`0.0005` is 0.05 %).
    fee_rate: Decimal
    #: The notional still allowed at this leverage: the bracket's limit less
    #: the notional already open on the symbol (position and open orders).
    notional_headroom: Decimal

    def __post_init__(self) -> None:
        if self.order_price is not None:
            require_positive("order_price", self.order_price)
        require_positive("last_price", self.last_price)
        require_positive("mark_price", self.mark_price)
        if self.leverage < 1:
            raise ValueError(f"leverage must be 1 or more, got {self.leverage}")
        require_not_negative("fee_rate", self.fee_rate)
        require_not_negative("notional_headroom", self.notional_headroom)


def assuming_price(terms: FuturesOrderTerms) -> Decimal:
    """@return The price Binance sizes the order's initial margin at."""
    buffered_last = terms.last_price * (1 + MARKET_PRICE_BUFFER)
    if terms.order_price is None:
        return buffered_last
    if terms.side is OrderSide.BUY:
        return terms.order_price
    return max(buffered_last, terms.mark_price, terms.order_price)


def open_loss(quantity: Decimal, terms: FuturesOrderTerms) -> Decimal:
    """@return The loss the order would open at today's mark: a long
    priced above the mark, or a short below it. Zero for a market order,
    which this module does not model (see the module docstring)."""
    require_not_negative("quantity", quantity)
    if terms.order_price is None:
        return Decimal(0)
    direction = 1 if terms.side is OrderSide.BUY else -1
    return quantity * abs(
        min(Decimal(0), direction * (terms.mark_price - terms.order_price))
    )


def futures_order_cost(quantity: Decimal, terms: FuturesOrderTerms) -> Decimal:
    """@return Binance's cost of the order: the initial margin at the
    assuming price plus the open loss. The fee is `estimated_fee`."""
    require_not_negative("quantity", quantity)
    return quantity * assuming_price(terms) / terms.leverage + open_loss(
        quantity, terms
    )


def futures_order_fee(quantity: Decimal, terms: FuturesOrderTerms) -> Decimal:
    """@return The taker fee on the order, priced at the assuming price."""
    return estimated_fee(quantity, assuming_price(terms), terms.fee_rate)


def futures_max_quantity(
    available: Decimal, terms: FuturesOrderTerms, step_size: Decimal
) -> Decimal:
    """@return The largest multiple of `step_size` whose Binance cost plus
    fee `available` pays and whose notional fits `notional_headroom`."""
    require_not_negative("available", available)
    one = Decimal(1)
    unit_cost = futures_order_cost(one, terms) + futures_order_fee(one, terms)
    by_balance = largest_fitting_quantity(unit_cost, available, step_size)
    notional_price = max(assuming_price(terms), terms.mark_price)
    by_notional = largest_fitting_quantity(
        notional_price, terms.notional_headroom, step_size
    )
    return min(by_balance, by_notional)
