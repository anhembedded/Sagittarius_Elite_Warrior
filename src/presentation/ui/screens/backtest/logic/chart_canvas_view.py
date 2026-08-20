from __future__ import annotations

from datetime import datetime
from enum import Enum

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
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
    TAKE_PROFIT_COLOR,
)


class TradeMarkerType(str, Enum):
    """
    Semantic execution marker types for Backtest chart (BOT-096).
    Distinguishes Long entries and exits from Short entries and exits.
    """

    LONG_ENTRY = "LONG_ENTRY"
    LONG_EXIT = "LONG_EXIT"
    SHORT_ENTRY = "SHORT_ENTRY"
    SHORT_EXIT = "SHORT_EXIT"


_LONG_ENTRY_LABEL = "MUA (LONG)"
_LONG_EXIT_LABEL = "ĐÓNG LONG"
_LONG_EXIT_TP_LABEL = "ĐÓNG LONG (TP)"
_SHORT_ENTRY_LABEL = "BÁN (SHORT)"
_SHORT_EXIT_LABEL = "ĐÓNG SHORT"
_SHORT_EXIT_TP_LABEL = "ĐÓNG SHORT (TP)"


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
    @brief Entry/exit flags at every trade's entry/exit (BOT-056/BOT-096/
    BOT-111), drawn via the existing `ChartCard.set_script_markers`
    (BOT-032 infra).
    @details Side-aware (`trade.side`, BOT-050): a Long entry is labeled
    'MUA (LONG)' (bullish green, up), a Short entry 'BÁN (SHORT)' (bearish
    red, down) — never the ambiguous "Sell"/"Buy" alone, which could read as
    opening the opposite side. Exit labels/colors are additionally aware of
    `trade.exit_reason`: a take-profit exit (`PaperExchange`'s own
    intra-bar mechanism, BOT-041/BOT-104 — not a strategy decision) gets a
    distinct gold marker and a "(TP)" suffix, since it is a genuinely
    different kind of event from the strategy's own decide()-driven exit.
    Every other reason (a strategy signal, forced end-of-backtest close, a
    future stop-loss/liquidation) keeps the plain side-based exit label —
    deliberately generic, since "the strategy decided to exit" means
    something different per strategy (e.g. `EmaTrendPullbackStrategy`'s own
    touch-EMA condition is specific to that one strategy, not a universal
    "reason" this shared rendering code can name truthfully for every
    strategy).
    """
    markers: list[MarkerPoint] = []
    for trade in result.trades:
        is_short = trade.side is PositionSide.SHORT
        markers.append(_entry_marker(trade, is_short))
        markers.append(_exit_marker(trade, is_short))
    return markers


def _entry_marker(trade: Trade, is_short: bool) -> MarkerPoint:
    label = _SHORT_ENTRY_LABEL if is_short else _LONG_ENTRY_LABEL
    color = BEAR_COLOR if is_short else BULL_COLOR
    direction = "down" if is_short else "up"
    return (trade.entry_time.timestamp(), trade.entry_price, label, color, direction)


def _exit_marker(trade: Trade, is_short: bool) -> MarkerPoint:
    is_take_profit = trade.exit_reason is ExitReason.TAKE_PROFIT
    if is_take_profit:
        label = _SHORT_EXIT_TP_LABEL if is_short else _LONG_EXIT_TP_LABEL
        color = TAKE_PROFIT_COLOR
    else:
        label = _SHORT_EXIT_LABEL if is_short else _LONG_EXIT_LABEL
        color = BULL_COLOR if is_short else BEAR_COLOR
    direction = "up" if is_short else "down"
    return (trade.exit_time.timestamp(), trade.exit_price, label, color, direction)
