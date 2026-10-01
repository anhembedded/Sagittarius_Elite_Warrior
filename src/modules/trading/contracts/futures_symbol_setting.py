"""`EPIC-028O` — a Futures symbol's leverage and margin mode, as the account
has them now."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.estimate_inputs import (
    require_positive,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)


@dataclass(frozen=True)
class FuturesSymbolSetting:
    """`GET /fapi/v1/symbolConfig`'s row for one symbol. `positionRisk` v3 no
    longer carries the leverage (`BUG-114`), so this is where a desk reads
    it."""

    symbol: str
    leverage: int
    margin_type: MarginType
    #: The largest position notional the current leverage allows.
    max_notional: Decimal

    def __post_init__(self) -> None:
        if self.leverage < 1:
            raise ValueError(f"leverage must be 1 or more, got {self.leverage}")
        require_positive("max_notional", self.max_notional)
