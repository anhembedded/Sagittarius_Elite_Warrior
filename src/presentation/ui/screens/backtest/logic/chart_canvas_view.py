from __future__ import annotations

from datetime import datetime
from enum import Enum

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
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


class TradeMarkerType(str, Enum):
    """
    Semantic execution marker types for Backtest chart (BOT-096 / BOT-050).
    Distinguishes Long entries and exits from Short entries and exits.
    """

    LONG_ENTRY = "LONG_ENTRY"
    LONG_EXIT = "LONG_EXIT"
    SHORT_ENTRY = "SHORT_ENTRY"
    SHORT_EXIT = "SHORT_EXIT"


_LONG_ENTRY_LABEL = "MUA (LONG)"
_LONG_EXIT_LABEL = "ĐÓNG LONG"
_SHORT_ENTRY_LABEL = "BÁN (SHORT)"
_SHORT_EXIT_LABEL = "ĐÓNG SHORT"


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
    @brief Trade entry and exit flags at every trade's entry/exit (BOT-056 / BOT-096 / BOT-050),
    drawn via the chart marker layer.
    @details
    - For LONG trades:
      - Entry: 'MUA (LONG)' (bullish green, pointing up ▲).
      - Exit: 'ĐÓNG LONG' (bearish red, pointing down ▼).
    - For SHORT trades:
      - Entry: 'BÁN (SHORT)' (bearish red, pointing down ▼).
      - Exit: 'ĐÓNG SHORT' (bullish green, pointing up ▲).
    """
    markers: list[MarkerPoint] = []
    for trade in result.trades:
        if trade.side == PositionSide.SHORT:
            markers.append(
                (
                    trade.entry_time.timestamp(),
                    trade.entry_price,
                    _SHORT_ENTRY_LABEL,
                    BEAR_COLOR,
                    "down",
                )
            )
            markers.append(
                (
                    trade.exit_time.timestamp(),
                    trade.exit_price,
                    _SHORT_EXIT_LABEL,
                    BULL_COLOR,
                    "up",
                )
            )
        else:
            markers.append(
                (
                    trade.entry_time.timestamp(),
                    trade.entry_price,
                    _LONG_ENTRY_LABEL,
                    BULL_COLOR,
                    "up",
                )
            )
            markers.append(
                (
                    trade.exit_time.timestamp(),
                    trade.exit_price,
                    _LONG_EXIT_LABEL,
                    BEAR_COLOR,
                    "down",
                )
            )
    return markers
