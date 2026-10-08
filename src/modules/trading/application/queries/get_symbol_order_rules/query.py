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
    #: Ask the exchange again instead of the venue's cached catalog
    #: (`EPIC-035U`): a run that lives for days must see a filter change.
    refresh: bool = field(kw_only=True, default=False)

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
