"""This module's own long-lived state: the registry of strategy classes, and
the factory/session pair that build and hold the one armed strategy.

`EPIC-025E` PR 4.4f-2 — the second of `binance_bot_module.py`'s remaining
bindings to move, following 4.4f-1's precedent for backtesting. `port_bindings
.py`'s own docstring already explains why these two singletons stayed in the
strangler root this long (avoiding a second armed session the tick path never
drives) and why moving them now is safe: nothing here changes *what* gets
built, only *where* the binding that builds it lives.

Two singletons, not a lambda pair resolved lazily like `port_bindings.py`'s:
`LiveStrategyFactory` and `LiveStrategySession` are each built exactly once,
by `register()`, matching `binance_bot_module.py`'s own prior shape — the
`StrategyRegistry` they close over must exist first, which is why
`bind_state()` binds it before the other two.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_factory import (
    LiveStrategyFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_trend_pullback_strategy import (
    EmaTrendPullbackStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.long_term_trend_zone_strategy import (
    LongTermTrendZoneStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.multi_ema_trend_follower_strategy import (
    MultiEmaTrendFollowerStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.support_resistance_strategy import (
    SupportResistanceStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.volume_spike_flow_strategy import (
    VolumeSpikeFlowStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_state(container: IContainer) -> None:
    """Registers every strategy class, then the factory/session pair that
    builds and holds the one live-armed strategy."""
    registry = StrategyRegistry()
    registry.register("ema_crossover", EmaCrossoverStrategy)
    registry.register("multi_ema_trend_follower", MultiEmaTrendFollowerStrategy)
    registry.register("support_resistance", SupportResistanceStrategy)
    registry.register("ema_trend_confirm_pullback", EmaTrendPullbackStrategy)
    registry.register("long_term_trend_zone", LongTermTrendZoneStrategy)
    registry.register("volume_spike_flow", VolumeSpikeFlowStrategy)
    container.singleton(StrategyRegistry, registry)

    container.singleton(
        LiveStrategyFactory,
        lambda c: LiveStrategyFactory(
            c.resolve(StrategyRegistry),
            c.resolve(IEventPublisher),
            c.resolve(IOrderSubmission),
            c.resolve(ITradingAccountReader),
            c.resolve(IMarketMetadataProvider),
        ),
    )
    container.singleton(
        LiveStrategySession,
        lambda c: LiveStrategySession(c.resolve(LiveStrategyFactory)),
    )
