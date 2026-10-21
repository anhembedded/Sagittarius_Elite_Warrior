from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.request_priority import (
    RequestPriority,
)
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
    #: `BOT-226` — whether the read looks for a bot's protective stops and so may use the weight
    #: reserve.
    priority: RequestPriority = field(default=RequestPriority.ROUTINE, kw_only=True)
