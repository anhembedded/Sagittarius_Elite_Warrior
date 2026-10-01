from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class GetOrderNotionalLimitQuery:
    """@brief Query for the largest notional the app lets one order on
    `venue` have (`EPIC-028O`): `TradingLimits.max_notional_per_order`, the
    limit `ExecuteOrderCommandHandler` refuses an order over."""

    venue: TradingVenue = field(kw_only=True)
