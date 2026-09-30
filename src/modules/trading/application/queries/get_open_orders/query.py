from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class GetOpenOrdersQuery:
    """@brief Query for a venue's live open orders (`EPIC-028E`), read from
    the exchange so a desk opened after an order was placed elsewhere still
    shows it."""

    venue: TradingVenue = field(kw_only=True)
    #: One symbol, or `None` for every symbol on the account.
    symbol: str | None = field(default=None, kw_only=True)
