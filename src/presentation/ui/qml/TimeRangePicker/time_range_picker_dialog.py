"""`TimeRangePickerDialog` — the standalone `TimeRangePicker.qml`/
`TimeRangePickerVM` pair, hosted behind `QmlOverlay`'s chrome.

@details `NOTES.md`'s own "future host" example already spells out this
exact wiring; the only thing it left implicit is that "future" is now
"three screens at once" (`EPIC-015` bậc 1: Data Management, Dev Board,
Backtest all open the same picker). Building one shared host here — VM
construction, the Hủy/Áp dụng footer, the "reload on every open" call — is
`qml-rule.md` §0.2's reuse rule applied: three screens each hand-rolling the
same footer/Apply-enable wiring around `TimeRangePickerVM` would be the
"bản sao gần giống" that section forbids, not three independent widgets.

Unlike `SymbolPicker/symbol_picker_modal_host.py`'s `SymbolPickerModal`,
this host does not take a pre-built widget ViewModel — `TimeRangePickerVM`
has no `ISource` Port to adapt (`time_range_picker_vm.py`'s own docstring:
"no reason to invent its own ISource ABC"), so there is nothing for a
screen to build except the five `get_*` callables its constructor already
takes. This class simply forwards them, so a screen's own composition root
only has to answer "where do these five values come from on my ViewModel",
never re-wire the footer or the refresh-on-open behaviour.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from ..host import QmlOverlay
from .time_range_picker_vm import TimeRangePickerVM

_QML = Path(__file__).with_name("TimeRangePicker.qml")
_DEFAULT_TITLE = "KHOẢNG THỜI GIAN DỮ LIỆU"


def _default_get_now() -> datetime:
    return datetime.now(UTC)


class TimeRangePickerDialog(QmlOverlay):
    """
    @brief Chrome is `Overlay` (via `QmlOverlay`), body is
    `TimeRangePicker.qml`, rules are `TimeRangePickerVM`.

    @param get_from_text / get_to_text The screen's current start/end, as
        `constants.DATETIME_FORMAT` text — the same two values every caller
        of the old `pick_date_range()` bridge already had to supply.
    @param get_timeframe_seconds / get_timeframe_label What lets the
        summary read "≈ N nến {label}" for the screen's actual active
        timeframe instead of a value hardcoded to one interval.
    @param get_now Defaults to `datetime.now(UTC)` — overridable only for
        tests that need a fixed clock.
    """

    applied = Signal(str, str)

    def __init__(
        self,
        *,
        get_from_text: Callable[[], str],
        get_to_text: Callable[[], str],
        get_timeframe_seconds: Callable[[], int],
        get_timeframe_label: Callable[[], str],
        get_now: Callable[[], datetime] = _default_get_now,
        title: str = _DEFAULT_TITLE,
        parent: QWidget | None = None,
    ) -> None:
        self._widget_vm = TimeRangePickerVM(
            get_now=get_now,
            get_from_text=get_from_text,
            get_to_text=get_to_text,
            get_timeframe_seconds=get_timeframe_seconds,
            get_timeframe_label=get_timeframe_label,
        )
        super().__init__(
            title, qml_file=_QML, context={"vm": self._widget_vm}, parent=parent
        )
        self.setObjectName("timeRangePickerDialog")
        self.resize(720, 480)

        self._widget_vm.stateChanged.connect(self._sync_apply_enabled)
        self._widget_vm.applied.connect(self._on_applied)
        self._sync_apply_enabled()

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setObjectName("btnCancelTimeRange")
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_cancel)
        self._btn_apply: QPushButton = QPushButton("Áp dụng")
        self._btn_apply.setObjectName("btnApplyTimeRange")
        self._btn_apply.clicked.connect(self._widget_vm.apply)
        row.addWidget(self._btn_apply)
        return row

    def open_dialog(self) -> None:
        self._widget_vm.refresh()
        self.show()
        self.raise_()

    def _sync_apply_enabled(self) -> None:
        self._btn_apply.setEnabled(self._widget_vm.canApply)

    def _on_applied(self, start_text: str, end_text: str) -> None:
        self.applied.emit(start_text, end_text)
        self.accept()
