from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class CancelOrderCommand:
    """@brief Command to cancel one still-open order by its app-generated
    `client_order_id` (`EPIC-024B` §0).
    @details The one cancel path that existed before this,
    `EmergencyStopCommand`, cancels every open order on a symbol at once
    and is not reusable for a single row's "Huỷ" button — this is the
    first per-order cancel any UI in this app can reach.
    """

    symbol: str
    client_order_id: str
    #: `EPIC-028B` (ADR D3) — the venue this acts on. Keyword-only and
    #: required: a caller that forgets it fails at construction, never
    #: silently addresses some default venue.
    venue: TradingVenue = field(kw_only=True)
