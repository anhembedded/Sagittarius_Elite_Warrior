from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.chart_card import (
    OhlcCandle,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.marker_layer import (
    MarkerPoint,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
    TAKE_PROFIT_COLOR,
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


_LONG_ENTRY_LABEL = "BUY (LONG)"
_LONG_EXIT_LABEL = "CLOSE LONG"
_LONG_EXIT_TP_LABEL = "CLOSE LONG (TP)"
_SHORT_ENTRY_LABEL = "SELL (SHORT)"
_SHORT_EXIT_LABEL = "CLOSE SHORT"
_SHORT_EXIT_TP_LABEL = "CLOSE SHORT (TP)"


class ChartDisplayMode(str, Enum):
    """The Backtest Screen's 3 chart modes (BOT-056 §2.1)."""

    OHLC = "ohlc"
    EQUITY = "equity"
    BOTH = "both"


class MarkerOutcomeFilter(str, Enum):
    """PROP-004 — which trade outcomes get an entry/exit marker pair drawn.
    A separate axis from `MarkerSideFilter` (combinable), unlike
    `trade_log_filter.TradeLogFilter`'s 5 mutually-exclusive tabs — the
    proposal's own acceptance bar wants outcome and side picked
    independently."""

    ALL = "ALL"
    WINS_ONLY = "WINS_ONLY"
    LOSSES_ONLY = "LOSSES_ONLY"


class MarkerSideFilter(str, Enum):
    """PROP-004 — which position side gets an entry/exit marker pair drawn."""

    ALL = "ALL"
    LONG_ONLY = "LONG_ONLY"
    SHORT_ONLY = "SHORT_ONLY"


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
    return trade_flag_markers_for_trades(result.trades)


def trade_flag_markers_for_trades(trades: Sequence[Trade]) -> list[MarkerPoint]:
    """The part of `trade_flag_markers()` that doesn't need a whole
    `BacktestResult` — split out so PROP-004's marker filters can build
    markers from an already-filtered trade list without faking one up."""
    markers: list[MarkerPoint] = []
    for trade in trades:
        is_short = trade.side is PositionSide.SHORT
        markers.append(_entry_marker(trade, is_short))
        markers.append(_exit_marker(trade, is_short))
    return markers


def filter_trades_for_markers(
    trades: Sequence[Trade],
    *,
    outcome: MarkerOutcomeFilter,
    side: MarkerSideFilter,
    min_abs_pnl_percent: float,
) -> list[Trade]:
    """PROP-004 — narrows which trades get a marker pair drawn. Win/loss
    matches `trade_log_filter.filter_trade_log_rows()`'s own sign
    convention (`pnl > 0` is a win) so the two screens never disagree
    about which side of zero a trade falls on."""
    filtered: Sequence[Trade] = trades
    if outcome is MarkerOutcomeFilter.WINS_ONLY:
        filtered = [trade for trade in filtered if trade.pnl > 0]
    elif outcome is MarkerOutcomeFilter.LOSSES_ONLY:
        filtered = [trade for trade in filtered if trade.pnl <= 0]
    if side is MarkerSideFilter.LONG_ONLY:
        filtered = [trade for trade in filtered if trade.side is PositionSide.LONG]
    elif side is MarkerSideFilter.SHORT_ONLY:
        filtered = [trade for trade in filtered if trade.side is PositionSide.SHORT]
    if min_abs_pnl_percent > 0.0:
        filtered = [
            trade for trade in filtered if abs(trade.pnl_percent) >= min_abs_pnl_percent
        ]
    return list(filtered)


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
