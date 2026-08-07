from PySide6.QtWidgets import QWidget, QHBoxLayout, QSplitter
from PySide6.QtCore import Signal, Qt

from Binace_Bot.src.presentation.ui.components.monitor_card import MonitorCard
from Binace_Bot.src.presentation.ui.screens.data_management.sync_control_card import (
    SyncControlCard,
)
from Binace_Bot.src.presentation.ui.screens.data_management.database_status_card import (
    DatabaseStatusCard,
)


class DataManagementView(QWidget):
    """
    @brief The View for the Data Management Screen.
    @details Assembles three dumb BaseCards: `control_card` (symbol/interval/time
    range + scan/sync/clear actions), `status_card` (status table + progress bar),
    and `monitor_card` (sync logs). A QSplitter keeps the layout responsive.

    The widgets the Presenter drives live one level down inside the cards, but are
    re-exposed as flat attributes here (e.g. `self.cbo_symbol`) so the existing
    Presenter contract — which reads/writes `view.cbo_symbol`, `view.table_status`,
    etc. directly — keeps working unchanged.
    """

    sig_sync_row_clicked = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        self.control_card = SyncControlCard()
        self.status_card = DatabaseStatusCard()
        self.monitor_card = MonitorCard()

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.addWidget(self.status_card)
        right_splitter.addWidget(self.monitor_card)
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 1)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(self.control_card)
        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)

        main_layout.addWidget(main_splitter)

        self._expose_control_widgets()
        self._expose_status_widgets()
        self._wire_internal_signals()

    def _expose_control_widgets(self) -> None:
        """Re-exposes control_card widgets as flat `self.*` attrs for the Presenter."""
        self.cbo_symbol = self.control_card.cbo_symbol
        self.cbo_interval = self.control_card.cbo_interval
        self.chk_custom_time = self.control_card.chk_custom_time
        self.dt_from = self.control_card.dt_from
        self.dt_to = self.control_card.dt_to
        self.btn_check_status = self.control_card.btn_check_status
        self.btn_check_all = self.control_card.btn_check_all
        self.btn_sync_data = self.control_card.btn_sync_data
        self.btn_sync_all_gaps = self.control_card.btn_sync_all_gaps
        self.btn_clear_data = self.control_card.btn_clear_data

    def _expose_status_widgets(self) -> None:
        """Re-exposes status_card widgets as flat `self.*` attrs for the Presenter."""
        self.table_status = self.status_card.table_status
        self.progress_bar = self.status_card.progress_bar

    def _wire_internal_signals(self) -> None:
        # Bubble the per-row "Sync" click up through the View's own signal so the
        # Presenter can keep connecting to `view.sig_sync_row_clicked` directly.
        self.status_card.sig_sync_row_clicked.connect(self.sig_sync_row_clicked)

        # Clearing the on-screen log is a pure UI concern — no Presenter round-trip.
        self.monitor_card.clear_logs_clicked.connect(self.monitor_card.clear_logs)

    def append_log(self, text: str) -> None:
        self.monitor_card.append_log(text)

    def update_status_table(
        self, symbol: str, interval: str, first: str, last: str, total: str, status: str
    ) -> None:
        self.status_card.update_row(symbol, interval, first, last, total, status)

    def clear_table(self) -> None:
        self.status_card.clear()
