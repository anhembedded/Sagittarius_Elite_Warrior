"""Integration tests for Backtest with Broker Simulation (BOT-104 Phase 2)."""

import logging
from datetime import UTC, datetime, timedelta
from typing import ClassVar
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_historical_tick_backtest import (
    RunHistoricalTickBacktestCommand,
    RunHistoricalTickBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest import (
    RunStaticBacktestCommand,
    RunStaticBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

_T0 = datetime(2024, 1, 1, tzinfo=UTC)


class _PyramidingStrategy(BaseStrategy):
    """Strategy that issues 3 BUY signals in a row, then 1 SELL signal."""

    ACTIONS: ClassVar[dict[int, SignalAction]] = {
        1: SignalAction.BUY,  # Bar 1 -> fills Bar 2
        2: SignalAction.BUY,  # Bar 2 -> fills Bar 3
        3: SignalAction.BUY,  # Bar 3 -> fills Bar 4
        4: SignalAction.SELL,  # Bar 4 -> fills Bar 5
    }

    def setup(self) -> None:
        self._call_index = 0

    def build_indicators(self) -> dict:
        return {}

    def decide(self, context: StrategyContext) -> tuple[SignalAction, str]:
        self._call_index += 1
        action = self.ACTIONS.get(self._call_index, SignalAction.HOLD)
        if action is SignalAction.BUY:
            return self.buy(f"pyramid buy {self._call_index}")
        if action is SignalAction.SELL:
            return self.sell("pyramid exit all")
        return self.hold()


def _make_klines(
    count: int = 10, start_price: float = 100.0, step: float = 10.0
) -> list[MarketData]:
    """Generates synthetic 1m candles increasing by `step` each minute."""
    klines = []
    for i in range(count):
        price = start_price + i * step
        klines.append(
            MarketData(
                symbol="BTCUSDT",
                interval=TimeFrame.ONE_MINUTE.value,
                open_time=_T0 + timedelta(minutes=i),
                open_price=price,
                high_price=price + 2.0,
                low_price=price - 2.0,
                close_price=price + 1.0,
                volume=100.0,
                close_time=_T0 + timedelta(minutes=i + 1),
                quote_asset_volume=10_000.0,
                number_of_trades=10,
                taker_buy_base_asset_volume=50.0,
                taker_buy_quote_asset_volume=5_000.0,
            )
        )
    return klines


def test_static_backtest_with_position_sizing_and_pyramiding_integration(caplog):
    caplog.set_level(logging.DEBUG, logger="App.PaperExchange")

    repo = Mock()
    klines = _make_klines(count=8, start_price=100.0, step=10.0)
    # BUG-025: RunStaticBacktestCommandHandler streams via count_klines()/
    # stream_klines() instead of get_klines() — mirror that contract here
    # against this test's static `klines` list.
    repo.count_klines.side_effect = lambda **kwargs: (
        len(klines)
        if kwargs.get("limit") is None
        else min(kwargs["limit"], len(klines))
    )
    repo.stream_klines.side_effect = lambda **kwargs: iter(
        klines[kwargs.get("offset") or 0 :][: kwargs.get("limit")]
    )

    registry = StrategyRegistry()
    registry.register("pyramiding_test", _PyramidingStrategy)

    event_publisher = Mock()
    handler = RunStaticBacktestCommandHandler(
        repository=repo,
        strategy_registry=registry,
        event_publisher=event_publisher,
    )

    # Configure 25% equity sizing, pyramiding=3, slippage=2 ticks (tick_size=0.1 -> 0.20 slippage)
    sizing = PositionSizing(type=PositionSizingType.PERCENT_OF_EQUITY, value=25.0)
    broker_cfg = BrokerSimulationConfig(
        pyramiding=3,
        slippage_ticks=2,
        tick_size=0.1,
        commission_value=0.0,  # 0 fee for exact math verification
    )

    cmd = RunStaticBacktestCommand(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE,
        strategy_key="pyramiding_test",
        initial_balance=10_000.0,
        position_sizing=sizing,
        broker_config=broker_cfg,
    )

    result = handler.execute(cmd)

    assert isinstance(result, BacktestResult)
    # 3 entries were opened, 1 sell signal closed all 3 positions -> exactly 3 closed trades
    assert result.metrics.total_closed_trades == 3
    assert len(result.trades) == 3

    # Check slippage applied to entry fills:
    # Bar 2 open = 110.0 -> entry_price = 110.20
    # Bar 3 open = 120.0 -> entry_price = 120.20
    # Bar 4 open = 130.0 -> entry_price = 130.20
    assert result.trades[0].entry_price == pytest.approx(110.20)
    assert result.trades[1].entry_price == pytest.approx(120.20)
    assert result.trades[2].entry_price == pytest.approx(130.20)

    # Check slippage applied to exit fill:
    # Bar 5 open = 140.0 -> exit_price = 139.80
    assert result.trades[0].exit_price == pytest.approx(139.80)
    assert result.trades[1].exit_price == pytest.approx(139.80)
    assert result.trades[2].exit_price == pytest.approx(139.80)

    # Check all trades are profitable and equity increased
    assert result.metrics.percent_profitable == 100.0
    assert result.metrics.net_profit > 0.0
    assert result.equity_curve[-1][1] > 10_000.0

    # Check log trace evidence
    log_messages = [rec.message for rec in caplog.records]
    assert any(
        "[paper-exchange] Initialized for BTCUSDT" in msg for msg in log_messages
    )
    assert any("Pyramiding: 3" in msg for msg in log_messages)
    assert any("Slippage: 2 ticks" in msg for msg in log_messages)
    assert any("Pos: 1/3" in msg for msg in log_messages)
    assert any("Pos: 2/3" in msg for msg in log_messages)
    assert any("Pos: 3/3" in msg for msg in log_messages)
    assert any("All positions closed (3 trades)" in msg for msg in log_messages)


def test_realtime_backtest_with_broker_simulation_integration(caplog):
    caplog.set_level(logging.DEBUG, logger="App.PaperExchange")

    repo = Mock()
    # Synthetic 1s ticks: 60 ticks per 1m bar
    ticks = []
    for i in range(180):  # 3 bars worth of ticks
        price = 100.0 + (i * 0.1)
        ticks.append(
            MarketData(
                symbol="BTCUSDT",
                interval=TimeFrame.ONE_SECOND.value,
                open_time=_T0 + timedelta(seconds=i),
                open_price=price,
                high_price=price + 0.05,
                low_price=price - 0.05,
                close_price=price,
                volume=10.0,
                close_time=_T0 + timedelta(seconds=i + 1),
                quote_asset_volume=1000.0,
                number_of_trades=1,
                taker_buy_base_asset_volume=5.0,
                taker_buy_quote_asset_volume=500.0,
            )
        )
    repo.get_klines.return_value = ticks

    registry = StrategyRegistry()
    registry.register("pyramiding_test", _PyramidingStrategy)

    event_publisher = Mock()
    handler = RunHistoricalTickBacktestCommandHandler(
        repository=repo,
        strategy_registry=registry,
        event_publisher=event_publisher,
    )

    sizing = PositionSizing(type=PositionSizingType.PERCENT_OF_EQUITY, value=50.0)
    broker_cfg = BrokerSimulationConfig(
        pyramiding=2,
        slippage_ticks=1,
        tick_size=0.1,
        commission_value=0.0,
    )

    cmd = RunHistoricalTickBacktestCommand(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE,
        tick_resolution=TimeFrame.ONE_SECOND,
        strategy_key="pyramiding_test",
        initial_balance=10_000.0,
        position_sizing=sizing,
        broker_config=broker_cfg,
    )

    result = handler.execute(cmd)

    assert isinstance(result, BacktestResult)
    assert result.metrics.total_closed_trades == 2
    assert result.metrics.net_profit >= 0.0
    assert result.equity_curve[-1][1] >= 10_000.0
