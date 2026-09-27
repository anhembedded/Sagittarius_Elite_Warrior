"""EPIC-027B — both backtest handlers honour the Spot gate end to end: a
SHORT-emitting strategy trades only its long side, the result counts every
dropped SHORT/COVER, and a price crash never ends in a liquidation."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.application.run_historical_tick_backtest import (
    RunHistoricalTickBacktestCommand,
    RunHistoricalTickBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.application.run_static_backtest import (
    RunStaticBacktestCommand,
    RunStaticBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_engine_factory import (
    StrategyEngineFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_sizing_policy import (
    default_sizing_policy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.base_strategy import (
    BaseStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.strategy_context import (
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)

_BASE_TIME = datetime(2024, 1, 1, tzinfo=UTC)
_STRATEGY_KEY = "scripted_mixed"


class _ScriptedMixedStrategy(BaseStrategy):
    """Emits both sides by `decide()` call index: three short-side signals
    around one long round trip."""

    ACTIONS: ClassVar[dict[int, SignalAction]] = {
        0: SignalAction.SHORT,
        1: SignalAction.BUY,
        2: SignalAction.SHORT,
        3: SignalAction.COVER,
        4: SignalAction.SELL,
    }

    def setup(self) -> None:
        self._call_index = 0

    def build_indicators(self) -> dict:
        return {}

    def decide(
        self, context: StrategyContext
    ) -> tuple[SignalAction, str, Mapping[str, Any]]:
        action = self.ACTIONS.get(self._call_index, SignalAction.HOLD)
        self._call_index += 1
        emit = {
            SignalAction.BUY: self.buy,
            SignalAction.SELL: self.sell,
            SignalAction.SHORT: self.short,
            SignalAction.COVER: self.cover,
        }.get(action)
        return emit("scripted") if emit is not None else self.hold()


class _BuyWhenFlatStrategy(BaseStrategy):
    def build_indicators(self) -> dict:
        return {}

    def decide(
        self, context: StrategyContext
    ) -> tuple[SignalAction, str, Mapping[str, Any]]:
        if context.current_position_side is None:
            return self.buy("enter")
        return self.hold()


def _candle(
    open_time: datetime,
    span: timedelta,
    low: float,
    high: float,
    close: float,
    interval: TimeFrame,
) -> MarketData:
    return MarketData(
        symbol="BTCUSDT",
        interval=interval.value,
        open_time=open_time,
        open_price=close,
        high_price=high,
        low_price=low,
        close_price=close,
        volume=1.0,
        close_time=open_time + span - timedelta(milliseconds=1),
        quote_asset_volume=close,
        number_of_trades=1,
        taker_buy_base_asset_volume=0.5,
        taker_buy_quote_asset_volume=close * 0.5,
    )


def _hourly_candles(prices: list[tuple[float, float, float]]) -> list[MarketData]:
    """`(low, high, close)` per hour; each candle opens at its close."""
    span = timedelta(hours=1)
    return [
        _candle(_BASE_TIME + index * span, span, low, high, close, TimeFrame.ONE_HOUR)
        for index, (low, high, close) in enumerate(prices)
    ]


def _one_tick_per_minute(closes: list[float]) -> list[MarketData]:
    span = timedelta(seconds=1)
    return [
        _candle(
            _BASE_TIME + timedelta(minutes=index),
            span,
            close,
            close,
            close,
            TimeFrame.ONE_SECOND,
        )
        for index, close in enumerate(closes)
    ]


def _repository_with(
    candles: list[MarketData], market: MarketType
) -> FakeMarketDataRepository:
    """The candles stored under the run's own market, which is where a run
    reads them from (EPIC-027D)."""
    return FakeMarketDataRepository(candles, market=market)


def _engine_factory(strategy_cls: type[BaseStrategy]) -> StrategyEngineFactory:
    registry = StrategyRegistry()
    registry.register(_STRATEGY_KEY, strategy_cls)
    return StrategyEngineFactory(registry, Mock())


def _run_static(
    candles: list[MarketData],
    broker_config: BrokerSimulationConfig,
    strategy_cls: type[BaseStrategy] = _ScriptedMixedStrategy,
) -> BacktestResult:
    handler = RunStaticBacktestCommandHandler(
        repository=_repository_with(candles, broker_config.market_type),
        engine_factory=_engine_factory(strategy_cls),
        sizing_policy=default_sizing_policy(),
        event_publisher=Mock(),
    )
    result = handler.execute(
        RunStaticBacktestCommand(
            symbol="BTCUSDT",
            interval=TimeFrame.ONE_HOUR,
            strategy_key=_STRATEGY_KEY,
            initial_balance=1_000.0,
            fee_percent=0.0,
            broker_config=broker_config,
        )
    )
    assert isinstance(result, BacktestResult)
    return result


def _run_tick(
    ticks: list[MarketData], broker_config: BrokerSimulationConfig
) -> BacktestResult:
    handler = RunHistoricalTickBacktestCommandHandler(
        repository=_repository_with(ticks, broker_config.market_type),
        engine_factory=_engine_factory(_ScriptedMixedStrategy),
        sizing_policy=default_sizing_policy(),
        event_publisher=Mock(),
    )
    result = handler.execute(
        RunHistoricalTickBacktestCommand(
            symbol="BTCUSDT",
            interval=TimeFrame.ONE_MINUTE,
            tick_resolution=TimeFrame.ONE_SECOND,
            strategy_key=_STRATEGY_KEY,
            initial_balance=1_000.0,
            fee_percent=0.0,
            broker_config=broker_config,
        )
    )
    assert isinstance(result, BacktestResult)
    return result


_SPOT = BrokerSimulationConfig(commission_value=0.0, market_type=MarketType.SPOT)
_FUTURES = BrokerSimulationConfig(commission_value=0.0)
_FLAT_HOURS = [(99.0, 101.0, 100.0 + step) for step in range(8)]
_FLAT_MINUTES = [100.0 + step for step in range(8)]


def test_static_spot_run_trades_only_the_long_side_and_counts_the_short_signals():
    result = _run_static(_hourly_candles(_FLAT_HOURS), _SPOT)

    assert [trade.side for trade in result.trades] == [PositionSide.LONG]
    assert result.trades[0].exit_reason is ExitReason.STRATEGY_SIGNAL
    assert result.ignored_short_signals == 3


def test_static_futures_run_still_trades_the_short_side_and_ignores_nothing():
    result = _run_static(_hourly_candles(_FLAT_HOURS), _FUTURES)

    assert PositionSide.SHORT in [trade.side for trade in result.trades]
    assert result.ignored_short_signals == 0


def test_tick_spot_run_honours_the_same_gate():
    result = _run_tick(_one_tick_per_minute(_FLAT_MINUTES), _SPOT)

    assert [trade.side for trade in result.trades] == [PositionSide.LONG]
    assert result.ignored_short_signals == 3


def test_tick_futures_run_still_trades_the_short_side_and_ignores_nothing():
    result = _run_tick(_one_tick_per_minute(_FLAT_MINUTES), _FUTURES)

    assert PositionSide.SHORT in [trade.side for trade in result.trades]
    assert result.ignored_short_signals == 0


def test_static_spot_price_crash_stops_out_and_never_liquidates():
    crash = [
        (99.0, 101.0, 100.0),
        (99.0, 101.0, 100.0),
        (60.0, 100.0, 60.0),
        (1.0, 60.0, 1.0),
        (0.5, 2.0, 0.5),
    ]
    config = BrokerSimulationConfig(
        commission_value=0.0, market_type=MarketType.SPOT, stop_loss_pct=5.0
    )

    result = _run_static(_hourly_candles(crash), config, _BuyWhenFlatStrategy)

    reasons = [trade.exit_reason for trade in result.trades]
    assert ExitReason.LIQUIDATION not in reasons
    assert reasons[0] is ExitReason.STOP_LOSS
    assert result.trades[0].pnl < 0
    # Re-enters whenever flat, so the crash may stop it out more than once;
    # every loss is realised from its own cash, none from a liquidation.
    assert result.final_balance == pytest.approx(
        1_000.0 + sum(trade.pnl for trade in result.trades)
    )
    assert result.final_balance > 0


def test_a_run_reads_the_candles_of_its_own_market():
    """EPIC-027D — Spot and Futures candles of one symbol are stored apart and
    priced differently; each run fills at its own market's prices."""
    spot = _hourly_candles([(99.0, 101.0, 100.0 + step) for step in range(8)])
    futures = _hourly_candles([(199.0, 201.0, 200.0 + step) for step in range(8)])
    repository = FakeMarketDataRepository(spot, market=MarketType.SPOT)
    repository.save_klines(MarketType.FUTURES_USD_M, futures)

    def run(config: BrokerSimulationConfig) -> BacktestResult:
        handler = RunStaticBacktestCommandHandler(
            repository=repository,
            engine_factory=_engine_factory(_BuyWhenFlatStrategy),
            sizing_policy=default_sizing_policy(),
            event_publisher=Mock(),
        )
        result = handler.execute(
            RunStaticBacktestCommand(
                symbol="BTCUSDT",
                interval=TimeFrame.ONE_HOUR,
                strategy_key=_STRATEGY_KEY,
                initial_balance=1_000.0,
                fee_percent=0.0,
                broker_config=config,
            )
        )
        assert isinstance(result, BacktestResult)
        return result

    assert run(_SPOT).trades[0].entry_price == pytest.approx(101.0)
    assert run(_FUTURES).trades[0].entry_price == pytest.approx(201.0)
