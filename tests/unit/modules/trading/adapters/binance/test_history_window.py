"""`EPIC-028E` — `fetch_span` reads a span within the endpoint's limits and
never lets the row cap cut a window short.

@details The endpoint is a small in-memory stand-in that behaves like
Binance: it refuses a window longer than its span limit and returns at most
`limit` rows, oldest first. Every test checks what came back against the
rows that exist.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.history_window import (
    HistoryWindowRules,
    HistoryWindowTooDenseError,
    fetch_span,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)


class _Endpoint:
    """Rows at the given millisecond timestamps, served like Binance."""

    def __init__(self, rows_ms: list[int], rules: HistoryWindowRules) -> None:
        self._rows = sorted(rows_ms)
        self._rules = rules
        self.windows: list[tuple[int, int]] = []

    def __call__(self, start: int, end: int) -> list[int]:
        assert end - start + 1 <= self._rules.max_span_ms, "span over the limit"
        self.windows.append((start, end))
        return [ms for ms in self._rows if start <= ms <= end][: self._rules.limit]


def test_a_long_span_is_read_in_windows_no_longer_than_the_limit() -> None:
    rules = HistoryWindowRules(max_span_ms=100, limit=10)
    endpoint = _Endpoint([5, 150, 299], rules)

    rows = fetch_span(endpoint, 0, 299, rules)

    assert rows == [5, 150, 299]
    assert endpoint.windows == [(0, 99), (100, 199), (200, 299)]


def test_windows_neither_overlap_nor_leave_a_gap_at_their_edges() -> None:
    """Both ends are inclusive: a row exactly on a boundary is read once."""
    rules = HistoryWindowRules(max_span_ms=100, limit=10)
    endpoint = _Endpoint([99, 100, 199, 200], rules)

    assert fetch_span(endpoint, 0, 250, rules) == [99, 100, 199, 200]


def test_a_full_window_is_split_until_every_row_is_read() -> None:
    rules = HistoryWindowRules(max_span_ms=1000, limit=3)
    rows_ms = [1, 2, 3, 4, 5, 6, 7, 500, 900]
    endpoint = _Endpoint(rows_ms, rules)

    assert fetch_span(endpoint, 0, 999, rules) == rows_ms


def test_a_window_one_row_short_of_the_limit_is_not_split() -> None:
    rules = HistoryWindowRules(max_span_ms=1000, limit=3)
    endpoint = _Endpoint([1, 2], rules)

    fetch_span(endpoint, 0, 999, rules)

    assert endpoint.windows == [(0, 999)]


def test_a_millisecond_holding_a_full_page_raises_rather_than_drops_rows() -> None:
    rules = HistoryWindowRules(max_span_ms=1000, limit=2)
    endpoint = _Endpoint([7, 7, 7], rules)

    with pytest.raises(HistoryWindowTooDenseError):
        fetch_span(endpoint, 0, 999, rules)


def test_the_dense_error_is_the_readers_one_failure_type() -> None:
    assert issubclass(HistoryWindowTooDenseError, AccountHistoryUnavailableError)


def test_a_span_that_ends_before_it_starts_asks_for_nothing() -> None:
    rules = HistoryWindowRules(max_span_ms=100, limit=10)
    endpoint = _Endpoint([5], rules)

    assert fetch_span(endpoint, 50, 10, rules) == []
    assert endpoint.windows == []
