"""`BOT-106D` — shaping `BacktestResult` into what the drawdown underwater
chart and the monthly/yearly returns heatmap render.

@details Pure functions, no Qt: `calculate_drawdown_series()` and
`calculate_monthly_returns()`/`calculate_yearly_returns()` (`BOT-106C`) do
the actual math; this module only maps their output to the plain-dict shape
the two new widgets consume — same boundary convention as
`trade_log_row_to_qml()`/`stat_cards_to_qml()`.
"""

from __future__ import annotations

from typing import Any

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.drawdown_series_calculator import (
    calculate_drawdown_series,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.monthly_returns_calculator import (
    calculate_monthly_returns,
    calculate_yearly_returns,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)

_MONTHS_PER_YEAR = 12


def build_drawdown_chart_points(result: BacktestResult) -> list[dict[str, float]]:
    """One `{"t": epoch_seconds, "v": -drawdown_percent}` point per
    `equity_curve` point. Negated so the underwater area draws *below* the
    zero line — `calculate_drawdown_series()`'s own convention is a positive
    percent drop, which is correct for arithmetic but upside-down for a
    "how far underwater" area chart."""
    series = calculate_drawdown_series(result.equity_curve)
    return [
        {"t": time.timestamp(), "v": -drawdown_percent}
        for time, drawdown_percent in series
    ]


def _signed_percent(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:,.2f}%"


def _return_color(value: float) -> str:
    return BULL_COLOR if value >= 0 else BEAR_COLOR


def _month_cell(value: float | None) -> dict[str, str] | None:
    """`None` stays `None` — `YearlyReturn.months`' own contract is "a month
    the curve never reached is absent, not zero", and the heatmap must keep
    telling "no data" apart from "flat month" (`monthly_returns_calculator.py`
    docstring)."""
    if value is None:
        return None
    return {"text": _signed_percent(value), "color": _return_color(value)}


def build_yearly_returns_rows(result: BacktestResult) -> list[dict[str, Any]]:
    """One row per year the equity curve spans, oldest first: 12 month
    cells (`None` where that month has no data) plus a compounded
    year-to-date figure."""
    monthly = calculate_monthly_returns(result.equity_curve, result.initial_balance)
    yearly = calculate_yearly_returns(monthly)
    return [
        {
            "year": year_return.year,
            "months": [
                _month_cell(year_return.months.get(month))
                for month in range(1, _MONTHS_PER_YEAR + 1)
            ],
            "ytdText": _signed_percent(year_return.ytd_return_percent),
            "ytdColor": _return_color(year_return.ytd_return_percent),
        }
        for year_return in yearly
    ]
