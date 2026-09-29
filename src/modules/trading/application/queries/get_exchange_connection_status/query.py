from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class GetExchangeConnectionStatusQuery:
    """
    @brief Query to check whether this app can reach and sign requests to
    the trading venue, and what state that account is in (`EPIC-021D`).
    @details Only the venue (`EPIC-028B`): both venues can be live at once,
    each with its own credentials and account.
    """

    #: `EPIC-028B` (ADR D3) — the venue this acts on. Keyword-only and
    #: required: a caller that forgets it fails at construction, never
    #: silently addresses some default venue.
    venue: TradingVenue = field(kw_only=True)
