from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.time_range_preset import (
    TimeRangePreset,
    resolve_time_range,
)

_NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


def test_all_history_resolves_to_no_bounds():
    assert resolve_time_range(TimeRangePreset.ALL_HISTORY, _NOW) == (None, None)


def test_last_7_days_resolves_to_a_7_day_window_ending_now():
    start, end = resolve_time_range(TimeRangePreset.LAST_7_DAYS, _NOW)
    assert end == _NOW
    assert (end - start).days == 7


def test_last_365_days_resolves_to_a_365_day_window():
    start, end = resolve_time_range(TimeRangePreset.LAST_365_DAYS, _NOW)
    assert (end - start).days == 365


def test_custom_passes_through_the_given_bounds_untouched():
    custom_start = datetime(2025, 1, 1, tzinfo=UTC)
    custom_end = datetime(2025, 6, 1, tzinfo=UTC)

    result = resolve_time_range(
        TimeRangePreset.CUSTOM, _NOW, custom_start=custom_start, custom_end=custom_end
    )

    assert result == (custom_start, custom_end)


def test_custom_with_no_bounds_set_resolves_to_none_none():
    """Validation of an unfilled custom range is the caller's job — this
    function just resolves the mapping."""
    assert resolve_time_range(TimeRangePreset.CUSTOM, _NOW) == (None, None)
