from Sagittarius_Elite_Warrior.src.application.services.strategy_engine import (
    StrategyEngine,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus


def build_engine(
    registry: StrategyRegistry, key: str, event_bus: IEventBus
) -> StrategyEngine:
    """
    @brief Builds a ready-to-run `StrategyEngine` for a registered strategy key.
    @details Reads `strategy.build_indicators()` rather than guessing an
    indicator set from the strategy's class/key — that keeps "which
    indicators does this strategy need" declared in exactly one place (the
    strategy itself), with this factory only wiring it up.
    """
    strategy = registry.create(key)
    return StrategyEngine(
        indicators=strategy.build_indicators(),
        strategy=strategy,
        event_bus=event_bus,
    )
