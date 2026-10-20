from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_opener import (
    SessionOpener,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class EnsureSessionReadyCommand:
    """@brief Command to open a venue's order session if it is not open, after
    reconciling the account (`EPIC-021G`, `EPIC-034C`).
    @details Only the venue (`EPIC-028B`): reconciliation is account-wide
    (ADR §4) within that venue, and nothing else is for a caller to
    parameterize.
    """

    #: `EPIC-028B` (ADR D3) — the venue this acts on. Keyword-only and
    #: required: a caller that forgets it fails at construction, never
    #: silently addresses some default venue.
    venue: TradingVenue = field(kw_only=True)
    #: `BOT-183` - the bot this opening is for, carried on the event it publishes, or
    #: `OpenedByPerson.PERSON` for a person's action (`BOT-197`); `None` when no opener is known.
    opened_for: SessionOpener = field(default=None, kw_only=True)
