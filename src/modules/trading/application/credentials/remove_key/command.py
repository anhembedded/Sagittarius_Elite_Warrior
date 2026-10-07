from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class RemoveKeyCommand:
    """@brief Forget the key the app keeps for one venue (`BUG-176`); no other
    venue's key is touched."""

    venue: TradingVenue = field(kw_only=True)
