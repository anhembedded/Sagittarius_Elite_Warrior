"""The text a time range's host stores for an instant, and reading it back.

Not display text: a host keeps its range as editable `DATETIME_FORMAT` text
(the Backtest's From/To, a sync's custom range) and parses it back, so the
same fixed format goes both ways. What a person reads about a range (the
picker's summary) is written by the application's formatter in
`range_rules.build_summary`. Split from `range_rules.py` so the formatter ban
(`test_display_values_go_through_the_formatter.py`) exempts this round trip
alone (review of PR #389).
"""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import DATETIME_FORMAT


def parse_instant(raw: str) -> datetime | None:
    """A host's text as an instant, or `None` when it is not one."""
    try:
        return datetime.strptime(raw.strip(), DATETIME_FORMAT).replace(tzinfo=UTC)
    except (ValueError, AttributeError):
        return None


def format_instant(value: datetime | None) -> str:
    """The text a host stores. `None` is the empty string — "no limit"."""
    return value.strftime(DATETIME_FORMAT) if value else ""
