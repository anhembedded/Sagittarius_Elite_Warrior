from datetime import UTC, datetime
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.event_handlers.market_data.market_tick_event_handler import (
    MarketTickEventHandler,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


def _market_data(
    symbol: str = "BTCUSDT", interval: str = TimeFrame.ONE_MINUTE.value
) -> MarketData:
    dt = datetime(2023, 1, 1, tzinfo=UTC)
    return MarketData(
        symbol=symbol,
        interval=interval,
        open_time=dt,
        open_price=100.0,
        high_price=110.0,
        low_price=90.0,
        close_price=105.0,
        volume=1000.0,
        close_time=dt,
        quote_asset_volume=105000.0,
        number_of_trades=50,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=52500.0,
    )


def test_logs_at_debug_not_info():
    """`EPIC-021G` §2.5 / `BUG-042`: tick processing runs every candle,
    every symbol — it must never be `INFO`, or `SignalLogHandler` mirrors
    it to the UI's queued log model on every single tick."""
    handler = MarketTickEventHandler(
        live_symbol="BTCUSDT",
        live_interval=TimeFrame.ONE_MINUTE.value,
        strategy_engine=None,
        live_trading_coordinator=None,
    )
    handler.logger = Mock()

    handler.handle(MarketTickEvent(market_data=_market_data()))

    handler.logger.debug.assert_called_once()
    handler.logger.info.assert_not_called()
    call_args = handler.logger.debug.call_args[0][0]
    assert "Processing tick for" in call_args
    assert "BTCUSDT" in call_args


def test_no_strategy_engine_configured_does_nothing_further():
    handler = MarketTickEventHandler(
        live_symbol="BTCUSDT",
        live_interval=TimeFrame.ONE_MINUTE.value,
        strategy_engine=None,
        live_trading_coordinator=None,
    )

    # Would raise if it tried to call .on_tick() on None.
    handler.handle(MarketTickEvent(market_data=_market_data()))


def test_feeds_the_engine_when_the_tick_matches_symbol_and_interval():
    engine = Mock()
    engine.on_tick.return_value = None
    handler = MarketTickEventHandler(
        live_symbol="BTCUSDT",
        live_interval=TimeFrame.ONE_MINUTE.value,
        strategy_engine=engine,
        live_trading_coordinator=None,
    )

    event = MarketTickEvent(market_data=_market_data("BTCUSDT"))
    handler.handle(event)

    engine.on_tick.assert_called_once_with(event.market_data)


def test_ignores_a_tick_for_a_different_symbol():
    """Corrupting one `StrategyEngine`'s indicator state by feeding it a
    different symbol's candles is exactly what this guards against
    (`EPIC-021G` — single-symbol live trading, see the handler's own
    docstring)."""
    engine = Mock()
    handler = MarketTickEventHandler(
        live_symbol="BTCUSDT",
        live_interval=TimeFrame.ONE_MINUTE.value,
        strategy_engine=engine,
        live_trading_coordinator=None,
    )

    handler.handle(MarketTickEvent(market_data=_market_data("ETHUSDT")))

    engine.on_tick.assert_not_called()


def test_ignores_a_tick_for_a_different_interval_same_symbol():
    """`BUG-085`: the same corruption `test_ignores_a_tick_for_a_different_
    symbol` guards against also happens when two intervals of the SAME
    symbol are streaming — an EMA fed alternating `1m` and `5m` closes is
    neither timeframe's EMA."""
    engine = Mock()
    handler = MarketTickEventHandler(
        live_symbol="BTCUSDT",
        live_interval=TimeFrame.ONE_MINUTE.value,
        strategy_engine=engine,
        live_trading_coordinator=None,
    )

    handler.handle(
        MarketTickEvent(
            market_data=_market_data("BTCUSDT", TimeFrame.FIVE_MINUTES.value)
        )
    )

    engine.on_tick.assert_not_called()


def test_feeds_only_the_configured_interval_when_intervals_are_interleaved():
    """`BUG-085` regression: alternating `1m` and `5m` ticks for the same
    symbol must reach the engine as an unbroken `1m`-only stream, not a
    mix of both."""
    engine = Mock()
    engine.on_tick.return_value = None
    handler = MarketTickEventHandler(
        live_symbol="BTCUSDT",
        live_interval=TimeFrame.ONE_MINUTE.value,
        strategy_engine=engine,
        live_trading_coordinator=None,
    )
    one_minute_tick = MarketTickEvent(
        market_data=_market_data("BTCUSDT", TimeFrame.ONE_MINUTE.value)
    )
    five_minute_tick = MarketTickEvent(
        market_data=_market_data("BTCUSDT", TimeFrame.FIVE_MINUTES.value)
    )

    handler.handle(one_minute_tick)
    handler.handle(five_minute_tick)
    handler.handle(one_minute_tick)

    assert engine.on_tick.call_count == 2
    for call in engine.on_tick.call_args_list:
        assert call.args[0].interval == TimeFrame.ONE_MINUTE.value


def test_no_live_interval_configured_ignores_every_tick():
    """An empty configured interval means "no live interval configured"
    (`BUG-085` §4.2) — it must never fall back to matching everything."""
    engine = Mock()
    handler = MarketTickEventHandler(
        live_symbol="BTCUSDT",
        live_interval="",
        strategy_engine=engine,
        live_trading_coordinator=None,
    )

    handler.handle(MarketTickEvent(market_data=_market_data("BTCUSDT")))

    engine.on_tick.assert_not_called()


def test_forwards_an_actionable_signal_straight_to_the_coordinator():
    """The safety-critical wiring: `on_tick()`'s returned `Signal` goes
    directly to `LiveTradingCoordinator.handle()`, never through the
    shared `SignalGeneratedEvent` bus a backtest run also publishes on
    (see both classes' own module docstrings for why)."""
    engine = Mock()
    signal = Mock()
    engine.on_tick.return_value = signal
    coordinator = Mock()
    handler = MarketTickEventHandler(
        live_symbol="BTCUSDT",
        live_interval=TimeFrame.ONE_MINUTE.value,
        strategy_engine=engine,
        live_trading_coordinator=coordinator,
    )

    handler.handle(MarketTickEvent(market_data=_market_data("BTCUSDT")))

    coordinator.handle.assert_called_once_with(signal)


def test_no_signal_does_not_call_the_coordinator():
    engine = Mock()
    engine.on_tick.return_value = None
    coordinator = Mock()
    handler = MarketTickEventHandler(
        live_symbol="BTCUSDT",
        live_interval=TimeFrame.ONE_MINUTE.value,
        strategy_engine=engine,
        live_trading_coordinator=coordinator,
    )

    handler.handle(MarketTickEvent(market_data=_market_data("BTCUSDT")))

    coordinator.handle.assert_not_called()
