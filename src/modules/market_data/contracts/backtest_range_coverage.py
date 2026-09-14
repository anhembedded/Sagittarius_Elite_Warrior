"""What `GetBacktestRangeCoverageQuery` answers with — a published type.

"Is this symbol/timeframe/date range complete enough to backtest on?" is a
market_data question, but the caller is the Backtest screen, which must render
*why* a range was rejected rather than only that it was. So the answer is a
value object with the diagnosis in it, not a boolean.

Published rather than internal: this is the one shape that crosses the module's
edge (`backtesting`'s UI reads every field to build its warning), while the two
functions that *produce* it stay inside the module, in
`application/queries/get_backtest_range_coverage/coverage_builders.py`. A
consumer imports the answer; it does not import how the answer is computed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

#: How many missing candle opens a report carries. A year of 1-minute candles
#: with a wide gap has hundreds of thousands of them; a reader needs enough to
#: recognise *where* history breaks, and `expected_candles` minus
#: `actual_candles` already says how many there are in total.
MAX_REPORTED_MISSING_OPENS = 3


@dataclass(frozen=True)
class BacktestRangeCoverage:
    """Coverage of a half-open interval `[start, end)`, with the diagnosis.

    `is_fully_covered` is the verdict; every other field exists so the caller
    can say what is wrong instead of only that something is. `first_open_time`
    and `last_open_time` are `None` when the range holds no candle at all —
    distinct from a range whose bounds are known but whose middle has holes.

    `missing_open_times` is truncated to `MAX_REPORTED_MISSING_OPENS`; it is a
    sample, never a complete list, so code must not treat its length as the
    number of missing candles.
    """

    is_fully_covered: bool
    first_open_time: datetime | None
    last_open_time: datetime | None
    expected_candles: int
    actual_candles: int
    duplicate_candles: int
    missing_open_times: tuple[datetime, ...]
    has_unclosed_candle: bool
