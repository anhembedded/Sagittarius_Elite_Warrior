"""The verified fake for `IRangeCoverage` (HLD §10.3).

**Who needs it.** Two backtest coordinators ask whether a date range is
complete enough to run on, and `IRangeCoverage` is a *foreign* port to both,
so `Mock(spec=IRangeCoverage)` is not an option —
`test_no_foreign_port_is_mocked.py` fails on it, and `BUG-072` is what a
loose stand-in cost here already: a mock's response envelope reached a Qt
signal typed `object` and crashed the interpreter marshalling it.

**Scripted, not computed, and that is the honest shape.** This fake answers
what a test tells it to. It does not re-derive coverage from candles,
because the arithmetic lives in `coverage_builders.py` — inside the module,
where HLD §3.4 puts it ("a consumer imports the answer, never the
arithmetic") — and a `contracts/` fake reaching into `application/` for it
would invert the module's one direction. A second, hand-written copy of that
arithmetic would be worse: the consumers under test do not compute coverage,
they *render* it, so what their tests need is the ability to say "answer
this" and check what the screen then shows.

What the contract suite next door still pins for both implementations is the
part a script cannot fake away: an untouched range answers with a real
`BacktestRangeCoverage` saying nothing is stored, never `None` and never an
envelope.

**It refuses an impossible script.** `answer_with()` rejects a sample longer
than `MAX_REPORTED_MISSING_OPENS`, because the real path truncates to it —
a test that scripted five missing opens would be asserting against an answer
production cannot produce.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.backtest_range_coverage import (
    MAX_REPORTED_MISSING_OPENS,
    BacktestRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_range_coverage import (
    IRangeCoverage,
)

#: What an implementation answers for a range it has nothing stored for. The
#: shape matters to a screen: bounds `None` means "nothing here", which it
#: must render differently from "some of it is missing".
NOTHING_STORED = BacktestRangeCoverage(
    is_fully_covered=False,
    first_open_time=None,
    last_open_time=None,
    expected_candles=0,
    actual_candles=0,
    duplicate_candles=0,
    missing_open_times=(),
    has_unclosed_candle=False,
)


def fully_covered(
    first_open: datetime, last_open: datetime, candles: int
) -> BacktestRangeCoverage:
    """The answer for a range that is complete — the common scripted case."""
    return BacktestRangeCoverage(
        is_fully_covered=True,
        first_open_time=first_open,
        last_open_time=last_open,
        expected_candles=candles,
        actual_candles=candles,
        duplicate_candles=0,
        missing_open_times=(),
        has_unclosed_candle=False,
    )


@dataclass(frozen=True, slots=True)
class CoverageRequest:
    """One `coverage()` call, as the caller made it."""

    symbol: str
    interval: TimeFrame
    start_time: datetime | None
    end_time: datetime
    now: datetime


class FakeRangeCoverage(IRangeCoverage):
    """Coverage answers a test scripts, and a record of what was asked."""

    def __init__(self) -> None:
        self._answers: dict[tuple[str, TimeFrame], BacktestRangeCoverage] = {}
        #: Every call, in order. A consumer's test asserts "the screen asked
        #: about the range the user picked" against this — a fact about the
        #: screen, which no scripted answer can show.
        self.requests: list[CoverageRequest] = []

    def coverage(
        self,
        symbol: str,
        interval: TimeFrame,
        *,
        start_time: datetime | None,
        end_time: datetime,
        now: datetime,
    ) -> BacktestRangeCoverage:
        self.requests.append(
            CoverageRequest(
                symbol=symbol,
                interval=interval,
                start_time=start_time,
                end_time=end_time,
                now=now,
            )
        )
        return self._answers.get((symbol, interval), NOTHING_STORED)

    # -- what a consumer's test usually wants to know ------------------------

    def answer_with(
        self,
        coverage: BacktestRangeCoverage,
        *,
        symbol: str = "BTCUSDT",
        interval: TimeFrame = TimeFrame.ONE_MINUTE,
    ) -> None:
        """Script the answer for one symbol and timeframe."""
        if len(coverage.missing_open_times) > MAX_REPORTED_MISSING_OPENS:
            raise ValueError(
                "missing_open_times is a sample truncated to "
                f"{MAX_REPORTED_MISSING_OPENS}; a longer one cannot come from "
                "the real path, so a test asserting on it would be asserting "
                "against an answer production never produces"
            )
        self._answers[(symbol, interval)] = coverage

    def was_asked_about(self, symbol: str, interval: TimeFrame | None = None) -> bool:
        """Whether any call asked about this symbol (optionally at one
        timeframe)."""
        return any(
            request.symbol == symbol
            and (interval is None or request.interval == interval)
            for request in self.requests
        )
