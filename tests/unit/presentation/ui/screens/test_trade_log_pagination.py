from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.trade_log_pagination import (
    clamp_page,
    paginate_trade_log_rows,
    total_pages,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.trade_log_row import (
    TradeLogRow,
)

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _rows(count: int) -> list[TradeLogRow]:
    return [
        TradeLogRow(i, _T0, 100.0, _T0, 100.0, 1.0, 0.0, 0.0)
        for i in range(1, count + 1)
    ]


def test_total_pages_of_zero_rows_is_one():
    assert total_pages(0, page_size=20) == 1


def test_total_pages_rounds_up():
    assert total_pages(41, page_size=20) == 3
    assert total_pages(40, page_size=20) == 2


def test_clamp_page_never_goes_below_1():
    assert clamp_page(0, row_count=10, page_size=20) == 1
    assert clamp_page(-5, row_count=10, page_size=20) == 1


def test_clamp_page_never_exceeds_total_pages():
    assert clamp_page(99, row_count=10, page_size=20) == 1
    assert clamp_page(99, row_count=41, page_size=20) == 3


def test_paginate_returns_the_requested_slice():
    rows = _rows(45)

    page_1 = paginate_trade_log_rows(rows, page=1, page_size=20)
    page_2 = paginate_trade_log_rows(rows, page=2, page_size=20)
    page_3 = paginate_trade_log_rows(rows, page=3, page_size=20)

    assert [row.index for row in page_1] == list(range(1, 21))
    assert [row.index for row in page_2] == list(range(21, 41))
    assert [row.index for row in page_3] == list(range(41, 46))


def test_paginate_clamps_an_out_of_range_page():
    rows = _rows(5)

    page = paginate_trade_log_rows(rows, page=99, page_size=20)

    assert [row.index for row in page] == [1, 2, 3, 4, 5]
