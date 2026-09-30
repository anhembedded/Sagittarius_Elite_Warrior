"""`EPIC-028E` — cuts a venue's history into ADR O5 pages, newest first.

@details Shared by `GetOrderHistoryQueryHandler` and
`GetTradeHistoryQueryHandler`: both read every row the reader returns for the
span, sort newest first by a stable key, and hand back one page with the total
so a screen can say "page 2 of 7". Each page request reads the span again;
a caching decorator behind `IAccountHistoryReader` is the place to change that
if paging ever proves slow (the port's own extension list).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HISTORY_PAGE_SIZE,
    HistoryPage,
)


@dataclass(frozen=True)
class PageRequest:
    """Which page, and which symbols the rows were read from."""

    page: int
    scanned_symbols: tuple[str, ...]


def newest_first_page[T](
    rows: Iterable[T], sort_key: Callable[[T], Any], request: PageRequest
) -> HistoryPage[T]:
    """@return Page `request.page` of `rows`, newest first; empty rows past
    the last page, with the true total."""
    ordered = sorted(rows, key=sort_key, reverse=True)
    start = request.page * HISTORY_PAGE_SIZE
    return HistoryPage(
        rows=tuple(ordered[start : start + HISTORY_PAGE_SIZE]),
        page=request.page,
        total_rows=len(ordered),
        scanned_symbols=request.scanned_symbols,
    )
