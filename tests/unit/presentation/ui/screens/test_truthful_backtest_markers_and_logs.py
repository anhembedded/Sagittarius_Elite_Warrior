from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.chart_canvas_view import (
    _LONG_ENTRY_LABEL,
    _LONG_EXIT_LABEL,
    TradeMarkerType,
    trade_flag_markers,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.trade_log_filter import (
    TradeLogFilter,
    filter_trade_log_rows,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.trade_log_row import (
    build_trade_log_rows,
)

_T0 = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
_T2 = datetime(2026, 1, 1, 14, 0, tzinfo=UTC)
_T3 = datetime(2026, 1, 1, 16, 0, tzinfo=UTC)


def _sample_backtest_result() -> BacktestResult:
    trade1 = Trade(
        symbol="BTCUSDT",
        entry_time=_T0,
        entry_price=50000.0,
        exit_time=_T1,
        exit_price=52000.0,
        quantity=0.1,
        pnl=200.0,
        pnl_percent=4.0,
        fees_paid=5.0,
    )
    trade2 = Trade(
        symbol="BTCUSDT",
        entry_time=_T2,
        entry_price=51000.0,
        exit_time=_T3,
        exit_price=49500.0,
        quantity=0.1,
        pnl=-150.0,
        pnl_percent=-2.94,
        fees_paid=5.0,
    )
    trades = [trade1, trade2]
    curve = [(_T0, 10000.0), (_T1, 10200.0), (_T2, 10200.0), (_T3, 10050.0)]
    metrics = BacktestMetrics.compute(trades, curve, 10000.0)
    return BacktestResult(
        symbol="BTCUSDT",
        initial_balance=10000.0,
        final_balance=10050.0,
        trades=trades,
        equity_curve=curve,
        metrics=metrics,
    )


def test_trade_marker_semantics_are_explicitly_modeled():
    # BOT-096: Enum defines domain semantics for execution markers
    assert TradeMarkerType.LONG_ENTRY == "LONG_ENTRY"
    assert TradeMarkerType.LONG_EXIT == "LONG_EXIT"
    assert TradeMarkerType.SHORT_ENTRY == "SHORT_ENTRY"
    assert TradeMarkerType.SHORT_EXIT == "SHORT_EXIT"


def test_trade_markers_reflect_long_only_execution_truth():
    result = _sample_backtest_result()
    markers = trade_flag_markers(result)

    # 2 trades -> 4 markers (2 entries, 2 exits)
    assert len(markers) == 4

    # First trade: entry and exit
    entry1_x, entry1_y, entry1_label, entry1_color, entry1_dir = markers[0]
    exit1_x, exit1_y, exit1_label, exit1_color, exit1_dir = markers[1]

    assert entry1_x == _T0.timestamp()
    assert entry1_y == 50000.0
    assert entry1_label == _LONG_ENTRY_LABEL
    assert entry1_color == BULL_COLOR
    assert entry1_dir == "up"

    assert exit1_x == _T1.timestamp()
    assert exit1_y == 52000.0
    assert exit1_label == _LONG_EXIT_LABEL
    assert exit1_color == BEAR_COLOR
    assert exit1_dir == "down"

    # Exit label must never confuse the user by claiming to be a SHORT entry
    assert "SHORT" not in exit1_label.upper()
    assert "SELL" not in exit1_label.upper()
    assert "ĐÓNG" in exit1_label or "EXIT" in exit1_label


def test_short_filter_truthfully_returns_empty_in_long_only_engine():
    result = _sample_backtest_result()
    rows = build_trade_log_rows(result.trades)

    long_rows = filter_trade_log_rows(rows, TradeLogFilter.LONG)
    short_rows = filter_trade_log_rows(rows, TradeLogFilter.SHORT)

    assert len(long_rows) == 2
    assert len(short_rows) == 0
