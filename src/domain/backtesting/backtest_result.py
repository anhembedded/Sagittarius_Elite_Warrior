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
    from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData


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
    #: The bars the run's own engine actually evaluated, when it built them
    #: itself rather than reading them whole from the repository — currently
    #: only the Realtime engine, which aggregates `tick_resolution` ticks
    #: into `interval` bars as it replays them. `None` means "this engine
    #: read its bars straight from storage" (Static), so the chart can query
    #: the same interval back and get identical candles.
    #:
    #: The chart MUST prefer these when present. A Realtime run's bars are
    #: aggregated from the ticks it actually had, gaps included (see
    #: `tick_gap_forced_commit`), so the exchange's own published candles
    #: for that interval are NOT interchangeable with them — drawing the
    #: published ones beneath markers derived from these would show a chart
    #: that disagrees with the decisions the strategy really made.
    committed_bars: list[MarketData] | None = None

    @classmethod
    def compute(
        cls,
        symbol: str,
        initial_balance: float,
        final_balance: float,
        trades: list[Trade],
        equity_curve: list[tuple[datetime, float]],
        out_of_sample: OutOfSampleValidation | None = None,
        committed_bars: list[MarketData] | None = None,
    ) -> BacktestResult:
        return cls(
            symbol=symbol,
            initial_balance=initial_balance,
            final_balance=final_balance,
            trades=list(trades),
            equity_curve=list(equity_curve),
            metrics=BacktestMetrics.compute(trades, equity_curve, initial_balance),
            out_of_sample=out_of_sample,
            committed_bars=None if committed_bars is None else list(committed_bars),
        )
