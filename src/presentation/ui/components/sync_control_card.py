from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDateTimeEdit,
    QFormLayout,
    QGroupBox,
    QVBoxLayout,
    QPushButton,
)
from PySide6.QtCore import QDateTime, QSize
from Binace_Bot.src.presentation.ui.components.base_card import BaseCard
from Binace_Bot.src.presentation.ui.assets import IconTheme, get_icon_loader
from sagittarius_engine.extensions.pyside_mvc.ui_matrix_mixin import UIMatrixMixin

_DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
_DEFAULT_INTERVALS = ["1m", "5m", "15m", "1h", "1d", "1w"]
_DEFAULT_LOOKBACK_DAYS = 30
_ICON_SIZE = QSize(16, 16)


class SyncControlCard(BaseCard, UIMatrixMixin):
    """
    @brief Controls for selecting a symbol/interval/time range and triggering DB
    scans, syncs and clears on the Data Management screen.
    @details Inherits from BaseCard. Follows Rule 1: No DB imports, no business
    logic — every action is exposed as a plain button the Presenter listens to.
    Exposed as `view.control_card` so BasePresenter auto-binds the FSM/UI-matrix
    to this card instead of the whole screen.
    """

    def __init__(self, parent=None):
        super().__init__(title="Sync Controls", parent=parent)
        self._setup_content()

    def _setup_content(self):
        group_target = QGroupBox("Target")
        layout_target = QFormLayout(group_target)

        self.cbo_symbol = QComboBox()
        self.cbo_symbol.setEditable(True)
        self.cbo_symbol.addItems(_DEFAULT_SYMBOLS)

        self.cbo_interval = QComboBox()
        self.cbo_interval.addItems(_DEFAULT_INTERVALS)

        layout_target.addRow("Symbol:", self.cbo_symbol)
        layout_target.addRow("Interval:", self.cbo_interval)

        group_range = QGroupBox("Time Range")
        layout_range = QFormLayout(group_range)

        self.chk_custom_time = QCheckBox("Use Custom Time Range")

        self.dt_from = QDateTimeEdit(
            QDateTime.currentDateTime().addDays(-_DEFAULT_LOOKBACK_DAYS)
        )
        self.dt_from.setCalendarPopup(True)
        self.dt_from.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_from.setEnabled(False)

        self.dt_to = QDateTimeEdit(QDateTime.currentDateTime())
        self.dt_to.setCalendarPopup(True)
        self.dt_to.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_to.setEnabled(False)

        self.chk_custom_time.toggled.connect(self.dt_from.setEnabled)
        self.chk_custom_time.toggled.connect(self.dt_to.setEnabled)

        layout_range.addRow(self.chk_custom_time)
        layout_range.addRow("From:", self.dt_from)
        layout_range.addRow("To:", self.dt_to)

        group_scan = QGroupBox("Scan")
        layout_scan = QVBoxLayout(group_scan)
        self.btn_check_status = self._make_button(
            "Scan Current Status", "database", IconTheme.MUTED
        )
        self.btn_check_all = self._make_button(
            "Scan All Status", "layout-dashboard", IconTheme.MUTED
        )
        layout_scan.addWidget(self.btn_check_status)
        layout_scan.addWidget(self.btn_check_all)

        group_sync = QGroupBox("Sync")
        layout_sync = QVBoxLayout(group_sync)
        self.btn_sync_data = self._make_button(
            "Sync Current", "play", IconTheme.SUCCESS
        )
        self.btn_sync_all_gaps = self._make_button(
            "Sync All Gaps", "clock", IconTheme.SUCCESS
        )
        layout_sync.addWidget(self.btn_sync_data)
        layout_sync.addWidget(self.btn_sync_all_gaps)

        self.btn_clear_data = self._make_button(
            "Clear Local Data", "trash-2", IconTheme.DANGER
        )

        self.body_layout.addWidget(group_target)
        self.body_layout.addWidget(group_range)
        self.body_layout.addWidget(group_scan)
        self.body_layout.addWidget(group_sync)
        self.body_layout.addWidget(self.btn_clear_data)
        self.body_layout.addStretch()

    @staticmethod
    def _make_button(text: str, icon_name: str, color: str) -> QPushButton:
        button = QPushButton(text)
        button.setIcon(get_icon_loader().get_icon(icon_name, color=color))
        button.setIconSize(_ICON_SIZE)
        return button
