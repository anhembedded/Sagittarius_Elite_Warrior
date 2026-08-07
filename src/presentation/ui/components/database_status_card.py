import functools

from PySide6.QtWidgets import (
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QHeaderView,
    QProgressBar,
    QPushButton,
    QLabel,
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from Binace_Bot.src.presentation.ui.components.base_card import BaseCard
from Binace_Bot.src.presentation.ui.assets import IconTheme, get_icon_loader

_COLUMN_HEADERS = [
    "Symbol",
    "Interval",
    "First Record",
    "Last Record",
    "Total Candles",
    "Status/Gaps",
    "Action",
]
_SYMBOL_COLUMN = 0
_INTERVAL_COLUMN = 1
_STATUS_COLUMN = 5
_ACTION_COLUMN = 6
_HEALTHY_STATUSES = {"OK", "0 gaps found!"}
_ACTION_COLUMN_WIDTH = 100


class DatabaseStatusCard(BaseCard):
    """
    @brief Displays the per-symbol/interval sync status table plus a scan progress
    bar and a live row-count/gap summary in the header.
    @details Inherits from BaseCard. Follows Rule 1: No DB imports, no business
    logic — row coloring and the summary count only interpret the already-formatted
    `status_text` string the Presenter forwards from `DatabaseStatusDTO`.
    """

    sig_sync_row_clicked = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(title="Database Status", parent=parent)
        self._setup_content()

    def _setup_content(self):
        self.lbl_summary = QLabel("0 rows")
        self.lbl_summary.setObjectName("card_stat_label")
        self.add_to_header(self.lbl_summary)

        self.table_status = QTableWidget(0, len(_COLUMN_HEADERS))
        self.table_status.setObjectName("db_status_table")
        self.table_status.setHorizontalHeaderLabels(_COLUMN_HEADERS)
        self.table_status.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_status.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_status.setAlternatingRowColors(True)
        self.table_status.setShowGrid(False)
        self.table_status.verticalHeader().setVisible(False)

        header = self.table_status.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        # A fixed width (not ResizeToContents) so the button fits identically on
        # every platform — ResizeToContents sizes off the *header label*, not the
        # cell widget, and doesn't reliably grow for a wider button + icon.
        header.setSectionResizeMode(_ACTION_COLUMN, QHeaderView.Fixed)
        header.resizeSection(_ACTION_COLUMN, _ACTION_COLUMN_WIDTH)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.hide()

        self.body_layout.addWidget(self.table_status, 1)
        self.body_layout.addWidget(self.progress_bar)

    def update_row(
        self, symbol: str, interval: str, first: str, last: str, total: str, status: str
    ) -> None:
        """Updates an existing symbol/interval row, or appends a new one."""
        row_idx = self._find_row(symbol, interval)
        if row_idx == -1:
            row_idx = self._insert_row(symbol, interval)

        self.table_status.setItem(row_idx, _SYMBOL_COLUMN, QTableWidgetItem(symbol))
        self.table_status.setItem(row_idx, _INTERVAL_COLUMN, QTableWidgetItem(interval))
        self.table_status.setItem(row_idx, 2, QTableWidgetItem(str(first)))
        self.table_status.setItem(row_idx, 3, QTableWidgetItem(str(last)))
        self.table_status.setItem(row_idx, 4, QTableWidgetItem(str(total)))
        self._set_status_cell(row_idx, status)
        self._update_summary()

    def clear(self) -> None:
        self.table_status.setRowCount(0)
        self._update_summary()

    def _find_row(self, symbol: str, interval: str) -> int:
        for row in range(self.table_status.rowCount()):
            item_symbol = self.table_status.item(row, _SYMBOL_COLUMN)
            item_interval = self.table_status.item(row, _INTERVAL_COLUMN)
            if (
                item_symbol
                and item_interval
                and item_symbol.text() == symbol
                and item_interval.text() == interval
            ):
                return row
        return -1

    def _insert_row(self, symbol: str, interval: str) -> int:
        row_idx = self.table_status.rowCount()
        self.table_status.insertRow(row_idx)

        btn_sync = QPushButton("Sync")
        btn_sync.setObjectName("btnRowSync")
        btn_sync.setIcon(get_icon_loader().get_icon("play", color=IconTheme.SUCCESS))
        btn_sync.clicked.connect(
            functools.partial(self._emit_sync_row, symbol, interval)
        )
        self.table_status.setCellWidget(row_idx, _ACTION_COLUMN, btn_sync)
        return row_idx

    def _set_status_cell(self, row_idx: int, status: str) -> None:
        item = QTableWidgetItem(status)
        color = IconTheme.SUCCESS if status in _HEALTHY_STATUSES else IconTheme.DANGER
        item.setForeground(QColor(color))
        self.table_status.setItem(row_idx, _STATUS_COLUMN, item)

    def _emit_sync_row(self, symbol: str, interval: str, checked: bool = False) -> None:
        self.sig_sync_row_clicked.emit(symbol, interval)

    def _update_summary(self) -> None:
        total_rows = self.table_status.rowCount()
        gap_rows = 0
        for row in range(total_rows):
            status_item = self.table_status.item(row, _STATUS_COLUMN)
            if status_item and status_item.text() not in _HEALTHY_STATUSES:
                gap_rows += 1

        noun = "row" if total_rows == 1 else "rows"
        suffix = f" · {gap_rows} with gaps" if gap_rows else ""
        self.lbl_summary.setText(f"{total_rows} {noun}{suffix}")
