"""Backtest time-range chooser — the shared picker, wired to this screen.

`EPIC-015` replaced the preset-list-only `Overlay` this module used to define
with `TimeRangePicker.qml`; `EPIC-025` PR 4.3d replaced *that* with
`support/ui_kit/time_range_picker`, a `QDialog` on two real `QCalendarWidget`s
(ADR D20 — the platform has a calendar, so nothing here draws one).

What survives both swaps: `BackTestViewModel.time_range.presetOptions`
(`7d/30d/90d/365d/all/custom`) matches the shared picker's preset labels, which
additionally offer "Today" — an accepted gain, not a gap to paper over, and the
reason this screen's popup test asserts one row *more* than the ViewModel's
option list.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.time_range_picker import (
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
            title="BACKTEST TIME RANGE",
            parent=parent,
        )
        self.setObjectName("backtestTimeRangePickerDialog")
        self.applied.connect(self._source.apply)
