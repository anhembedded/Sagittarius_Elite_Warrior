from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)


@dataclass(frozen=True)
class BacktestCompletedEvent:
    """Fired once a static (or, later, dynamic) backtest run finishes successfully."""

    result: BacktestResult
