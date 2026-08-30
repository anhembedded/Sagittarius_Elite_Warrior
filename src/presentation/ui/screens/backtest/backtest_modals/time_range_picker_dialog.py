"""Backtest time-range chooser — `EPIC-015`: hosts the standalone
`TimeRangePicker.qml` in place of the old preset-list-only `Overlay`.

Replaces `TimeRangePickerDialog` (the QtWidgets preset-list dialog this
module used to define). `BackTestViewModel.timeRangePresetOptions`
(`7d/30d/90d/365d/all/custom`) already matches `TimeRangePickerVM`'s own
hardcoded preset labels; the new widget additionally offers "Hôm nay" and a
live two-month calendar, both accepted gains, not gaps to paper over.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimeRangePicker.time_range_picker_dialog import (
    TimeRangePickerDialog,
)

from .backtest_time_range_source import BacktestTimeRangeSource

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


class TimeRangePickerDialogWidget(TimeRangePickerDialog):
    """
    @brief Choose the Backtest window's date range. Chrome+body come from
    `TimeRangePickerDialog`, the screen wiring is
    `BacktestTimeRangeSource` reading/writing `BackTestViewModel`.

    @details Mirrors `CapitalDialogWidget`'s shape: the screen ViewModel
    write happens through the adapter this composition root owns, not
    pushed down into `BackTestModalsHost`.
    """

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        self._source = BacktestTimeRangeSource(view_model)
        super().__init__(
            get_from_text=self._source.get_from_text,
            get_to_text=self._source.get_to_text,
            get_timeframe_seconds=self._source.get_timeframe_seconds,
            get_timeframe_label=self._source.get_timeframe_label,
            title="KHOẢNG THỜI GIAN BACKTEST",
            parent=parent,
        )
        self.setObjectName("backtestTimeRangePickerDialog")
        self.applied.connect(self._source.apply)
