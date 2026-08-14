from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)

#: BOT-080 — if the in-sample run's net_profit_percent beats the
#: out-of-sample run's by more than this many percentage points, flag it:
#: a strategy that looks great on the data it was tuned on and much worse on
#: data it never saw is the signature of overfitting, not "still profitable
#: on unseen data, just less so". Only fires in that direction — an
#: out-of-sample run that does BETTER than in-sample is not a red flag.
#: A starting number, not a validated threshold — same caveat as BOT-079's
#: constants, revisit once this has seen real use.
OUT_OF_SAMPLE_DIVERGENCE_WARNING_POINTS = 30.0


@dataclass(frozen=True)
class OutOfSampleValidation:
    """
    @brief BOT-080 — the in-sample (tuning) and out-of-sample (unseen)
    halves of one static backtest run, computed as two independent
    `BacktestResult`s over a chronological split of the same kline range.
    @details Deliberately does not replace or modify the full-range
    `BacktestResult` it's attached to (`BacktestResult.out_of_sample`) —
    the Backtest Screen's existing stat cards/chart/trade log keep showing
    the full range unchanged; this is additional information, not a
    different primary result.
    """

    in_sample: BacktestResult
    out_of_sample: BacktestResult
    in_sample_ratio: float

    @property
    def has_high_divergence(self) -> bool:
        divergence = (
            self.in_sample.metrics.net_profit_percent
            - self.out_of_sample.metrics.net_profit_percent
        )
        return divergence > OUT_OF_SAMPLE_DIVERGENCE_WARNING_POINTS
