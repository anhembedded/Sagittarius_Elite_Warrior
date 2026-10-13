"""`EPIC-039G` — the funding a venue charges, read for the planner.

@details Trading answers `NotApplicable` on a venue with no funding (Spot), a `FundingRate`
where there is one, and raises when the exchange does not answer. The planner needs the
three as one value of its own: no funding at all (`None`), a rate (`FundingView(rate)`), or
funding that exists and could not be read (`FundingView(None)`), never a zero in place of
either of the last two.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    FundingView,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_entry_terms import (
    IOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.market_price_unavailable_error import (
    MarketPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)

logger = logging.getLogger("App.Bots.Readiness")


def funding_view_of(terms: IOrderEntryTerms, symbol: str) -> FundingView | None:
    try:
        answer = terms.funding_rate_for(symbol)
    except MarketPriceUnavailableError as exc:
        logger.warning(
            "Funding rate of %s not read (%s); funding is unknown, not zero [funding-unknown]",
            symbol,
            exc,
        )
        return FundingView(None)
    if answer is NotApplicable.ON_THIS_VENUE:
        return None
    return FundingView(answer.rate)
