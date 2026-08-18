from __future__ import annotations

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger("App.DisplayTimezone")

DEFAULT_TIMEZONE = "UTC"
SYSTEM_TIMEZONE_KEY = "SYSTEM"


def get_system_timezone_name() -> str:
    """Detects the local system timezone name, defaulting to UTC if unavailable."""
    try:
        local_tz = datetime.now().astimezone().tzinfo
        if local_tz is not None:
            tz_str = str(local_tz)
            if tz_str:
                return tz_str
    except (AttributeError, ValueError, OSError) as e:
        logger.warning(f"Could not detect system timezone: {e}")
    return DEFAULT_TIMEZONE


def resolve_zone_info(tz_name: str) -> ZoneInfo:
    """
    Resolves a timezone identifier into a concrete ZoneInfo instance.
    Supports "UTC", "SYSTEM", and standard IANA timezone identifiers.
    Falls back to UTC with a warning if the name cannot be resolved.
    """
    if not tz_name or tz_name == DEFAULT_TIMEZONE:
        return ZoneInfo("UTC")

    if tz_name == SYSTEM_TIMEZONE_KEY:
        sys_name = get_system_timezone_name()
        try:
            return ZoneInfo(sys_name)
        except (ZoneInfoNotFoundError, ValueError):
            logger.warning(
                f"Failed to resolve system timezone {sys_name!r}; falling back to UTC."
            )
            return ZoneInfo("UTC")

    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning(
            f"Invalid or unknown timezone identifier: {tz_name!r}; falling back to UTC."
        )
        return ZoneInfo("UTC")


def get_display_timezone_label(tz_name: str) -> str:
    """Returns a concise, human-readable label for the chosen display timezone."""
    if tz_name == DEFAULT_TIMEZONE:
        return "UTC"
    if tz_name == SYSTEM_TIMEZONE_KEY:
        return f"Hệ thống ({get_system_timezone_name()})"
    return tz_name


def get_supported_timezones() -> list[dict[str, str]]:
    """Returns list of selectable timezone options for UI pickers."""
    sys_name = get_system_timezone_name()
    options = [
        {"id": "UTC", "label": "UTC (Giờ phối hợp quốc tế)", "shortLabel": "UTC"},
        {
            "id": SYSTEM_TIMEZONE_KEY,
            "label": f"Giờ hệ thống ({sys_name})",
            "shortLabel": f"Hệ thống ({sys_name})",
        },
        {
            "id": "Asia/Ho_Chi_Minh",
            "label": "Asia/Ho_Chi_Minh (Việt Nam / GMT+7)",
            "shortLabel": "Asia/Ho_Chi_Minh",
        },
        {
            "id": "Asia/Tokyo",
            "label": "Asia/Tokyo (Nhật Bản / GMT+9)",
            "shortLabel": "Asia/Tokyo",
        },
        {
            "id": "Europe/London",
            "label": "Europe/London (Anh)",
            "shortLabel": "Europe/London",
        },
        {
            "id": "America/New_York",
            "label": "America/New_York (Mỹ - Eastern)",
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
    if dt.tzinfo is None:
        dt_utc = dt.replace(tzinfo=UTC)
    else:
        dt_utc = dt.astimezone(UTC)

    target_tz = resolve_zone_info(tz_name)
    converted = dt_utc.astimezone(target_tz)
    return converted.strftime(fmt)


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
    target_tz = resolve_zone_info(tz_name)
    converted = dt_utc.astimezone(target_tz)
    offset = converted.utcoffset()
    return offset.total_seconds() if offset is not None else 0.0
