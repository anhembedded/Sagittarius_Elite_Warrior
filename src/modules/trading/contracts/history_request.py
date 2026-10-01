"""`EPIC-028J` — which page of a venue's history a desk asks for.

@details `since` is fixed when a desk opens a history and kept while the
user pages through it: `CachedAccountHistoryReader` serves a repeated span
from its cache only for the same or a later `since`, so a desk that moved
`since` on every page click would re-read the exchange each time
(`EPIC-028Q`).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime


@dataclass(frozen=True)
class HistoryRequest:
    """One page of one history, for one pair or every active one."""

    #: One symbol, or `None` for every symbol the venue names as active.
    symbol: str | None
    #: The oldest moment to include; timezone-aware.
    since: datetime
    #: Zero-based.
    page: int = 0

    def __post_init__(self) -> None:
        if self.since.tzinfo is None:
            raise ValueError("since must be timezone-aware")
        if self.page < 0:
            raise ValueError(f"page must be zero or more, got {self.page}")

    def at_page(self, page: int) -> HistoryRequest:
        """The same history and span, another page."""
        return replace(self, page=page)
