"""No-GUI tests for TimeRangePickerVM."""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101, PLR2004

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimeRangePicker.time_range_picker_vm import (
    TimeRangePickerVM,
)

_NOW = datetime(2026, 8, 26, 6, 56, tzinfo=UTC)


def _vm(
    *,
    from_text: str = "2026-07-06 06:56",
    to_text: str = "2026-08-26 06:56",
    timeframe_seconds: int = 300,
    timeframe_label: str = "5m",
) -> TimeRangePickerVM:
    vm = TimeRangePickerVM(
        get_now=lambda: _NOW,
        get_from_text=lambda: from_text,
        get_to_text=lambda: to_text,
        get_timeframe_seconds=lambda: timeframe_seconds,
        get_timeframe_label=lambda: timeframe_label,
    )
    vm.refresh()
    return vm


def test_refresh_seeds_the_range_and_builds_the_summary():
    vm = _vm()

    assert vm.fromText == "2026-07-06 06:56"
    assert vm.toText == "2026-08-26 06:56"
    assert vm.summaryText == "51 ngày · 2026-07-06 → 2026-08-26   ≈ 14,688 nến 5m"
    assert vm.canApply is True
    assert [p["id"] for p in vm.presets] == [
        "today",
        "7d",
        "30d",
        "90d",
        "365d",
        "all",
        "custom",
    ]
    assert next(p for p in vm.presets if p["id"] == "custom")["selected"] is True


def test_refresh_falls_back_to_a_week_when_seed_text_is_unparseable():
    vm = _vm(from_text="garbage", to_text="also garbage")

    assert vm.toText == _NOW.strftime("%Y-%m-%d %H:%M")
    assert "7 ngày" in vm.summaryText


def test_fixed_length_preset_resolves_relative_to_now():
    vm = _vm()
    vm.choosePreset("30d")

    assert vm.fromText == "2026-07-27 06:56"
    assert vm.toText == "2026-08-26 06:56"
    assert next(p for p in vm.presets if p["id"] == "30d")["selected"] is True


def test_today_preset_yields_a_same_instant_pair():
    vm = _vm()
    vm.choosePreset("today")

    assert vm.fromText == vm.toText == _NOW.strftime("%Y-%m-%d %H:%M")
    assert vm.canApply is True


def test_all_history_preset_clears_both_bounds():
    vm = _vm()
    vm.choosePreset("all")

    assert vm.fromText == ""
    assert vm.toText == ""
    assert vm.summaryText == "Toàn bộ lịch sử · không giới hạn"
    assert vm.canApply is True


def test_unknown_preset_id_is_ignored():
    vm = _vm()
    before = vm.fromText
    vm.choosePreset("does-not-exist")

    assert vm.fromText == before


def test_calendar_day_click_sets_start_then_end_then_restarts():
    vm = _vm()
    vm.choosePreset("all")  # clear both ends first

    vm.selectDay("2026-08-10")
    assert vm.fromText.startswith("2026-08-10")
    assert vm.toText == ""
    assert next(p for p in vm.presets if p["id"] == "custom")["selected"] is True

    vm.selectDay("2026-08-15")
    assert vm.toText.startswith("2026-08-15")

    # Clicking before the current start restarts the pair rather than
    # inverting it — same rule `DateRangeOverlay._on_day` uses.
    vm.selectDay("2026-08-05")
    assert vm.fromText.startswith("2026-08-05")
    assert vm.toText == ""


def test_left_and_right_calendar_are_consecutive_months_of_six_weeks():
    vm = _vm()
    vm.pageMonths(0)  # forces a rebuild at the current anchor

    assert len(vm.leftDays) == 42
    assert len(vm.rightDays) == 42
    assert vm.leftMonthLabel != vm.rightMonthLabel


def test_page_months_wraps_the_year():
    vm = _vm(from_text="2026-12-15 00:00", to_text="2026-12-20 00:00")
    assert vm.leftMonthLabel == "Tháng 12 2026"

    vm.pageMonths(1)
    assert vm.leftMonthLabel == "Tháng 1 2027"

    vm.pageMonths(-1)
    assert vm.leftMonthLabel == "Tháng 12 2026"


def test_typed_from_and_to_text_update_the_range_and_preset():
    vm = _vm()
    vm.setFromText("2026-08-01 00:00")
    vm.setToText("2026-08-10 00:00")

    assert vm.summaryText.startswith("9 ngày")
    assert next(p for p in vm.presets if p["id"] == "custom")["selected"] is True


def test_unparseable_typed_text_clears_that_bound_and_blocks_apply():
    vm = _vm()
    vm.setFromText("not a date")

    assert vm.fromText == ""
    assert vm.canApply is False
    assert vm.summaryText == "Chọn ngày bắt đầu"


def test_candle_estimate_uses_the_injected_timeframe():
    one_minute = _vm(timeframe_seconds=60, timeframe_label="1m")
    five_minute = _vm(timeframe_seconds=300, timeframe_label="5m")

    assert "nến 1m" in one_minute.summaryText
    assert "nến 5m" in five_minute.summaryText
    # 51 days: 1m gives 5x as many candles as 5m.
    assert "73,440" in one_minute.summaryText
    assert "14,688" in five_minute.summaryText


def test_apply_emits_the_current_range_and_is_a_noop_when_incomplete():
    vm = _vm()
    emitted: list[tuple[str, str]] = []
    vm.applied.connect(lambda start, end: emitted.append((start, end)))

    vm.setFromText("not a date")
    vm.apply()
    assert emitted == []

    vm.refresh()
    vm.apply()
    assert emitted == [("2026-07-06 06:56", "2026-08-26 06:56")]
