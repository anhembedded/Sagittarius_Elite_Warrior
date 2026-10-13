"""`EPIC-039F` - everything the plan-time risk guard reads, as one value."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)


@dataclass(frozen=True, slots=True)
class PlanRiskInputs:
    """What `IRiskGuard.judge_plan` is given."""

    params: GridParams
    plan: GridPlan
    #: The account's setting for the symbol (leverage and margin mode as they stand now).
    setting: FuturesSymbolSetting
    brackets: LeverageBrackets
    #: The mark price now; liquidation is on mark.
    mark: Decimal
    thresholds: FuturesGridThresholds
    #: ATR(14) on the daily timeframe; `None` when no candles: the stop's distance to
    #: liquidation is then not judged against an ATR.
    daily_atr: Decimal | None = None

    def __post_init__(self) -> None:
        if self.mark <= 0:
            raise ValueError("mark must be positive")
