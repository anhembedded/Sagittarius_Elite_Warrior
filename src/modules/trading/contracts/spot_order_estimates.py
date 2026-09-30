"""`EPIC-028G` — what a Spot buy costs and how large it may be.

@details Spot has no margin, no assuming price and no open loss: a buy spends
its notional from the quote balance. The fee is counted in the quote too,
although a Spot buy is actually charged it in the base asset it receives, so
the maximum reads at most one fee low, never high.

**Which price.** `SpotOrderTerms.price` is a limit order's price, and then the
maximum is never refused for balance. For a market buy the fill price is not
known in advance: the caller passes the price it expects to pay (the best
ask), and a book that moves up between the estimate and the fill can make
that quantity unaffordable. A desk that must not be refused sizes a market
buy by quote amount instead (Binance's `quoteOrderQty`); that is `EPIC-028H`'s
choice, and this module says so rather than hide it.

A sell's maximum is the free base balance floored to the step, and needs no
estimate.
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


@dataclass(frozen=True)
class SpotOrderTerms:
    """What a Spot buy's cost depends on."""

    #: A limit order's price; for a market buy, the price the caller expects
    #: to pay (see the module docstring).
    price: Decimal
    #: The taker rate, as a fraction (`0.001` is 0.1 %).
    fee_rate: Decimal

    def __post_init__(self) -> None:
        require_positive("price", self.price)
        require_not_negative("fee_rate", self.fee_rate)


def spot_buy_cost(quantity: Decimal, terms: SpotOrderTerms) -> Decimal:
    """@return The quote the buy spends, its fee counted in the quote."""
    require_not_negative("quantity", quantity)
    return quantity * terms.price + estimated_fee(quantity, terms.price, terms.fee_rate)


def spot_max_buy_quantity(
    available_quote: Decimal, terms: SpotOrderTerms, step_size: Decimal
) -> Decimal:
    """@return The largest multiple of `step_size` whose `spot_buy_cost`
    `available_quote` pays."""
    return largest_fitting_quantity(
        spot_buy_cost(Decimal(1), terms), available_quote, step_size
    )
