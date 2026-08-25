from collections.abc import Mapping
from typing import Any

from Sagittarius_Elite_Warrior.src.application.ports.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_engine import (
    StrategyEngine,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)


def build_engine(
    registry: StrategyRegistry,
    key: str,
    event_publisher: IEventPublisher,
    params: Mapping[str, Any] | None = None,
) -> StrategyEngine:
    """
    @brief Builds a ready-to-run `StrategyEngine` for a registered strategy key.
    @param params Values for the parameters the strategy declares via
    `input_*()` (BOT-046). None uses every declared default.
    @details Reads `strategy.build_indicators()` rather than guessing an
    indicator set from the strategy's class/key — that keeps "which
    indicators does this strategy need" declared in exactly one place (the
    strategy itself), with this factory only wiring it up. `build_indicators()`
    is called only after `registry.create()` returns, i.e. after `setup()`
    has already resolved every declared input — a strategy reading
    `self._fast_period` there sees the caller-supplied value, not the default.
    """
    strategy = registry.create(key, params)
    return StrategyEngine(
        indicators=strategy.build_indicators(),
        strategy=strategy,
        event_publisher=event_publisher,
    )
