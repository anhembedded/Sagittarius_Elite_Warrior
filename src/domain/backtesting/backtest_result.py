from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade


@dataclass(frozen=True)
class BacktestResult:
    """
    @brief Full outcome of one static backtest run — everything the Backtest
    Screen (BOT-022) needs to render its 4 TradingView-style panels
    (Properties, Performance Summary, List of Trades, Overview).
    """

    symbol: str
    initial_balance: float
    final_balance: float
    trades: list[Trade]
    equity_curve: list[tuple[datetime, float]]
    metrics: BacktestMetrics

    @classmethod
    def compute(
        cls,
        symbol: str,
        initial_balance: float,
        final_balance: float,
        trades: list[Trade],
        equity_curve: list[tuple[datetime, float]],
    ) -> BacktestResult:
        return cls(
            symbol=symbol,
            initial_balance=initial_balance,
            final_balance=final_balance,
            trades=list(trades),
            equity_curve=list(equity_curve),
            metrics=BacktestMetrics.compute(trades, equity_curve, initial_balance),
        )
