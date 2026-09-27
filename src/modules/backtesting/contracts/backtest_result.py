from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exchange_filters import (
    ExchangeFilters,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
    from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.out_of_sample_validation import (
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
    #: EPIC-027B — SHORT/COVER signals a Spot run dropped because a Spot
    #: market cannot execute them (ADR D4: counted and reported, never
    #: remapped). Always 0 for a Futures run. A result fact, so the report
    #: (`EPIC-027E`) and the UI show it without re-deriving it.
    ignored_short_signals: int = 0
    #: EPIC-027C — entries an exchange filter refused (below the minimum
    #: quantity or notional). They opened nothing and the run continued.
    rejected_entries: int = 0
    #: EPIC-027C — the exchange filters this run applied, or `None` when no
    #: metadata was available and none were (ADR D5: whether filters applied,
    #: and their values, is a result fact).
    exchange_filters: ExchangeFilters | None = None
    #: EPIC-027D — the market this run simulated. Defaults like
    #: `BrokerSimulationConfig.market_type`, so a result built without one
    #: (a report saved before EPIC-027E) reads as the engine default.
    market_type: MarketType = MarketType.FUTURES_USD_M

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
        ignored_short_signals: int = 0,
        rejected_entries: int = 0,
        exchange_filters: ExchangeFilters | None = None,
        market_type: MarketType = MarketType.FUTURES_USD_M,
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
            ignored_short_signals=ignored_short_signals,
            rejected_entries=rejected_entries,
            exchange_filters=exchange_filters,
            market_type=market_type,
        )
