"""What a time range means, with no widget in sight — `EPIC-025` PR 4.3d.

The part of the old `TimeRangePickerVM` (349 lines) worth keeping: which
presets exist, what each resolves to, whether a pair can be applied, and what
the summary line says. Everything else that class did was **calendar drawing**
— `leftDays`, `rightDays`, `weekdayLabels`, `pageMonths`, `_month_cells`, two
month labels — computed in Python so a `.qml` file could bind to it. That is
`QCalendarWidget`'s job, and ADR D20 forbids the substitute.

Pure functions over plain values, deliberately holding no `QObject`: this is the
part that can be wrong without anything crashing — a preset that resolves to the
wrong span looks exactly like a user who picked those dates — so keeping it out
of the dialog is what lets it be tested with no Qt event loop at all.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import Enum

from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import DATETIME_FORMAT

#: How far back a seed range reaches when the host has nothing usable to offer.
FALLBACK_DAYS = 7


class RangePresetKind(str, Enum):
    TODAY = "today"
    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"
    LAST_90_DAYS = "90d"
    LAST_365_DAYS = "365d"
    ALL_HISTORY = "all"
    CUSTOM = "custom"


PRESET_ORDER: tuple[RangePresetKind, ...] = (
    RangePresetKind.TODAY,
    RangePresetKind.LAST_7_DAYS,
    RangePresetKind.LAST_30_DAYS,
    RangePresetKind.LAST_90_DAYS,
    RangePresetKind.LAST_365_DAYS,
    RangePresetKind.ALL_HISTORY,
    RangePresetKind.CUSTOM,
)

PRESET_LABELS: dict[RangePresetKind, str] = {
    RangePresetKind.TODAY: "Today",
    RangePresetKind.LAST_7_DAYS: "Last 7 days",
    RangePresetKind.LAST_30_DAYS: "Last 30 days",
    RangePresetKind.LAST_90_DAYS: "Last 90 days",
    RangePresetKind.LAST_365_DAYS: "Last 365 days",
    RangePresetKind.ALL_HISTORY: "All history",
    RangePresetKind.CUSTOM: "Custom",
}

#: Only the fixed-length presets need a day count. `ALL_HISTORY` resolves to
#: `(None, None)` — the "no limit" convention the backend's
#: `resolve_time_range` already uses — and `CUSTOM` leaves the selection alone.
_PRESET_DAYS: dict[RangePresetKind, int] = {
    RangePresetKind.TODAY: 0,
    RangePresetKind.LAST_7_DAYS: 7,
    RangePresetKind.LAST_30_DAYS: 30,
    RangePresetKind.LAST_90_DAYS: 90,
    RangePresetKind.LAST_365_DAYS: 365,
}

_ALL_HISTORY_SUMMARY = "All history · unlimited"
_NEEDS_START = "Select a start date"
_NEEDS_END = "Select an end date"
#: An inverted pair cannot be applied, so the line under the calendars has to
#: say why rather than report the span. Its predecessor clamped the negative
#: span to `0 days`, which read as a legitimate single-instant range.
_INVERTED = "The end is before the start"
_SECONDS_PER_DAY = 86400


def parse_instant(raw: str) -> datetime | None:
    """A host's text as an instant, or `None` when it is not one."""
    try:
        return datetime.strptime(raw.strip(), DATETIME_FORMAT).replace(tzinfo=UTC)
    except (ValueError, AttributeError):
        return None


def format_instant(value: datetime | None) -> str:
    """The text a host stores. `None` is the empty string — "no limit"."""
    return value.strftime(DATETIME_FORMAT) if value else ""


def resolve_preset(
    kind: RangePresetKind, now: datetime
) -> tuple[datetime | None, datetime | None] | None:
    """What a preset means, or `None` for one that changes nothing.

    `TODAY` deliberately yields `start == end` — a single instant, the same
    convention the deleted `DateRangeOverlay.DEFAULT_PRESETS` used. A
    "midnight to now" reading of "today" would be a second, different meaning
    this app does not otherwise have.
    """
    if kind is RangePresetKind.CUSTOM:
        return None
    if kind is RangePresetKind.ALL_HISTORY:
        return None, None
    return now - timedelta(days=_PRESET_DAYS[kind]), now


def seed_range(
    from_text: str, to_text: str, now: datetime
) -> tuple[datetime, datetime]:
    """The pair a freshly opened dialog starts on — always a usable one.

    A host can hold nothing, half a pair, or an **inverted** one: the
    exchange's range has not been scanned yet, or a previous edit was
    abandoned halfway. Any of those has to become a range the user can see and
    Apply, because a dialog that opened on an invalid one would look broken
    with nothing on screen saying why.

    @par `BUG-128` lived in this function's predecessor
    `TimeRangePickerVM.refresh()` read
    `if start is None or end is None or start > end:` and then filled the gaps
    with `end = end or now` / `start = start or (end - week)`. For the first
    two disjuncts that works. For the third it does **nothing**: both values
    are non-`None`, so both `or`s keep what they had and the inverted pair is
    returned unchanged — a condition that detected a state and then declined
    to repair it. The picker then showed `08 Jul → 01 Jul`, `can_apply()` said
    yes because both ends are present, and the user could Apply a window the
    backend reads as empty.

    Written as three explicit branches rather than one condition plus
    fallbacks, because the bug was precisely a fallback that did not cover the
    case its own condition named.
    """
    start = parse_instant(from_text)
    end = parse_instant(to_text)

    if start is not None and end is not None and start <= end:
        return start, end
    if start is not None and end is not None:
        # Inverted. Keep the end the user last had — it is the more recent
        # edit in every flow that produces this — and re-derive the start.
        return end - timedelta(days=FALLBACK_DAYS), end

    end = end or now
    if start is not None and start <= end:
        return start, end
    return end - timedelta(days=FALLBACK_DAYS), end


def can_apply(start: datetime | None, end: datetime | None) -> bool:
    """Both ends or neither ("all history"), and in that order.

    Two conditions, and the second one is `BUG-128`'s other half. Half a pair
    is the one state the backend cannot act on: `resolve_time_range` reads
    `(None, None)` as "no limit" and two instants as a window, and has no
    reading for "from here to whenever".

    An **inverted** pair it can act on, and that is worse — it resolves to a
    window containing nothing, so a sync finds no candles and a backtest runs
    over none, with nothing on screen saying why. `seed_range` stops the host
    from *seeding* one; this stops the dialog from *emitting* one, which is the
    path a user takes by clicking From after To. The predecessor asked only
    whether both ends were present, so ordering was nobody's question at either
    end of the pair's life.
    """
    if (start is None) != (end is None):
        return False
    return start is None or end is None or start <= end


def build_summary(
    start: datetime | None,
    end: datetime | None,
    *,
    timeframe_seconds: int,
    timeframe_label: str,
) -> str:
    """The line under the calendars, in the screen's *own* timeframe.

    The candle estimate is why `timeframe_seconds` is a parameter rather than a
    constant: the QtWidgets bridge this replaced always said "1m" regardless of
    what the screen actually had selected.
    """
    if start is None and end is None:
        return _ALL_HISTORY_SUMMARY
    if start is None:
        return _NEEDS_START
    if end is None:
        return _NEEDS_END
    if start > end:
        return _INVERTED
    days = (end.date() - start.date()).days
    seconds = max(int(timeframe_seconds), 1)
    candles = int(days * _SECONDS_PER_DAY / seconds)
    return (
        f"{days} days · {start.date()} → {end.date()}"
        f"   ≈ {candles:,} candles {timeframe_label}"
    )
