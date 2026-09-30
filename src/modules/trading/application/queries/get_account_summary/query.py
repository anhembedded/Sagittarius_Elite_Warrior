from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class GetAccountSummaryQuery:
    """@brief Query for what a venue's desk shows about its account
    (`EPIC-028D`): spendable balance, value, and the market's own figures.
    """

    #: The venue to read. Keyword-only and required (ADR D3): a caller that
    #: forgets it fails at construction, never reads some default venue.
    venue: TradingVenue = field(kw_only=True)
