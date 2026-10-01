from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class GetMarkPriceQuery:
    """@brief Query for a Futures symbol's mark price (`EPIC-028O`,
    `GET /fapi/v1/premiumIndex`)."""

    venue: TradingVenue = field(kw_only=True)
    symbol: str = field(kw_only=True)

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
