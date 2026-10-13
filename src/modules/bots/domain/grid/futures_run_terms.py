"""`EPIC-039K` — what a Futures replay needs beyond a Spot one: the ports for what differs.

@details The simulator stays pure: it performs no I/O and prices nothing itself. The
application reads the symbol's brackets and funding history, takes the fees from the cost
model (`ICostModel`, `EPIC-039G`) and hands them over as this one value, the way the venue's
terms reach a Spot replay. Nothing here knows which exchange the numbers came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_funding import (
    FundingCharger,
    FundingSchedule,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)


@dataclass(frozen=True, slots=True)
class FuturesRunTerms:
    """The brackets, the fees and the funding one Futures replay runs under."""

    brackets: LeverageBrackets
    #: Fractions of the traded notional, from `ICostModel.fees()`.
    maker_fee: Decimal
    taker_fee: Decimal
    funding: FundingSchedule
    #: Turns one settlement into money (`ICostModel.funding_estimate` behind it).
    charge: FundingCharger


def bracket_refusal(params: GridParams, brackets: LeverageBrackets) -> str | None:
    """Why the symbol's brackets do not allow `params`' leverage at the ladder's worst-case
    notional (`capital × leverage`, decision O2), or `None` when they do.

    @details The exchange would refuse the orders; a replay that placed them anyway would
    show a profit the venue never allows. The same comparison `futures_rules.py` makes for
    the Start gate (`leverage_above_bracket`).
    """
    worst_case = params.capital_quote * params.leverage
    bracket = brackets.bracket_for(worst_case)
    if params.leverage <= bracket.initial_leverage:
        return None
    return (
        f"{brackets.symbol} allows {bracket.initial_leverage}x at a notional of "
        f"{worst_case:.2f} (bracket {bracket.bracket}); {params.leverage}x is above it."
    )
