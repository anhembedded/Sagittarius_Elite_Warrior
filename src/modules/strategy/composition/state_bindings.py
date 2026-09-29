"""This module's own long-lived state: the registry of strategy classes, and
each venue's live strategy session (`EPIC-028B`: one armed strategy per
venue).

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
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.venue_strategy_sessions import (
    VenueStrategySessions,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
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

    # `EPIC-028B` — one session per venue, each built with that venue's own
    # published trading ports, so an armed strategy sends its orders to the
    # venue it was armed on.
    container.singleton(
        VenueStrategySessions,
        lambda c: VenueStrategySessions(lambda venue: _build_session(c, venue)),
    )
    # The primary venue's session: what the single Trading screen and Dev
    # Board read (`IArmedStrategy` and the readers built on it) until each
    # venue has its own desk (`EPIC-028K`/`028L`).
    container.singleton(
        LiveStrategySession,
        lambda c: c.resolve(VenueStrategySessions).get(c.resolve(TradingVenue)),
    )


def _build_session(container: IContainer, venue: TradingVenue) -> LiveStrategySession:
    """@raise VenueNotEnabledError `venue` is not served, before any session
    exists for it (`IVenueTradingPorts.get()` refuses first)."""
    ports = container.resolve(IVenueTradingPorts).get(venue)
    context = container.resolve(IVenueContexts).get(venue)
    return LiveStrategySession(
        LiveStrategyFactory(
            container.resolve(StrategyRegistry),
            container.resolve(IEventPublisher),
            ports.order_submission,
            context.account_reader,
            context.metadata_provider,
            ports.trading_session,
        )
    )
