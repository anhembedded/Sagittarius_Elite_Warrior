"""Candle-boundary arithmetic: snapping a timestamp to a timeframe's grid.

A candle does not open at an arbitrary instant. On a 15-minute timeframe the
opens are …:00, :15, :30, :45 and nothing in between, so "the last candle that
has closed by `now`" and "the first candle at or after `start`" are *rounding*
questions, not comparisons. Getting them wrong is how an off-by-one candle
enters a coverage report or a database query.

Domain, not a utility drawer: the grid is a market_data rule, it is expressed in
this context's own vocabulary (an *open time*), and it depends on nothing but
the standard library. `adapters/persistence/sqlalchemy_repository.py` snaps
query bounds with these, and the coverage builders
(`application/queries/get_backtest_range_coverage/coverage_builders.py`) decide
what "fully covered" means with them — one definition of the grid, read by both.
"""

from __future__ import annotations

from datetime import UTC, datetime


def as_utc(value: datetime) -> datetime:
    """Read a timestamp as UTC, whether or not it says so.

    A naive `datetime` coming out of SQLite carries no `tzinfo`; it is
    nevertheless UTC, because that is the only thing this application ever
    writes. Stamping it rather than converting it says that, and keeps a naive
    and an aware value comparable instead of raising `TypeError` deep inside an
    unrelated comparison.
    """
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def floor_open_time(value: datetime, interval_seconds: int) -> datetime:
    """The open time of the candle containing `value` — round **down**.

    Used for an upper bound: the newest candle that has fully closed by `value`.
    """
    return datetime.fromtimestamp(
        int(value.timestamp()) // interval_seconds * interval_seconds, UTC
    )


def ceil_open_time(value: datetime, interval_seconds: int) -> datetime:
    """The first candle open at or after `value` — round **up**.

    Used for a lower bound: a request starting mid-candle cannot claim that
    candle, because only part of it falls inside the requested range.
    """
    timestamp = int(value.timestamp())
    aligned = (timestamp + interval_seconds - 1) // interval_seconds * interval_seconds
    return datetime.fromtimestamp(aligned, UTC)
