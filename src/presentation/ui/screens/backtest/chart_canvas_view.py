from __future__ import annotations

from datetime import datetime
from enum import Enum

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_card import (
    OhlcCandle,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.marker_layer import (
    MarkerPoint,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)

_ENTRY_LABEL = "▲"
_EXIT_LABEL = "▼"


class ChartDisplayMode(str, Enum):
    """The Backtest Screen's 3 chart modes (BOT-056 §2.1)."""

    OHLC = "ohlc"
    EQUITY = "equity"
    BOTH = "both"


def equity_curve_to_candles(
    equity_curve: list[tuple[datetime, float]],
) -> list[OhlcCandle]:
    """
    @brief Turns the equity curve into `ChartCard`'s existing OHLC tuple
    format (open=high=low=close=equity), so the "Đường Vốn (Equity)" mode can
    reuse `ChartCard.set_chart_type("line")` unmodified instead of teaching
    `ChartCard` a second, unrelated kind of line series.
    """
    return [
        (equity_time.timestamp(), equity, equity, equity, equity)
        for equity_time, equity in equity_curve
    ]


def equity_curve_to_line_data(
    equity_curve: list[tuple[datetime, float]],
) -> tuple[list[float], list[float]]:
    """@brief (x, y) series for the equity subplot in "Song song" mode, via
    `ChartCard.add_subplot_indicator`/`update_indicator_data`."""
    x_data = [equity_time.timestamp() for equity_time, _ in equity_curve]
    y_data = [equity for _, equity in equity_curve]
    return x_data, y_data


def trade_flag_markers(result: BacktestResult) -> list[MarkerPoint]:
    """
    @brief Buy/Sell flags at every trade's entry/exit (BOT-056 §2.2), drawn
    via the existing `ChartCard.set_script_markers` (BOT-032 infra) — no new
    marker rendering added.
    @details Colored by entry/exit role (Buy always bullish-green, Sell
    always bearish-red — TradingView's own convention), not by whether that
    particular trade ended up profitable; a losing trade still opened with a
    real Buy and closed with a real Sell.
    """
    markers: list[MarkerPoint] = []
    for trade in result.trades:
        markers.append(
            (
                trade.entry_time.timestamp(),
                trade.entry_price,
                _ENTRY_LABEL,
                BULL_COLOR,
                "up",
            )
        )
        markers.append(
            (
                trade.exit_time.timestamp(),
                trade.exit_price,
                _EXIT_LABEL,
                BEAR_COLOR,
                "down",
            )
        )
    return markers
