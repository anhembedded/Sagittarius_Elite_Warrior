import logging

from Sagittarius_Elite_Warrior.src.application.services.live_trading_coordinator import (
    LiveTradingCoordinator,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_engine import (
    StrategyEngine,
)
from Sagittarius_Elite_Warrior.src.domain.events.market_tick_event import (
    MarketTickEvent,
)


class MarketTickEventHandler:
    """
    @brief Application Event Handler for MarketTickEvent.
    @details Feeds every closed candle for the one configured live symbol
    into `StrategyEngine.on_tick()` (`EPIC-021G`), then hands whatever
    `Signal` it returns straight to `LiveTradingCoordinator.handle()` — a
    direct call, not a second subscription to the `SignalGeneratedEvent`
    `on_tick()` also publishes internally.

    @par Why not subscribe `LiveTradingCoordinator` to `SignalGeneratedEvent`
    That event goes out on the same global event bus a *backtest* run
    uses for its own `StrategyEngine` (`RunHistoricalTickBacktestCommand
    Handler` takes the same shared `IEventPublisher`). A coordinator
    listening on that bus would receive backtest-generated signals too and
    could attempt a real order from a backtest run — gated only by the
    three safety checks, not by "this signal didn't come from a live
    tick" at all. Calling `.handle(signal)` directly, using the `Signal`
    already returned to this handler, sidesteps that hazard entirely: no
    backtest code path ever reaches this class. `ADR §7`'s "no shortcut
    from event handler to `ITradingClient`" is still honored — this calls
    `LiveTradingCoordinator`, which still goes through `ExecuteOrderCommand`
    via `ICommandDispatcher`, never `ITradingClient` directly.

    @par Single-symbol, single-interval only, on purpose
    Every indicator inside `strategy_engine` holds mutable, incrementally
    updated state (`BOT-042B`/`C`). Feeding it candles from two different
    symbols would corrupt that state — an EMA fed alternating BTCUSDT and
    ETHUSDT closes is neither symbol's EMA. The same is true for mixing
    intervals of the same symbol (`BUG-085`): an EMA fed alternating `1m`
    and `5m` closes is neither timeframe's EMA. Multi-symbol / multi-
    interval live trading needs one `StrategyEngine` each, which is
    `EPIC-021I`'s screen to configure, not this handler's job to guess at.

    @par `logger.debug()`, not `.info()` — `BUG-042`
    `SignalLogHandler` mirrors every `"App"` `INFO+` line to the UI's log
    model via a queued Qt signal; 838 trades once produced 5,028 `INFO`
    lines in 2 seconds and froze the UI. Tick processing runs every
    candle, every symbol — `DEBUG` here, `INFO` reserved for the
    once-per-meaningful-event lines this handler's collaborators already
    log (an order sent, a limit hit).

    @par No engine dependency (`EPIC-008F`)
    This class used to take `sagittarius_engine.App` in its constructor and
    store it as `self.app` — the whole engine runtime held by an
    Application-layer object, the heaviest of the layering violations that
    epic set out to remove. It was also **never read**: the attribute was
    assigned and nothing ever used it, so dropping the parameter changes no
    behaviour. Anything this handler genuinely needs later must arrive as a
    port (`application/ports/`), not as the runtime it could pull anything out
    of.
    """

    def __init__(
        self,
        live_symbol: str,
        live_interval: str,
        strategy_engine: StrategyEngine | None,
        live_trading_coordinator: LiveTradingCoordinator | None,
    ) -> None:
        self.logger = logging.getLogger("App.TradingStrategy")
        self._live_symbol = live_symbol
        self._live_interval = live_interval
        self._strategy_engine = strategy_engine
        self._live_trading_coordinator = live_trading_coordinator

    def handle(self, event: MarketTickEvent) -> None:
        """
        @brief Handles the MarketTickEvent.
        """
        md = event.market_data
        self.logger.debug(f"Processing tick for {md.symbol} at {md.close_price}")

        if (
            self._strategy_engine is None
            or md.symbol != self._live_symbol
            or md.interval != self._live_interval
        ):
            return

        signal = self._strategy_engine.on_tick(md)
        if signal is not None and self._live_trading_coordinator is not None:
            self._live_trading_coordinator.handle(signal)
