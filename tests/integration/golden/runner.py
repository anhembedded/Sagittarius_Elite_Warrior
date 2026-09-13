"""One static backtest over the golden dataset, through the public handler."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest.command import (
    RunStaticBacktestCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest.handler import (
    RunStaticBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.tests.integration.golden.dataset import (
    INTERVAL,
    SYMBOL,
    make_golden_klines,
)
from Sagittarius_Elite_Warrior.tests.integration.golden.fakes.in_memory_market_data_repository import (
    InMemoryMarketDataRepository,
)
from Sagittarius_Elite_Warrior.tests.integration.golden.fakes.recording_event_publisher import (
    RecordingEventPublisher,
)

STRATEGY_KEY = "ema_crossover"
STRATEGY_PARAMS: Mapping[str, Any] = {"fast_period": 12, "slow_period": 26}
INITIAL_BALANCE = 10_000.0
FEE_PERCENT = 0.1


def run_golden_backtest() -> BacktestResult:
    registry = StrategyRegistry()
    registry.register(STRATEGY_KEY, EmaCrossoverStrategy)
    handler = RunStaticBacktestCommandHandler(
        repository=InMemoryMarketDataRepository(make_golden_klines()),
        strategy_registry=registry,
        event_publisher=RecordingEventPublisher(),
    )
    command = RunStaticBacktestCommand(
        symbol=SYMBOL,
        interval=INTERVAL,
        strategy_key=STRATEGY_KEY,
        strategy_params=dict(STRATEGY_PARAMS),
        initial_balance=INITIAL_BALANCE,
        fee_percent=FEE_PERCENT,
    )
    result = handler.execute(command)
    if not isinstance(result, BacktestResult):
        raise TypeError(f"expected a BacktestResult, got {result!r}")
    return result
