from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class EnableTradingCommand:
    """@brief Command to turn live trading on for this session
    (`EPIC-021G`).
    @details Only the venue (`EPIC-028B`): reconciliation is account-wide
    (ADR §4) within that venue, and nothing else is for a caller to
    parameterize.
    """

    #: `EPIC-028B` (ADR D3) — the venue this acts on. Keyword-only and
    #: required: a caller that forgets it fails at construction, never
    #: silently addresses some default venue.
    venue: TradingVenue = field(kw_only=True)
