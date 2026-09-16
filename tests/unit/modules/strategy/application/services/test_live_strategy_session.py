"""`EPIC-022A` — `LiveStrategySession`.

Two groups of tests live here:

1. **Arming/disarming**, the new behaviour: the seam the Trading screen's
   strategy picker writes to.
2. **Tick filtering and forwarding**, moved verbatim in intent from
   `tests/unit/application/event_handlers/test_market_tick_event_handler.py`
   when the logic moved out of that handler. `BUG-085`'s
   interleaved-interval regression in particular must keep failing if the
   filter is ever loosened — it is a real bug that reached the user, not a
   hypothetical.
"""

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)


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


def _config(
    symbol: str = "BTCUSDT",
    interval: str = TimeFrame.ONE_MINUTE.value,
    key: str = "ema_crossover",
) -> LiveStrategyConfig:
    return LiveStrategyConfig(strategy_key=key, symbol=symbol, interval=interval)


class _FakeFactory:
    """Hands back engines/coordinators the test controls, and records every
    config it was asked to build — enough to prove a re-arm really rebuilt
    rather than reused."""

    def __init__(self, pairs=None):
        self._pairs = list(pairs or [])
        self.built_configs: list[LiveStrategyConfig] = []

    def build(self, config):
        self.built_configs.append(config)
        if self._pairs:
            return self._pairs.pop(0)
        engine = Mock()
        engine.on_tick.return_value = None
        return engine, Mock()


# --------------------------------------------------------------------- #
# Arming / disarming
# --------------------------------------------------------------------- #


def test_a_new_session_is_disarmed_and_ignores_every_tick():
    factory = _FakeFactory()
    session = LiveStrategySession(factory)

    session.dispatch_tick(_market_data())

    assert session.is_armed is False
    assert session.config is None
    assert factory.built_configs == []


def test_arming_builds_the_pair_and_exposes_the_config():
    factory = _FakeFactory()
    session = LiveStrategySession(factory)
    config = _config()

    session.arm(config)

    assert session.is_armed is True
    assert session.config == config
    assert factory.built_configs == [config]


def test_re_arming_rebuilds_rather_than_reusing_the_running_engine():
    """A strategy swap must build a NEW engine, and route ticks to it.

    @details Asserted as the two observable facts, not as a claim about
    indicator state the test cannot see: the factory was asked to build
    twice, and after the second arm the FIRST engine receives nothing
    while the second receives the tick. (Reworded from a docstring that
    promised "clean indicator state" — a promise this body does not check
    and could not, since the engines here are doubles.)"""
    first_engine, second_engine = Mock(), Mock()
    first_engine.on_tick.return_value = None
    second_engine.on_tick.return_value = None
    factory = _FakeFactory([(first_engine, Mock()), (second_engine, Mock())])
    session = LiveStrategySession(factory)

    session.arm(_config(key="ema_crossover"))
    session.arm(_config(key="support_resistance"))
    session.dispatch_tick(_market_data())

    assert len(factory.built_configs) == 2
    first_engine.on_tick.assert_not_called()
    second_engine.on_tick.assert_called_once()


def test_disarming_makes_every_later_tick_inert():
    engine = Mock()
    engine.on_tick.return_value = None
    session = LiveStrategySession(_FakeFactory([(engine, Mock())]))
    session.arm(_config())

    session.disarm()
    session.dispatch_tick(_market_data())

    assert session.is_armed is False
    assert session.config is None
    engine.on_tick.assert_not_called()


def test_generation_changes_on_every_arm_and_disarm():
    """Comparing `config` alone cannot tell "still the same arming" from
    "re-armed with identical values"; a caller that needs to know reads
    this instead."""
    session = LiveStrategySession(_FakeFactory())
    seen = [session.generation]

    session.arm(_config())
    seen.append(session.generation)
    session.arm(_config())
    seen.append(session.generation)
    session.disarm()
    seen.append(session.generation)

    assert len(set(seen)) == len(seen)


@pytest.mark.parametrize(
    "config",
    [
        LiveStrategyConfig(strategy_key="", symbol="BTCUSDT", interval="1m"),
        LiveStrategyConfig(strategy_key="ema_crossover", symbol="", interval="1m"),
        LiveStrategyConfig(strategy_key="ema_crossover", symbol="BTCUSDT", interval=""),
    ],
)
def test_arming_an_incomplete_config_raises_instead_of_half_arming(config):
    """An empty interval must never fall back to "match everything"
    (`BUG-085` §4.2) — refusing outright is the only honest option, since
    a guessed interval is a wrong strategy."""
    factory = _FakeFactory()
    session = LiveStrategySession(factory)

    with pytest.raises(ValueError):
        session.arm(config)

    assert session.is_armed is False
    assert factory.built_configs == []


def test_a_failed_rebuild_leaves_the_previous_arming_intact():
    """`registry.create()` raises for an unknown key or an undeclared
    parameter. The previous strategy must keep running rather than the
    session ending up half-swapped with no engine at all."""

    class _FailingOnSecondBuild(_FakeFactory):
        def build(self, config):
            if self.built_configs:
                self.built_configs.append(config)
                raise ValueError("unknown strategy key")
            return super().build(config)

    good_config = _config(key="ema_crossover")
    factory = _FailingOnSecondBuild()
    session = LiveStrategySession(factory)
    session.arm(good_config)

    with pytest.raises(ValueError):
        session.arm(_config(key="does_not_exist"))

    assert session.is_armed is True
    assert session.config == good_config


# --------------------------------------------------------------------- #
# Tick filtering + forwarding (moved from the handler's own test file)
# --------------------------------------------------------------------- #


def test_feeds_the_engine_when_the_tick_matches_symbol_and_interval():
    engine = Mock()
    engine.on_tick.return_value = None
    session = LiveStrategySession(_FakeFactory([(engine, Mock())]))
    session.arm(_config())
    market_data = _market_data("BTCUSDT")

    session.dispatch_tick(market_data)

    engine.on_tick.assert_called_once_with(market_data)


def test_ignores_a_tick_for_a_different_symbol():
    """Corrupting one engine's indicator state by feeding it a different
    symbol's candles is exactly what this guards against (`EPIC-021G` —
    single-symbol live trading)."""
    engine = Mock()
    session = LiveStrategySession(_FakeFactory([(engine, Mock())]))
    session.arm(_config(symbol="BTCUSDT"))

    session.dispatch_tick(_market_data("ETHUSDT"))

    engine.on_tick.assert_not_called()


def test_ignores_a_tick_for_a_different_interval_same_symbol():
    """`BUG-085`: the same corruption also happens when two intervals of
    the SAME symbol are streaming — an EMA fed alternating `1m` and `5m`
    closes is neither timeframe's EMA."""
    engine = Mock()
    session = LiveStrategySession(_FakeFactory([(engine, Mock())]))
    session.arm(_config(interval=TimeFrame.ONE_MINUTE.value))

    session.dispatch_tick(_market_data("BTCUSDT", TimeFrame.FIVE_MINUTES.value))

    engine.on_tick.assert_not_called()


def test_feeds_only_the_configured_interval_when_intervals_are_interleaved():
    """`BUG-085` regression: alternating `1m` and `5m` ticks for the same
    symbol must reach the engine as an unbroken `1m`-only stream."""
    engine = Mock()
    engine.on_tick.return_value = None
    session = LiveStrategySession(_FakeFactory([(engine, Mock())]))
    session.arm(_config(interval=TimeFrame.ONE_MINUTE.value))

    session.dispatch_tick(_market_data("BTCUSDT", TimeFrame.ONE_MINUTE.value))
    session.dispatch_tick(_market_data("BTCUSDT", TimeFrame.FIVE_MINUTES.value))
    session.dispatch_tick(_market_data("BTCUSDT", TimeFrame.ONE_MINUTE.value))

    assert engine.on_tick.call_count == 2
    for call in engine.on_tick.call_args_list:
        assert call.args[0].interval == TimeFrame.ONE_MINUTE.value


def test_forwards_an_actionable_signal_straight_to_the_coordinator():
    """The safety-critical wiring: `on_tick()`'s returned `Signal` goes
    directly to `LiveTradingCoordinator.handle()`, never through the
    shared `SignalGeneratedEvent` bus a backtest run also publishes on."""
    engine, coordinator = Mock(), Mock()
    signal = Mock()
    engine.on_tick.return_value = signal
    session = LiveStrategySession(_FakeFactory([(engine, coordinator)]))
    session.arm(_config())

    session.dispatch_tick(_market_data("BTCUSDT"))

    coordinator.handle.assert_called_once_with(signal)


def test_no_signal_does_not_call_the_coordinator():
    engine, coordinator = Mock(), Mock()
    engine.on_tick.return_value = None
    session = LiveStrategySession(_FakeFactory([(engine, coordinator)]))
    session.arm(_config())

    session.dispatch_tick(_market_data("BTCUSDT"))

    coordinator.handle.assert_not_called()


def test_the_lock_is_released_before_the_coordinator_runs():
    """The coordinator makes real network calls. Holding the session lock
    across them would let one in-flight tick freeze the UI thread for a
    whole Binance round-trip the moment the user re-arms. Proven by
    re-entering the session from inside `coordinator.handle()` — with a
    lock still held around that call this deadlocks instead of failing an
    assert (a non-reentrant lock) or, with the `RLock`, silently passes
    only because the SAME thread happens to own it; so the assertion is on
    the observable result, that the re-arm went through."""
    engine, coordinator = Mock(), Mock()
    engine.on_tick.return_value = Mock()
    session = LiveStrategySession(
        _FakeFactory([(engine, coordinator), (Mock(), Mock())])
    )
    session.arm(_config(key="ema_crossover"))
    swapped = _config(key="support_resistance")
    coordinator.handle.side_effect = lambda _signal: session.arm(swapped)

    session.dispatch_tick(_market_data("BTCUSDT"))

    assert session.config == swapped
