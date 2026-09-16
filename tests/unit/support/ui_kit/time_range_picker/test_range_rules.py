"""The time-range rules, tested by a suite the gate actually runs.

`EPIC-025` PR 4.3d. The maths these functions carry used to live in
`TimeRangePickerVM` and had its own tests — at
`src/presentation/ui/qml/TimeRangePicker/tests/test_time_range_picker_vm.py`,
**colocated under `src/`**, which the gate never ran (`pytest
Sagittarius_Elite_Warrior/tests`). PR 1.4b-2 found that hole and counted twenty
such files; this is the first of them to be closed rather than deleted, because
the rules survived the widget.

No `QApplication`: these are functions over instants.
"""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.support.ui_kit.time_range_picker import (
    PRESET_ORDER,
    RangePresetKind,
    build_summary,
    can_apply,
    format_instant,
    parse_instant,
    resolve_preset,
    seed_range,
)

_NOW = datetime(2026, 7, 8, 12, 30, tzinfo=UTC)


def test_every_preset_has_a_label_and_a_place_in_the_order():
    from Sagittarius_Elite_Warrior.src.support.ui_kit.time_range_picker import (
        PRESET_LABELS,
    )

    assert set(PRESET_ORDER) == set(RangePresetKind)
    assert all(PRESET_LABELS[kind] for kind in PRESET_ORDER)


def test_a_fixed_length_preset_ends_now_and_starts_that_many_days_back():
    resolved = resolve_preset(RangePresetKind.LAST_30_DAYS, _NOW)

    assert resolved is not None
    start, end = resolved
    assert end == _NOW
    assert start is not None
    assert (end - start).days == 30


def test_today_is_a_single_instant_not_midnight_to_now():
    """The convention the deleted `DateRangeOverlay.DEFAULT_PRESETS` used. A
    "midnight to now" reading would be a second, different meaning of today
    that this app does not otherwise have."""
    resolved = resolve_preset(RangePresetKind.TODAY, _NOW)

    assert resolved == (_NOW, _NOW)


def test_all_history_resolves_to_no_limit_on_both_ends():
    """`(None, None)` is what the backend's `resolve_time_range` reads as
    unlimited."""
    assert resolve_preset(RangePresetKind.ALL_HISTORY, _NOW) == (None, None)


def test_custom_changes_nothing():
    """It is the state every other edit lands in, not a range of its own."""
    assert resolve_preset(RangePresetKind.CUSTOM, _NOW) is None


def test_a_usable_pair_is_seeded_from_the_host_unchanged():
    start, end = seed_range("2026-07-01 00:00", "2026-07-08 00:00", _NOW)

    assert start == datetime(2026, 7, 1, tzinfo=UTC)
    assert end == datetime(2026, 7, 8, tzinfo=UTC)


def test_nothing_from_the_host_seeds_a_week_ending_now():
    """A dialog that opened on an invalid range would make Apply unreachable
    with nothing on screen saying why."""
    start, end = seed_range("", "", _NOW)

    assert end == _NOW
    assert (end - start).days == 7


def test_half_a_pair_from_the_host_is_completed_rather_than_kept():
    start, end = seed_range("", "2026-07-08 00:00", _NOW)

    assert end == datetime(2026, 7, 8, tzinfo=UTC)
    assert (end - start).days == 7


def test_an_inverted_pair_from_the_host_is_replaced():
    """A previous edit abandoned halfway can leave start after end."""
    start, end = seed_range("2026-07-08 00:00", "2026-07-01 00:00", _NOW)

    assert start < end


def test_both_ends_or_neither_can_be_applied_but_never_exactly_one():
    """Half a pair is the one state the backend has no reading for: it takes
    `(None, None)` as unlimited and two instants as a window, and nothing as
    "from here to whenever"."""
    assert can_apply(_NOW, _NOW) is True
    assert can_apply(None, None) is True
    assert can_apply(_NOW, None) is False
    assert can_apply(None, _NOW) is False


def test_an_inverted_pair_cannot_be_applied():
    """`BUG-128`'s other half. `seed_range` stops a host from seeding one, but
    the user reaches the same state by clicking From after To, and the
    predecessor's check asked only whether both ends were *present*."""
    later = datetime(2026, 7, 8, tzinfo=UTC)
    earlier = datetime(2026, 7, 1, tzinfo=UTC)

    assert can_apply(later, earlier) is False
    assert can_apply(earlier, later) is True
    assert can_apply(later, later) is True


def test_the_summary_names_an_inverted_pair_rather_than_counting_zero_days():
    """A disabled Apply needs a reason on screen. The predecessor clamped the
    negative span and printed `0 days`, which reads as a legitimate single
    instant."""
    summary = build_summary(
        datetime(2026, 7, 8, tzinfo=UTC),
        datetime(2026, 7, 1, tzinfo=UTC),
        timeframe_seconds=60,
        timeframe_label="1m",
    )

    assert "end is before the start" in summary
    assert "0 days" not in summary


def test_the_summary_counts_candles_in_the_screens_own_timeframe():
    """Why `timeframe_seconds` is a parameter: the bridge this replaced always
    said "1m" regardless of what the screen had selected."""
    start = datetime(2026, 7, 1, tzinfo=UTC)
    end = datetime(2026, 7, 8, tzinfo=UTC)

    five_minutes = build_summary(
        start, end, timeframe_seconds=300, timeframe_label="5m"
    )
    one_hour = build_summary(start, end, timeframe_seconds=3600, timeframe_label="1h")

    assert "7 days" in five_minutes
    assert "2,016 candles 5m" in five_minutes
    assert "168 candles 1h" in one_hour


def test_the_summary_says_which_end_is_missing():
    assert "start" in build_summary(
        None, _NOW, timeframe_seconds=60, timeframe_label="1m"
    )
    assert "end" in build_summary(
        _NOW, None, timeframe_seconds=60, timeframe_label="1m"
    )
    assert "All history" in build_summary(
        None, None, timeframe_seconds=60, timeframe_label="1m"
    )


def test_a_zero_timeframe_does_not_divide_by_zero():
    """A screen whose timeframe has not loaded yet reports 0 seconds, and a
    summary is not worth a crash."""
    summary = build_summary(
        datetime(2026, 7, 1, tzinfo=UTC),
        datetime(2026, 7, 8, tzinfo=UTC),
        timeframe_seconds=0,
        timeframe_label="",
    )

    assert "7 days" in summary


def test_text_round_trips_through_parse_and_format():
    assert format_instant(parse_instant("2026-07-01 00:00")) == "2026-07-01 00:00"
    assert parse_instant("not a date") is None
    assert format_instant(None) == ""
