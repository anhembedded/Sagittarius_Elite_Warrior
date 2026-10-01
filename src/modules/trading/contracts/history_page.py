"""`EPIC-028E` — one page of an account history, newest first (ADR O5).

@details `scanned_symbols` says which pairs the rows come from. Binance's
order and trade history endpoints need a symbol, so "every pair" means every
pair the venue could name as active (`IAccountHistoryReader.active_symbols`);
a pair the venue cannot name is not among them. Carrying the list lets a
screen say what it is showing instead of implying it is everything.
`notices` carries the venue's `HistoryGaps` for the same reason (`EPIC-028Q`).
"""

from __future__ import annotations

from dataclasses import dataclass

#: ADR O5: fifty rows a page.
HISTORY_PAGE_SIZE = 50


@dataclass(frozen=True)
class HistoryPage[T]:
    """Up to `HISTORY_PAGE_SIZE` rows, newest first, and where they sit."""

    rows: tuple[T, ...]
    #: Zero-based.
    page: int
    #: Rows across every page; `0` when the history is empty.
    total_rows: int
    scanned_symbols: tuple[str, ...]
    #: What this history cannot show, in words a desk displays beside it
    #: (`HistoryGaps`); empty when the venue states no gap.
    notices: tuple[str, ...] = ()

    @property
    def page_count(self) -> int:
        return -(-self.total_rows // HISTORY_PAGE_SIZE)
