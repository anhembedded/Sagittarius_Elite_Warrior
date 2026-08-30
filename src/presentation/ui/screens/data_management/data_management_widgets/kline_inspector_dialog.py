"""The K-line inspector — `EPIC-015`: hosts the standalone
`KlineInspectorTable.qml`/`KlineInspectorVM` pair.

Replaces the old QtWidgets dialog (a paginated `QListView` + jump-to-date +
audit controls + a page-size bar) with the QML port, per that widget's own
`NOTES.md` scope decisions — not re-litigated here: no pagination (the fetch
is already bounded at 10,000 candles and `ListView(reuseItems: true)`
virtualizes the rest), jump-to-date and the audit button deferred, the
page-size selector dropped outright since virtualization makes it
meaningless.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.qml import QmlOverlay
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.KlineInspectorTable.kline_inspector_vm import (
    KlineInspectorVM,
)

from .kline_inspector_source import DataManagementKlineInspectorSource

if TYPE_CHECKING:
    from ..data_management_view_model import DataManagementViewModel

_QML = (
    Path(__file__).resolve().parents[3]
    / "qml"
    / "KlineInspectorTable"
    / "KlineInspectorTable.qml"
)


class KlineInspectorDialogWidget(QmlOverlay):
    """
    @brief Data Management's "Tra cứu dữ liệu nến (KLine Inspector)" modal.
    Chrome is `Overlay` (via `QmlOverlay`), body is `KlineInspectorTable.qml`,
    rules are `KlineInspectorVM` reading through
    `DataManagementKlineInspectorSource`.

    @details The outer `Overlay` title is left blank on purpose. Unlike
    `CapitalDialogWidget`/`TimeRangePickerDialogWidget`, this body already
    renders its own title through `kit/PanelHeader` ("Tra cứu dữ liệu nến
    (KLine Inspector)", upper-cased by the component) plus a
    symbol/interval/count subtitle line right below it — giving `Overlay`'s
    own title `QLabel` the same text would stack the same heading twice.

    No footer button row either, matching the old dialog's own UX: the
    QtWidgets `KLineInspectorDialog` this replaces never overrode
    `Overlay._build_buttons()`, so its only close affordance was already the
    window's own title-bar close control (a modal `QDialog` gets one by
    default) plus Escape — there was no "Đóng" button to preserve. Adding
    one now would be new UX this migration was not asked to invent.
    """

    def __init__(
        self, view_model: DataManagementViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        self._source = DataManagementKlineInspectorSource(view_model)
        self._widget_vm = KlineInspectorVM(
            get_klines=self._source.get_klines,
            get_symbol=self._source.get_symbol,
            get_interval=self._source.get_interval,
        )
        super().__init__(
            "", qml_file=_QML, context={"vm": self._widget_vm}, parent=parent
        )
        self.setObjectName("klineInspectorModal")
        self.resize(840, 600)

    def open_dialog(self) -> None:
        """Re-reads the candle list every time — `set_kline_inspector_data`
        (which fires `openKlineInspectorRequested`, the one signal this
        dialog is opened from) always means fresh data landed."""
        self._widget_vm.refresh()
        self.show()
        self.raise_()
