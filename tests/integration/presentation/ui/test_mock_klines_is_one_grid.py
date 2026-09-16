"""`BUG-123` — the mocked candle series must be **one** grid per process.

Every Dev Board history test seeds `mock_klines.build_mock_klines()` for five
symbols in a fixture, and the load-more tests then call it a *second* time in
the test body to work out which page sits immediately below what the screen is
already showing. While the anchor was `datetime.now()` read on every call, a
minute rolling over between those two calls shifted the second grid one minute
later, the "older" page's newest row landed exactly on the row the chart
already held, and only four of five candles were new — `assert 9 == (5 + 5)`,
once in roughly every sixty seconds of gate wall-clock.

So this file does not test a screen. It tests the shared builder's one
promise: **any two callers in the same process get the same grid**, whatever
the clock does between them. Two calls that disagree are the defect; five
symbols that disagree are the same defect seeding a store the tests then
compare across symbols.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.tests.integration.presentation.ui import mock_klines
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.mock_klines import (
    SEEDED_SYMBOLS,
    build_mock_klines,
)


class _RollingClock:
    """`now()` jumps a minute on every call — a minute boundary crossed
    between two reads, made deterministic instead of waited for."""

    def __init__(self) -> None:
        self._instant = datetime(2026, 9, 16, 1, 39, 59, tzinfo=UTC)

    def now(self, tz: object = None) -> datetime:
        instant = self._instant
        self._instant = self._instant + timedelta(minutes=1)
        return instant


def test_two_calls_in_one_process_return_the_same_grid(monkeypatch) -> None:
    """The exact shape of `BUG-123`: the fixture seeds the store, the test
    body later derives "the page below the oldest row shown" from a second
    call, and the two have to agree on where the grid starts."""
    monkeypatch.setattr(mock_klines, "datetime", _RollingClock())

    first = [candle.open_time for candle in build_mock_klines("ETHUSDT")]
    second = [candle.open_time for candle in build_mock_klines("ETHUSDT")]

    assert first == second, (
        "the mocked series moved between two calls in the same process — a "
        "page derived from the second call is no longer adjacent to what the "
        "first one put in the store"
    )


def test_every_seeded_symbol_lands_on_the_same_grid(monkeypatch) -> None:
    """`seeded_history` loops `SEEDED_SYMBOLS` in one fixture, so the same
    defect could also leave two symbols a minute apart inside one store —
    silently, because each symbol reads consistently on its own."""
    monkeypatch.setattr(mock_klines, "datetime", _RollingClock())

    grids = {
        symbol: [candle.open_time for candle in build_mock_klines(symbol)]
        for symbol in SEEDED_SYMBOLS
    }

    assert len(set(map(tuple, grids.values()))) == 1, (
        f"the seeded symbols do not share one grid: "
        f"{ {symbol: rows[0] for symbol, rows in grids.items()} }"
    )


def test_the_series_still_ends_in_the_past() -> None:
    """Why the anchor may be frozen at all: the builder's own reason for
    reading the clock was to stay inside a recent-window default while never
    claiming a candle from the future. A grid fixed once per process keeps
    both — it only ever gets older as the session runs."""
    newest = build_mock_klines("ETHUSDT")[0]

    assert newest.close_time <= datetime.now(UTC)
