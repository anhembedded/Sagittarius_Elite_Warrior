"""`EPIC-028J` — what a history tab shows for one `HistoryPage`: its rows,
where the page sits, which pairs it read and what the venue cannot show.

@details The scope line is finding 3 of the PR 297 review made visible:
Binance reads a history one pair at a time, so "every pair" is the pairs the
venue can name as active (`IAccountHistoryReader.active_symbols`), and a tab
must say which they are rather than imply it is the whole account. The
notices are `HistoryPage.notices` (`EPIC-028Q`), shown beside the rows, never
in a tooltip.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HistoryPage,
)


class HistoryKind(str, Enum):
    """Which of a desk's two history tabs."""

    ORDERS = "orders"
    TRADES = "trades"


@dataclass(frozen=True)
class HistoryView[TRow]:
    """One page of a history tab, ready to render."""

    rows: tuple[TRow, ...]
    #: Zero-based.
    page: int
    #: `0` when the history is empty.
    page_count: int
    scope_text: str
    notices: tuple[str, ...]

    @property
    def has_previous(self) -> bool:
        return self.page > 0

    @property
    def has_next(self) -> bool:
        return self.page + 1 < self.page_count

    @property
    def page_text(self) -> str:
        if self.page_count == 0:
            return "No rows"
        return f"Page {self.page + 1} of {self.page_count}"


def history_view_for[TRecord, TRow](
    page: HistoryPage[TRecord], build_row: Callable[[TRecord], TRow]
) -> HistoryView[TRow]:
    return HistoryView(
        rows=tuple(build_row(record) for record in page.rows),
        page=page.page,
        page_count=page.page_count,
        scope_text=scope_text_for(page.scanned_symbols),
        notices=page.notices,
    )


def scope_text_for(scanned_symbols: tuple[str, ...]) -> str:
    """Names the pairs a page read; one pair when "hide other pairs" is on."""
    if len(scanned_symbols) == 1:
        return f"Showing {scanned_symbols[0]}."
    if not scanned_symbols:
        return (
            "No pair to read: the account holds nothing, has no open order "
            "and the venue names no pair traded in this span."
        )
    return (
        f"Pairs read: {', '.join(scanned_symbols)}. Binance reads a history "
        "one pair at a time, so a pair outside this list is not shown."
    )
