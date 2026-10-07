from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class EmergencyStopCommand:
    """@brief Command to stop everything, right now (`EPIC-021K`).

    @details Only the venue: it stops that venue's whole account
    (`EPIC-028B` — an Emergency Stop on Futures leaves Spot untouched, and
    vice versa), like `EnsureSessionReadyCommand`/`DisableTradingCommand`.
    Always attempted in full even when trading
    was already off or the account was already flat; each step's own
    result says what it actually found.
    """

    #: `EPIC-028B` (ADR D3) — the venue this acts on. Keyword-only and
    #: required: a caller that forgets it fails at construction, never
    #: silently addresses some default venue.
    venue: TradingVenue = field(kw_only=True)
