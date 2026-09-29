from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class GetOpenPositionsQuery:
    """@brief Query for the account's current open positions (`EPIC-024B`
    §2): the manual order form must read the real position before mapping
    a Long/Short button click to `OrderSide`/`reduce_only`, not guess from
    symbol/side alone.
    @details Only the venue (`EPIC-028B`): `ITradingClient.get_positions()`
    with no symbol already reads that venue's whole account.
    """

    #: `EPIC-028B` (ADR D3) — the venue this acts on. Keyword-only and
    #: required: a caller that forgets it fails at construction, never
    #: silently addresses some default venue.
    venue: TradingVenue = field(kw_only=True)
