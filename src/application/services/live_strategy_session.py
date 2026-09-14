"""`EPIC-022A` — the one place that knows which strategy is running right
now, and the only thing a live tick has to ask.

@details Before this class, `MarketTickEventHandler` received the symbol,
the interval, the `StrategyEngine` and the `LiveTradingCoordinator` as
four constructor arguments, and `binance_bot_module.py::boot()` built it
once and subscribed it to the event bus. That made "which strategy is
live" a startup-only decision: the Trading screen could show a picker,
but there was no seam to attach it to.

This holds the same four things behind `arm()`/`disarm()`, so the picker
has somewhere to write and the tick path has somewhere to read.

@par Why the tick logic lives here and not in the handler
Symbol/interval filtering, `on_tick()`, and the hand-off to
`LiveTradingCoordinator.handle()` are one indivisible step: they must all
see the *same* arming. Left in the handler, each would be a separate read
of a mutable field, and a re-arm landing between two of them would run
one strategy's signal through another strategy's coordinator. Taking a
single snapshot under the lock and using it for all three closes that
without making the caller think about it.

@par Why the snapshot is released before the work runs
`LiveTradingCoordinator.handle()` makes real network calls (metadata
fetch, balance read, order dispatch). Holding the lock across them would
make an `arm()` from the UI thread block for however long Binance takes
to answer — a frozen UI, for a lock that is only protecting four field
reads. So: snapshot inside the lock, work outside it. The honest
consequence is that a tick already in flight finishes on the engine it
started with. That window only exists while trading is OFF, because
`ArmStrategyCommandHandler` refuses to re-arm while it is on
(`EPIC-022` §4.1) — and while trading is off, no order can be sent by
either engine anyway.
"""

from __future__ import annotations

import logging
import threading

from Sagittarius_Elite_Warrior.src.application.services.live_strategy_factory import (
    LiveStrategyFactory,
)
from Sagittarius_Elite_Warrior.src.application.services.live_trading_coordinator import (
    LiveTradingCoordinator,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_engine import (
    StrategyEngine,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.live_strategy_config import (
    LiveStrategyConfig,
)

logger = logging.getLogger("App.LiveStrategySession")


class LiveStrategySession:
    """@brief Mutable, process-wide (DI singleton) holder for the armed
    strategy — the live counterpart to `TradingSessionState`.

    @details Starts disarmed. Nothing here decides *whether* arming is
    allowed (that is `ArmStrategyCommandHandler`'s business rule); this
    class only makes arming possible and keeps it consistent.
    """

    def __init__(self, factory: LiveStrategyFactory) -> None:
        #: `RLock`, matching `TradingSessionState` (`BUG-088`) — reached
        #: from the websocket thread (`dispatch_tick`) and from command
        #: handlers on the thread pool (`arm`/`disarm`) in production, not
        #: merely in theory.
        self._lock = threading.RLock()
        self._factory = factory
        self._config: LiveStrategyConfig | None = None
        self._engine: StrategyEngine | None = None
        self._coordinator: LiveTradingCoordinator | None = None
        #: Bumped on every arm/disarm. Lets a caller tell "still the same
        #: armed strategy" from "re-armed with identical values", which
        #: comparing `config` alone cannot.
        self._generation = 0

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def is_armed(self) -> bool:
        with self._lock:
            return self._engine is not None

    @property
    def available_strategy_keys(self) -> tuple[str, ...]:
        """@brief Every key this session could be armed with, sorted.

        @details Read from the very `StrategyRegistry` the factory builds
        from, so a caller checking a key before arming cannot be looking
        at a different registry than the one that will reject it. Sorted
        because the Trading screen's combo renders this directly and an
        unstable order would reshuffle the list between sessions.
        """
        return tuple(sorted(self._factory.registry.available()))

    @property
    def config(self) -> LiveStrategyConfig | None:
        """@brief What is armed, as data — safe to read from any thread.

        @details Returns the frozen value object, never the engine: a
        caller wanting to know "what is running" gets something it cannot
        accidentally drive.
        """
        with self._lock:
            return self._config

    def arm(self, config: LiveStrategyConfig) -> None:
        """@brief Replaces whatever was armed with a freshly built pair.

        @raises ValueError Propagated from `LiveStrategyFactory.build()`
        for an unknown strategy key or an undeclared parameter. Nothing is
        swapped when it raises — the previous arming stays intact, since
        the build happens before the assignment.
        """
        if not config.is_complete:
            raise ValueError(
                "A live strategy needs a strategy key, a symbol and an interval; "
                f"got key={config.strategy_key!r} symbol={config.symbol!r} "
                f"interval={config.interval!r}."
            )
        engine, coordinator = self._factory.build(config)
        with self._lock:
            self._config = config
            self._engine = engine
            self._coordinator = coordinator
            self._generation += 1
        logger.info(
            "Armed live strategy '%s' on %s %s.",
            config.strategy_key,
            config.symbol,
            config.interval,
        )

    def disarm(self) -> None:
        """@brief Back to the inert state — every later tick is ignored."""
        with self._lock:
            was_armed = self._engine is not None
            self._config = None
            self._engine = None
            self._coordinator = None
            self._generation += 1
        if was_armed:
            logger.info("Disarmed the live strategy.")

    def dispatch_tick(self, market_data: MarketData) -> None:
        """@brief One closed candle in; at most one order intent out.

        @details Silently ignores everything that is not the armed
        symbol+interval — `BUG-085`: an EMA fed alternating `1m` and `5m`
        closes is neither timeframe's EMA, and the same is true across
        symbols. Multi-symbol live trading needs one session each, not one
        engine fed everything.
        """
        with self._lock:
            config = self._config
            engine = self._engine
            coordinator = self._coordinator

        if engine is None or config is None:
            return
        if (
            market_data.symbol != config.symbol
            or market_data.interval != config.interval
        ):
            return

        signal = engine.on_tick(market_data)
        if signal is not None and coordinator is not None:
            coordinator.handle(signal)
