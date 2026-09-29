from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class DisableTradingCommand:
    """@brief Command to turn live trading off for this session (`EPIC-021I`).
    @details Only the venue, symmetric with `EnableTradingCommand`
    (`EPIC-028B`: turning one venue off leaves the other running). Unlike
    enabling, disabling never
    refuses: it always succeeds, so there is no `DisableTradingResult`
    with a block reason to report.
    """

    #: `EPIC-028B` (ADR D3) — the venue this acts on. Keyword-only and
    #: required: a caller that forgets it fails at construction, never
    #: silently addresses some default venue.
    venue: TradingVenue = field(kw_only=True)
