"""Port: *is this date range complete enough to run on?* (HLD §3.4, SDD-06b).

**Why this port exists.** Two backtest coordinators ask the same question —
the chart preview, to warn before a run, and the data-sync coordinator, to
decide whether to sync first — and both build
`GetBacktestRangeCoverageQuery` and dispatch it, so both import
`modules/market_data/application/`. That is the boundary rule's one
prohibition: a consumer may import a module's `contracts/` and nothing else.

**What it fixes beyond the boundary.** `BUG-072` is in this exact path. The
dispatched answer is untyped, so the chart preview unwrapped it with
`getattr(coverage_response, "data", coverage_response)` — a guard added
because a test double's response envelope once reached
`_previewDataReadySignal`'s loosely-typed `object` argument and **crashed the
interpreter** marshalling it between threads. A typed return makes the
envelope impossible rather than tolerated, and the `getattr` goes with it.

**Why the answer keeps the name `BacktestRangeCoverage`.** HLD §3.4 says the
concept is market_data's and backtest merely happened to ask first, which
argues for `RangeCoverage`. It stays as it is for now, for the same reason
`SymbolMarketMetadata` is published under its owner rather than promoted to
`core/vo`: the Published Language admits a rename once a second consumer
*family* exists, measured (HLD §2.4), and today every caller is the Backtest
screen. Renaming it now would be guessing, and renaming it later costs one
import path.

**`now` is the caller's clock, and that is deliberate.** `has_unclosed_candle`
and the expected-candle count depend on what "now" means, and two callers
already pass their own `datetime.now(UTC)`. Keeping it a parameter is what
makes the answer reproducible in a test — and it is what Phase 3 needs, where
`backtesting` replays history and "now" is the simulated clock rather than
the wall clock.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.backtest_range_coverage import (
    BacktestRangeCoverage,
)


class IRangeCoverage(ABC):
    """How much of a requested range this context actually has stored."""

    @abstractmethod
    def coverage(
        self,
        symbol: str,
        interval: TimeFrame,
        *,
        start_time: datetime | None,
        end_time: datetime,
        now: datetime,
    ) -> BacktestRangeCoverage:
        """The coverage of `[start_time, end_time)`, with the diagnosis.

        Always an answer, never an error, for a symbol nothing is stored for:
        `is_fully_covered=False` with `first_open_time`/`last_open_time`
        `None` says "nothing here", which is what a screen must render
        differently from "some of it is missing" — the whole reason this
        returns a value object instead of a boolean.

        `start_time=None` means "from the first candle stored", which is what
        a user who left the range open asks for. It is the expensive case —
        the real implementation scans every row of the shard for it
        (`pre_backtest_assertions.py` documents the cost) — so a caller that
        can bound the range should.
        """
