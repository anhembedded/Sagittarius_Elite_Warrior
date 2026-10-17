from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class GetOrderQuery:
    """@brief Query for one order of a venue by the client id it was sent under (`EPIC-039L`):
    the exchange's own answer, with no cache, for the one caller that must tell how an order
    ended (a bot's protective stop that left the open list)."""

    venue: TradingVenue = field(kw_only=True)
    symbol: str = field(kw_only=True)
    client_order_id: str = field(kw_only=True)
