"""`EPIC-028E` — reads a time span from a Binance history endpoint in full.

@details Every Binance history endpoint this app reads takes `startTime` and
`endTime` (both inclusive, milliseconds), refuses a span longer than its own
limit, and returns at most `limit` rows. `fetch_span` turns one requested
span into requests the exchange accepts, and never lets the row cap cut a
window short:

1. a start older than the endpoint's `max_age_ms` is moved forward to it:
   Binance refuses a `startTime` more than seven days old with -4181 on
   Futures `allOrders` and `userTrades`, and a "now minus seven days"
   computed before the request leaves is that old when it arrives
   (`BUG-173`);
2. the span is cut into consecutive windows no longer than `max_span_ms`;
3. a window that comes back holding exactly `limit` rows may have had more,
   so it is split in two and each half is read again, down to a single
   millisecond. A millisecond that still fills a whole page cannot be split
   further, and `HistoryWindowTooDenseError` says so rather than dropping
   rows.

Pure and venue-free: the endpoint, the span limit and the row limit come in
from the adapter (`FuturesHistoryReader`: seven days, `SpotHistoryReader`:
twenty-four hours, both 1 000 rows).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)

#: Reads one window, `(start_ms, end_ms)` inclusive, and returns its rows.
type WindowFetch[T] = Callable[[int, int], list[T]]


class HistoryWindowTooDenseError(AccountHistoryUnavailableError):
    """One millisecond holds a full page of rows: nothing narrower can be
    asked for, and returning the page would silently drop the rest. An
    `AccountHistoryUnavailableError`, so a caller catches one type."""


@dataclass(frozen=True)
class HistoryWindowRules:
    """What one endpoint accepts per request."""

    max_span_ms: int
    limit: int
    #: How far back from `until_ms` a start may be, kept under the exchange's
    #: own limit by a margin for the request's travel time; `None` when the
    #: endpoint has no such limit (Spot).
    max_age_ms: int | None = None


def fetch_span[T](
    fetch: WindowFetch[T], since_ms: int, until_ms: int, rules: HistoryWindowRules
) -> list[T]:
    """@return Every row from `since_ms` to `until_ms`, oldest window first.
    @throws HistoryWindowTooDenseError See the module docstring."""
    rows: list[T] = []
    start = since_ms
    if rules.max_age_ms is not None:
        start = max(start, until_ms - rules.max_age_ms)
    while start <= until_ms:
        end = min(start + rules.max_span_ms - 1, until_ms)
        rows.extend(_fetch_window(fetch, start, end, rules.limit))
        start = end + 1
    return rows


def _fetch_window[T](
    fetch: WindowFetch[T], start: int, end: int, limit: int
) -> list[T]:
    batch = fetch(start, end)
    if len(batch) < limit:
        return batch
    if start == end:
        raise HistoryWindowTooDenseError(
            f"{len(batch)} rows at one millisecond ({start}) fill a whole page; "
            "the rest cannot be requested"
        )
    middle = (start + end) // 2
    return _fetch_window(fetch, start, middle, limit) + _fetch_window(
        fetch, middle + 1, end, limit
    )
