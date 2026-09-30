from dataclasses import dataclass, field
from datetime import datetime

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: ADR D9 (`EPIC-027`): Spot trades USDT-quoted pairs only.
QUOTE_ASSET = "USDT"


@dataclass(frozen=True)
class GetAverageEntryPriceQuery:
    """@brief Query for the average entry price of what a venue holds on
    `symbol` (`EPIC-028E`, closing `EPIC-027` ADR O6), rebuilt from the fills
    since `since`."""

    venue: TradingVenue = field(kw_only=True)
    symbol: str = field(kw_only=True)
    since: datetime = field(kw_only=True)

    def __post_init__(self) -> None:
        if self.since.tzinfo is None:
            raise ValueError("since must be timezone-aware")
        if not self.symbol.endswith(QUOTE_ASSET) or self.symbol == QUOTE_ASSET:
            raise ValueError(f"{self.symbol} is not a {QUOTE_ASSET}-quoted pair")

    @property
    def base_asset(self) -> str:
        return self.symbol.removesuffix(QUOTE_ASSET)
