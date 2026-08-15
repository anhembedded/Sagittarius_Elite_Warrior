from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.domain.backtesting.out_of_sample_validation import (
        OutOfSampleValidation,
    )


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
    #: BOT-080 — None means "not computed" (e.g. too little data to split),
    #: not "no overfitting risk". Deliberately optional rather than a
    #: required field: every existing direct construction of a
    #: `BacktestResult` (tests, `.compute()`'s own pre-BOT-080 call sites)
    #: keeps working unchanged. Never affects `trades`/`equity_curve`/
    #: `metrics` above, which stay the full-range result exactly as before.
    out_of_sample: OutOfSampleValidation | None = None

    @classmethod
    def compute(
        cls,
        symbol: str,
        initial_balance: float,
        final_balance: float,
        trades: list[Trade],
        equity_curve: list[tuple[datetime, float]],
        out_of_sample: OutOfSampleValidation | None = None,
    ) -> BacktestResult:
        return cls(
            symbol=symbol,
            initial_balance=initial_balance,
            final_balance=final_balance,
            trades=list(trades),
            equity_curve=list(equity_curve),
            metrics=BacktestMetrics.compute(trades, equity_curve, initial_balance),
            out_of_sample=out_of_sample,
        )
