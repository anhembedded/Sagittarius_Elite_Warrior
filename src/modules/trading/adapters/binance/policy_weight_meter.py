"""`EPIC-047H` — `IVenueWeightMeter` over the venue's call policy: its last used-weight header and its gate."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.exchange_call_policy import (
    ExchangeCallPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_weight_meter import (
    IVenueWeightMeter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.weight_reading import (
    WeightReading,
)


class PolicyWeightMeter(IVenueWeightMeter):
    def __init__(self, policy: ExchangeCallPolicy) -> None:
        self._policy = policy

    def read(self) -> WeightReading:
        return self._policy.weight_reading()
