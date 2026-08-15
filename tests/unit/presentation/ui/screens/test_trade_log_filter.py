from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.trade_log_filter import (
    TradeLogFilter,
    filter_trade_log_rows,
    search_trade_log_rows,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.trade_log_row import (
    TradeLogRow,
)

_T0 = datetime(2026, 1, 1, 6, 0, tzinfo=UTC)
_T1 = datetime(2026, 3, 15, 18, 0, tzinfo=UTC)


def _row(index: int, pnl: float, entry_time=_T0, exit_time=_T1) -> TradeLogRow:
    return TradeLogRow(index, entry_time, 100.0, exit_time, 100.0 + pnl, 1.0, pnl, pnl)


def test_filter_all_returns_every_row():
    rows = [_row(1, 10.0), _row(2, -5.0)]

    assert filter_trade_log_rows(rows, TradeLogFilter.ALL) == rows


def test_filter_long_returns_every_row_since_the_engine_is_long_only():
    rows = [_row(1, 10.0), _row(2, -5.0)]

    assert filter_trade_log_rows(rows, TradeLogFilter.LONG) == rows


def test_filter_short_is_always_empty_until_bot_050():
    rows = [_row(1, 10.0), _row(2, -5.0)]

    assert filter_trade_log_rows(rows, TradeLogFilter.SHORT) == []


def test_filter_win_keeps_only_positive_pnl():
    rows = [_row(1, 10.0), _row(2, -5.0), _row(3, 0.0)]

    filtered = filter_trade_log_rows(rows, TradeLogFilter.WIN)

    assert [row.index for row in filtered] == [1]


def test_filter_loss_keeps_only_negative_pnl():
    rows = [_row(1, 10.0), _row(2, -5.0), _row(3, 0.0)]

    filtered = filter_trade_log_rows(rows, TradeLogFilter.LOSS)

    assert [row.index for row in filtered] == [2]


def test_search_empty_query_returns_every_row():
    rows = [_row(1, 10.0), _row(2, -5.0)]

    assert search_trade_log_rows(rows, "") == rows
    assert search_trade_log_rows(rows, "   ") == rows


def test_search_matches_the_display_index():
    rows = [_row(1, 10.0), _row(216, -5.0)]

    matched = search_trade_log_rows(rows, "216")

    assert [row.index for row in matched] == [216]


def test_search_matches_entry_or_exit_date():
    rows = [
        _row(1, 10.0, entry_time=datetime(2026, 1, 1, tzinfo=UTC)),
        _row(2, -5.0, entry_time=datetime(2026, 6, 1, tzinfo=UTC)),
    ]

    matched = search_trade_log_rows(rows, "2026-01")

    assert [row.index for row in matched] == [1]


def test_search_is_case_insensitive_and_matches_no_one_when_nothing_fits():
    rows = [_row(1, 10.0)]

    assert search_trade_log_rows(rows, "nonexistent-query") == []
