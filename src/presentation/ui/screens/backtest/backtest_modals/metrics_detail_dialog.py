"""Backtest extended-metrics readout — `EPIC-015` Phase 3: replaces
`ExtendedMetricsDialog`/`StatGrid` with `MetricsDetailPanel.qml`/
`MetricsDetailVM`, hosted behind `MetricsDetailModal`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.MetricsDetailPanel.metrics_detail_modal_host import (
    MetricsDetailModal,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.MetricsDetailPanel.metrics_detail_vm import (
    MetricsDetailVM,
)

from .backtest_metrics_detail_source import BacktestMetricsDetailSource

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


class MetricsDetailDialogWidget(MetricsDetailModal):
    """
    @brief Backtest's "CHỈ SỐ CHI TIẾT BACKTEST" readout. Chrome+modal is
    `MetricsDetailModal`, body is `MetricsDetailPanel.qml`, rules are
    `MetricsDetailVM` reading through `BacktestMetricsDetailSource`.

    @details Mirrors `SymbolPickerDialogWidget`/`TimeRangePickerDialogWidget`'s
    shape: this screen's composition root owns the adapter and the one piece
    of wiring the standalone component cannot own itself — refreshing the VM
    when new data arrives. Two paths keep it current, same dual coverage the
    old `ExtendedMetricsDialog` had: `BackTestViewModel.statCardsChanged`
    (fires whenever a run's stat cards, and since `EPIC-015` Phase 3 its
    `ExtendedMetricsSnapshot`, change) keeps it fresh while already open or
    while hidden, and `open_dialog()` refreshes once more on every open —
    the old dialog's `showEvent()` equivalent — so a change that landed
    while this dialog object already existed but was never shown is never
    silently missed.
    """

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        self._source = BacktestMetricsDetailSource(view_model)
        self._widget_vm = MetricsDetailVM(
            get_cards=self._source.get_cards,
            get_gross_profit=self._source.get_gross_profit,
            get_gross_loss=self._source.get_gross_loss,
            get_profit_factor=self._source.get_profit_factor,
            get_total_closed_trades=self._source.get_total_closed_trades,
            get_fee_rate_percent=self._source.get_fee_rate_percent,
            get_timeframe_seconds=self._source.get_timeframe_seconds,
        )
        super().__init__(self._widget_vm, parent=parent)
        self.setObjectName("backtestMetricsDetailDialog")
        view_model.statCardsChanged.connect(self._widget_vm.refresh)

    def open_dialog(self) -> None:
        self._widget_vm.refresh()
        self.show()
        self.raise_()
