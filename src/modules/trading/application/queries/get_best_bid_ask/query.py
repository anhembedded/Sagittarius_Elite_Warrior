from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class GetBestBidAskQuery:
    """@brief Query for the best bid and ask on a symbol's book (`EPIC-028O`,
    `ticker/bookTicker`), on either venue."""

    venue: TradingVenue = field(kw_only=True)
    symbol: str = field(kw_only=True)

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
