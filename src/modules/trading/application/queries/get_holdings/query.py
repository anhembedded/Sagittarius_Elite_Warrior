from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class GetHoldingsQuery:
    """@brief Query for the account's current Spot holdings (`EPIC-027O`).

    @details Only the venue (`EPIC-028B`), same reasoning
    `GetOpenPositionsQuery` gives: `ITradingAccountReader.check_connection()`
    with no symbol already reads that venue's whole account.
    """

    #: `EPIC-028B` (ADR D3) — the venue this acts on. Keyword-only and
    #: required: a caller that forgets it fails at construction, never
    #: silently addresses some default venue.
    venue: TradingVenue = field(kw_only=True)
