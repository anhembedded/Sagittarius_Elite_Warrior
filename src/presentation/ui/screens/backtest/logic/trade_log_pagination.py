from __future__ import annotations

import math

from .trade_log_row import TradeLogRow

#: 44 trades in the mockup, "hàng nghìn" (thousands) called out as realistic
#: in BOT-057 §3 — a fixed page size keeps each QML render cheap regardless
#: of how many trades a run produced.
PAGE_SIZE = 20


def total_pages(row_count: int, page_size: int = PAGE_SIZE) -> int:
    if row_count == 0:
        return 1
    return math.ceil(row_count / page_size)


def clamp_page(page: int, row_count: int, page_size: int = PAGE_SIZE) -> int:
    """@brief Keeps `page` inside [1, total_pages] — callers pass whatever
    the ViewModel currently holds, which can go stale after a filter/search
    shrinks the row count out from under the previously-selected page."""
    return max(1, min(page, total_pages(row_count, page_size)))


def paginate_trade_log_rows(
    rows: list[TradeLogRow], page: int, page_size: int = PAGE_SIZE
) -> list[TradeLogRow]:
    clamped = clamp_page(page, len(rows), page_size)
    start = (clamped - 1) * page_size
    return rows[start : start + page_size]
