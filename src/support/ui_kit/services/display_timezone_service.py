"""The user's display timezone: label, offset and formatting.

Capability: Show a time in the user's display timezone
    Also: timezone, utc offset, local time, datetime format
    Use: get_display_timezone_label, system_zone_name_at, get_supported_timezones, format_display_datetime, get_utc_offset_seconds, to_display_time, display_zone_name
    User: src/modules/backtesting/ui/view_models/time_range_view_model.py
    Status: stable
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import failure_detail

logger = logging.getLogger("App.DisplayTimezone")

DEFAULT_TIMEZONE = "UTC"
SYSTEM_TIMEZONE_KEY = "SYSTEM"

#: Reasons already logged, so a column of timestamps is one warning and not one per cell.
_reported_fallbacks: set[tuple[str, str]] = set()


def _fall_back_to_utc(subject: str, reason: str) -> None:
    """One WARNING per distinct `subject` and `reason`."""
    if (subject, reason) not in _reported_fallbacks:
        _reported_fallbacks.add((subject, reason))
        logger.warning("%s (%s); falling back to UTC.", subject, reason)


def machine_local_time(moment: datetime) -> datetime:
    """`moment` as the machine's own clock shows it, by the OS's rules for that instant (daylight
    saving included). The one place the service asks the OS: the result's zone is a fixed offset
    named by the platform's abbreviation (`+07`, `EDT`, a Windows display name), which is not an
    IANA key, so it is never looked up as one (`BUG-234`). Tests replace this function."""
    return moment.astimezone()


def _named_zone(tz_name: str) -> ZoneInfo:
    """An IANA zone; UTC, logged, for a name `ZoneInfo` cannot read."""
    if not tz_name or tz_name == DEFAULT_TIMEZONE:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        _fall_back_to_utc("Invalid or unknown timezone identifier", repr(tz_name))
        return ZoneInfo("UTC")


def to_display_time(moment: datetime, tz_name: str = DEFAULT_TIMEZONE) -> datetime:
    """The aware `moment` as it reads in the display zone `tz_name` ("UTC", "SYSTEM" or an IANA key).

    "SYSTEM" is the machine's own time, converted instant by instant, never a zone looked up by
    name: the machine's zone has no IANA key we can read with the standard library."""
    try:
        if tz_name != SYSTEM_TIMEZONE_KEY:
            return moment.astimezone(_named_zone(tz_name))
        return machine_local_time(moment)
    except (OSError, OverflowError, ValueError) as error:
        _fall_back_to_utc(
            "The moment or the zone cannot be converted", failure_detail(error)
        )
        return moment.astimezone(UTC)


def _offset_text(offset: timedelta) -> str:
    minutes = int(offset.total_seconds() // 60)
    sign = "-" if minutes < 0 else "+"
    hours, rest = divmod(abs(minutes), 60)
    return f"UTC{sign}{hours:02d}:{rest:02d}"


def system_zone_name_at(moment: datetime) -> str:
    """The machine's zone as it reads at `moment`, for a text that shows that moment: the
    platform's name and the UTC offset in force then (`EST, UTC-05:00` in January, `EDT,
    UTC-04:00` in July; `UTC+07:00` when the platform's name is the offset itself). The name
    comes from the same conversion that wrote the time (`BUG-239`)."""
    local = to_display_time(moment, SYSTEM_TIMEZONE_KEY)
    offset = local.utcoffset()
    if offset is None:
        return DEFAULT_TIMEZONE
    abbreviation = local.tzname() or ""
    if offset == timedelta(0) and abbreviation in {"", "UTC"}:
        return DEFAULT_TIMEZONE
    if not abbreviation or abbreviation[0] in "+-":
        return _offset_text(offset)
    return f"{abbreviation}, {_offset_text(offset)}"


def get_system_timezone_name() -> str:
    """The machine's zone as it is now: the label of the *setting* in a picker, which names
    the zone the person is in today. A text that shows a moment uses `system_zone_name_at`."""
    return system_zone_name_at(datetime.now(UTC))


def display_zone_name(tz_name: str, moment: datetime) -> str:
    """The zone `tz_name` shows `moment` in, by name ("UTC" when it cannot be resolved): a
    text that names its zone must name the one it was written in, and under "System" the
    offset is the one in force at `moment`, not today's."""
    if tz_name == SYSTEM_TIMEZONE_KEY:
        return system_zone_name_at(moment)
    return _named_zone(tz_name).key


def get_display_timezone_label(tz_name: str) -> str:
    """Returns a concise, human-readable label for the chosen display timezone."""
    if tz_name == DEFAULT_TIMEZONE:
        return "UTC"
    if tz_name == SYSTEM_TIMEZONE_KEY:
        return f"System ({get_system_timezone_name()})"
    return tz_name


def get_supported_timezones() -> list[dict[str, str]]:
    """Returns list of selectable timezone options for UI pickers."""
    sys_name = get_system_timezone_name()
    options = [
        {"id": "UTC", "label": "UTC (Coordinated Universal Time)", "shortLabel": "UTC"},
        {
            "id": SYSTEM_TIMEZONE_KEY,
            "label": f"System time ({sys_name})",
            "shortLabel": f"System ({sys_name})",
        },
        {
            "id": "Asia/Ho_Chi_Minh",
            "label": "Asia/Ho_Chi_Minh (Vietnam / GMT+7)",
            "shortLabel": "Asia/Ho_Chi_Minh",
        },
        {
            "id": "Asia/Tokyo",
            "label": "Asia/Tokyo (Japan / GMT+9)",
            "shortLabel": "Asia/Tokyo",
        },
        {
            "id": "Europe/London",
            "label": "Europe/London (UK)",
            "shortLabel": "Europe/London",
        },
        {
            "id": "America/New_York",
            "label": "America/New_York (US - Eastern)",
            "shortLabel": "America/New_York",
        },
    ]
    return options


def format_display_datetime(
    dt: datetime,
    tz_name: str = DEFAULT_TIMEZONE,
    fmt: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    """
    Formats a datetime object in the requested display timezone.
    Assumes naive datetime is UTC (standard across this application).
    """
    dt_utc = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)

    return to_display_time(dt_utc, tz_name).strftime(fmt)


def format_display_timestamp(
    timestamp: float,
    tz_name: str = DEFAULT_TIMEZONE,
    fmt: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    """Formats a UNIX timestamp in seconds in the requested display timezone."""
    try:
        dt_utc = datetime.fromtimestamp(timestamp, tz=UTC)
    except (OSError, ValueError, OverflowError):
        return ""
    return format_display_datetime(dt_utc, tz_name=tz_name, fmt=fmt)


def get_utc_offset_seconds(
    timestamp: float,
    tz_name: str = DEFAULT_TIMEZONE,
) -> float:
    """
    Returns the UTC offset in seconds at a given timestamp for the target timezone.
    Correctly accounts for Daylight Saving Time (DST).
    """
    try:
        dt_utc = datetime.fromtimestamp(timestamp, tz=UTC)
    except (OSError, ValueError, OverflowError):
        return 0.0
    offset = to_display_time(dt_utc, tz_name).utcoffset()
    return offset.total_seconds() if offset is not None else 0.0
