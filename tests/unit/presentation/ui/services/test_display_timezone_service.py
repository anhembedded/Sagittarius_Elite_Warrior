from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.presentation.ui.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
    SYSTEM_TIMEZONE_KEY,
    format_display_datetime,
    format_display_timestamp,
    get_display_timezone_label,
    get_supported_timezones,
    get_utc_offset_seconds,
    resolve_zone_info,
)


def test_resolve_zone_info_defaults_and_fallbacks() -> None:
    utc_zone = resolve_zone_info("UTC")
    assert utc_zone.key == "UTC"

    empty_zone = resolve_zone_info("")
    assert empty_zone.key == "UTC"

    invalid_zone = resolve_zone_info("NonExistent/Timezone_Invalid")
    assert invalid_zone.key == "UTC"

    vn_zone = resolve_zone_info("Asia/Ho_Chi_Minh")
    assert vn_zone.key == "Asia/Ho_Chi_Minh"


def test_resolve_zone_info_system() -> None:
    sys_zone = resolve_zone_info(SYSTEM_TIMEZONE_KEY)
    assert sys_zone is not None


def test_format_display_datetime_utc() -> None:
    dt = datetime(2026, 8, 17, 4, 30, 0, tzinfo=UTC)
    formatted = format_display_datetime(dt, tz_name="UTC")
    assert formatted == "2026-08-17 04:30:00"


def test_format_display_datetime_naive_assumes_utc() -> None:
    dt_naive = datetime(2026, 8, 17, 4, 30, 0)  # noqa: DTZ001
    formatted = format_display_datetime(dt_naive, tz_name="UTC")
    assert formatted == "2026-08-17 04:30:00"


def test_format_display_datetime_asia_ho_chi_minh() -> None:
    # 04:30 UTC -> 11:30 in UTC+7 (Asia/Ho_Chi_Minh)
    dt = datetime(2026, 8, 17, 4, 30, 0, tzinfo=UTC)
    formatted = format_display_datetime(dt, tz_name="Asia/Ho_Chi_Minh")
    assert formatted == "2026-08-17 11:30:00"


def test_format_display_datetime_daylight_saving_time() -> None:
    # America/New_York: Summer (EDT = UTC-4), Winter (EST = UTC-5)
    # Summer: 2026-07-15 16:00:00 UTC -> 12:00:00 EDT
    summer_dt = datetime(2026, 7, 15, 16, 0, 0, tzinfo=UTC)
    summer_formatted = format_display_datetime(summer_dt, tz_name="America/New_York")
    assert summer_formatted == "2026-07-15 12:00:00"

    # Winter: 2026-01-15 16:00:00 UTC -> 11:00:00 EST
    winter_dt = datetime(2026, 1, 15, 16, 0, 0, tzinfo=UTC)
    winter_formatted = format_display_datetime(winter_dt, tz_name="America/New_York")
    assert winter_formatted == "2026-01-15 11:00:00"


def test_format_display_timestamp() -> None:
    # Timestamp for 2026-08-17 00:00:00 UTC = 1786924800
    ts = datetime(2026, 8, 17, 0, 0, 0, tzinfo=UTC).timestamp()
    utc_str = format_display_timestamp(ts, tz_name="UTC")
    assert utc_str == "2026-08-17 00:00:00"

    vn_str = format_display_timestamp(ts, tz_name="Asia/Ho_Chi_Minh")
    assert vn_str == "2026-08-17 07:00:00"


def test_get_utc_offset_seconds() -> None:
    ts = datetime(2026, 8, 17, 0, 0, 0, tzinfo=UTC).timestamp()
    assert get_utc_offset_seconds(ts, tz_name="UTC") == 0.0
    assert get_utc_offset_seconds(ts, tz_name="Asia/Ho_Chi_Minh") == 7 * 3600.0


def test_get_display_timezone_label() -> None:
    assert get_display_timezone_label(DEFAULT_TIMEZONE) == "UTC"
    assert "Hệ thống" in get_display_timezone_label(SYSTEM_TIMEZONE_KEY)
    assert get_display_timezone_label("Asia/Ho_Chi_Minh") == "Asia/Ho_Chi_Minh"


def test_get_supported_timezones_contains_expected_keys() -> None:
    options = get_supported_timezones()
    ids = [opt["id"] for opt in options]
    assert "UTC" in ids
    assert SYSTEM_TIMEZONE_KEY in ids
    assert "Asia/Ho_Chi_Minh" in ids
