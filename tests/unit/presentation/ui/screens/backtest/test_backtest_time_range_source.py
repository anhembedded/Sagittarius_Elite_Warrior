"""`BacktestTimeRangeSource` — pure logic, no `QApplication` required.

Mirrors `test_backtest_symbol_picker_source.py`'s shape: a screen ViewModel
stand-in with just the members this adapter reads/writes, so the whole
suite runs with `QApplication.instance()` staying `None`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.presentation.ui.constants import DATETIME_FORMAT
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_modals.backtest_time_range_source import (
    BacktestTimeRangeSource,
)


class _FakeViewModel:
    """Just the four members `BacktestTimeRangeSource` reads/writes from a
    screen ViewModel — a real `BackTestViewModel` is a `QObject` and needs a
    `QApplication` to construct, which this test suite deliberately avoids.
    """

    def __init__(
        self,
        time_range_preset: str = "custom",
        custom_start_text: str = "",
        custom_end_text: str = "",
        selected_timeframe: str = "5m",
    ) -> None:
        self.timeRangePreset = time_range_preset
        self.customStartText = custom_start_text
        self.customEndText = custom_end_text
        self.selectedTimeframe = selected_timeframe


def test_get_from_to_text_resolve_a_fixed_length_preset_to_concrete_dates() -> None:
    view_model = _FakeViewModel(time_range_preset="7d")
    source = BacktestTimeRangeSource(view_model)

    start = datetime.strptime(source.get_from_text(), DATETIME_FORMAT).replace(
        tzinfo=UTC
    )
    end = datetime.strptime(source.get_to_text(), DATETIME_FORMAT).replace(tzinfo=UTC)

    assert (end - start).days == 7


def test_get_from_to_text_return_blank_for_all_history() -> None:
    view_model = _FakeViewModel(time_range_preset="all")
    source = BacktestTimeRangeSource(view_model)

    assert source.get_from_text() == ""
    assert source.get_to_text() == ""


def test_get_from_to_text_read_the_custom_fields_when_preset_is_custom() -> None:
    view_model = _FakeViewModel(
        time_range_preset="custom",
        custom_start_text="2026-01-01 00:00",
        custom_end_text="2026-01-08 00:00",
    )
    source = BacktestTimeRangeSource(view_model)

    assert source.get_from_text() == "2026-01-01 00:00"
    assert source.get_to_text() == "2026-01-08 00:00"


def test_get_timeframe_seconds_reads_a_known_code() -> None:
    source = BacktestTimeRangeSource(_FakeViewModel(selected_timeframe="1h"))

    assert source.get_timeframe_seconds() == 3600


def test_get_timeframe_seconds_falls_back_for_an_unknown_code() -> None:
    source = BacktestTimeRangeSource(_FakeViewModel(selected_timeframe="not-a-code"))

    assert source.get_timeframe_seconds() == 60


def test_get_timeframe_label_is_the_raw_exchange_code() -> None:
    source = BacktestTimeRangeSource(_FakeViewModel(selected_timeframe="15m"))

    assert source.get_timeframe_label() == "15m"


def test_apply_writes_an_explicit_custom_range() -> None:
    view_model = _FakeViewModel(time_range_preset="30d")
    source = BacktestTimeRangeSource(view_model)

    source.apply("2026-02-01 00:00", "2026-02-08 00:00")

    assert view_model.customStartText == "2026-02-01 00:00"
    assert view_model.customEndText == "2026-02-08 00:00"
    assert view_model.timeRangePreset == "custom"
