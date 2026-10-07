from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class EnrolKeyCommand:
    """@brief Add a Binance key: find the environment it belongs to and keep it
    for the venues it is for (`BUG-176`).

    @details The user never says which environment the key is from. `only_for`
    is set by Replace on one venue's row: the key must then be that venue's, and
    it is kept for that venue alone, so replacing one venue's key never touches
    another's. `credentials` prints masked, so the command may be logged.
    """

    credentials: ExchangeCredentials
    only_for: TradingVenue | None = None
