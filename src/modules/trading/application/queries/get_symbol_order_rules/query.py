from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class GetSymbolOrderRulesQuery:
    """@brief Query for one symbol's order filters on a venue (`EPIC-028H`):
    lot step, tick size and minimum notional."""

    venue: TradingVenue = field(kw_only=True)
    symbol: str = field(kw_only=True)

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
