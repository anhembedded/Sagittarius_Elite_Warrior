"""`calculate_monthly_returns`/`calculate_yearly_returns` — the two series
behind the monthly/annual returns heatmap `BOT-106C` describes.

@details Grouping is by calendar month/year of each `equity_curve` point's
own timestamp (already UTC — `BOT-097`'s invariant; display-timezone
conversion, if any, is presentation-only and out of scope here, same as
`drawdown_series_calculator.py`). A month's return is measured from the
equity carried in from the previous month (or `initial_balance` for the
first month the curve touches) to the last equity point inside that month —
never from that month's first point, which would silently drop whatever the
position was already worth entering the month.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MonthlyReturn:
    year: int
    month: int  #: 1-12
    return_percent: float


@dataclass(frozen=True)
class YearlyReturn:
    year: int
    #: Keyed by month (1-12); a month the equity curve never reached that
    #: year is simply absent, not zero — the heatmap must tell "no data" from
    #: "flat month" apart.
    months: dict[int, float]
    ytd_return_percent: float


def _percent_change(start: float, end: float) -> float:
    return (end - start) / start * 100 if start else 0.0


def calculate_monthly_returns(
    equity_curve: list[tuple[datetime, float]],
    initial_balance: float,
) -> list[MonthlyReturn]:
    """One entry per calendar month the curve spans, in chronological order."""
    if not equity_curve:
        return []

    results: list[MonthlyReturn] = []
    carried_in_equity = initial_balance
    current_key = (equity_curve[0][0].year, equity_curve[0][0].month)
    last_equity_in_month = initial_balance

    for time, equity in equity_curve:
        key = (time.year, time.month)
        if key != current_key:
            year, month = current_key
            results.append(
                MonthlyReturn(
                    year=year,
                    month=month,
                    return_percent=_percent_change(
                        carried_in_equity, last_equity_in_month
                    ),
                )
            )
            carried_in_equity = last_equity_in_month
            current_key = key
        last_equity_in_month = equity

    year, month = current_key
    results.append(
        MonthlyReturn(
            year=year,
            month=month,
            return_percent=_percent_change(carried_in_equity, last_equity_in_month),
        )
    )
    return results


def calculate_yearly_returns(
    monthly_returns: list[MonthlyReturn],
) -> list[YearlyReturn]:
    """One entry per year present in `monthly_returns`, `ytd_return_percent`
    the compounded return of every month recorded for that year so far —
    exact for a year still in progress, since it only compounds the months
    that actually happened."""
    years: dict[int, dict[int, float]] = {}
    for entry in monthly_returns:
        years.setdefault(entry.year, {})[entry.month] = entry.return_percent

    results: list[YearlyReturn] = []
    for year in sorted(years):
        months = years[year]
        compounded = math.prod(1.0 + months[month] / 100 for month in sorted(months))
        results.append(
            YearlyReturn(
                year=year,
                months=dict(months),
                ytd_return_percent=(compounded - 1.0) * 100,
            )
        )
    return results
