"""`ArmedStrategyConfig` — trading's own copy of what a live strategy arming
names, so `trading` never has to import `modules.strategy.contracts.
live_strategy_config` to know its shape.

@details `DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
§8: `trading` and `strategy` may not both declare each other as a dependency
(`strategy.dependencies` already names `"trading"` for a real boot-order
reason, and the reverse edge closes a cycle the Engine refuses to boot). This
type, and the four ports in this package, are the seam that keeps `trading`'s
UI reading an armed strategy's data without ever naming the module that owns
it — `strategy`'s adapter (`modules/strategy/adapters/`) constructs one of
these from its own `LiveStrategyConfig` at the boundary, field for field.

The bounds below mirror `modules/strategy/contracts/live_strategy_config.py`'s
own `MIN`/`MAX_SIZING_PERCENT`, `MIN`/`MAX_LEVERAGE` and
`SUPPORTED_LIVE_INTERVALS` — duplicated rather than imported, for the same
reason this whole file exists. If the two ever drift, the failure mode is a
spin box that accepts a value `strategy`'s own `arm()` then refuses with a
`ValueError` — shown through the error path both screens already have, not a
silent bypass, since the real validation stays inside `strategy` where
`LiveStrategyConfig.__post_init__` enforces it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame

DEFAULT_SIZING_PERCENT = 20.0
DEFAULT_LEVERAGE = 1.0

MIN_SIZING_PERCENT = 0.1
MAX_SIZING_PERCENT = 100.0
MIN_LEVERAGE = 1.0
MAX_LEVERAGE = 125.0

#: Mirrors `live_strategy_config.py`'s own curated subset — see that file for
#: why `1s`/`1w`/`1M` are excluded.
SUPPORTED_LIVE_INTERVALS: tuple[str, ...] = (
    TimeFrame.ONE_MINUTE.value,
    TimeFrame.THREE_MINUTES.value,
    TimeFrame.FIVE_MINUTES.value,
    TimeFrame.FIFTEEN_MINUTES.value,
    TimeFrame.THIRTY_MINUTES.value,
    TimeFrame.ONE_HOUR.value,
    TimeFrame.FOUR_HOURS.value,
    TimeFrame.ONE_DAY.value,
)


@dataclass(frozen=True)
class ArmedStrategyConfig:
    """@brief What the user chose to run live, as trading's own plain data.

    @details Deliberately unvalidated: the one place this gets constructed
    from a screen (`StrategyArmingCoordinator.build_config()`) hands it
    straight to `IStrategyArmingControl.arm()`, and `strategy`'s adapter is
    what turns it back into a real `LiveStrategyConfig` — which is where
    `__post_init__`'s range and interval checks still run, unchanged. This
    type only needs to carry the values across the boundary intact.
    """

    strategy_key: str
    symbol: str
    interval: str
    strategy_params: Mapping[str, Any] = field(default_factory=dict)
    sizing_percent: float = DEFAULT_SIZING_PERCENT
    leverage: float = DEFAULT_LEVERAGE

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "strategy_params", MappingProxyType(dict(self.strategy_params))
        )
