from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QLabel,
    QComboBox,
    QPushButton,
    QTableWidget,
    QProgressBar,
    QTextEdit,
    QTableWidgetItem,
    QAbstractItemView,
    QHeaderView,
)
from PySide6.QtCore import Signal
import functools


class DataManagementView(QWidget):
    """
    @brief The View for the Data Management Screen.
    @details Allows the user to select symbols, view DB status, and trigger syncs.
    """

    sig_sync_row_clicked = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # ==========================================
        # LEFT COLUMN (Controls)
        # ==========================================
        left_panel = QFrame()
        left_panel.setObjectName("ControlPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(15)

        lbl_title = QLabel("Database Management")
        lbl_title.setObjectName("PanelTitle")

        lbl_symbol = QLabel("Symbol:")
        self.cbo_symbol = QComboBox()
        self.cbo_symbol.setEditable(True)
        self.cbo_symbol.addItems(
            ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
        )

        lbl_interval = QLabel("Interval:")
        self.cbo_interval = QComboBox()
        self.cbo_interval.addItems(["1m", "5m", "15m", "1h", "1d", "1w"])

        # Date Pickers
        from PySide6.QtWidgets import QDateTimeEdit, QCheckBox
        from PySide6.QtCore import QDateTime

        self.chk_custom_time = QCheckBox("Use Custom Time Range")

        self.dt_from = QDateTimeEdit(QDateTime.currentDateTime().addDays(-30))
        self.dt_from.setCalendarPopup(True)
        self.dt_from.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_from.setEnabled(False)

        self.dt_to = QDateTimeEdit(QDateTime.currentDateTime())
        self.dt_to.setCalendarPopup(True)
        self.dt_to.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_to.setEnabled(False)

        self.chk_custom_time.toggled.connect(self.dt_from.setEnabled)
        self.chk_custom_time.toggled.connect(self.dt_to.setEnabled)

        self.btn_check_status = QPushButton("🔍 Scan Current Status")
        self.btn_check_all = QPushButton("🔍 Scan All Status")
        self.btn_sync_data = QPushButton("⬇️ Sync Current")
        self.btn_sync_all_gaps = QPushButton("⚡ Sync All Gaps")
        self.btn_clear_data = QPushButton("🗑️ Clear Local Data")

        left_layout.addWidget(lbl_title)
        left_layout.addWidget(lbl_symbol)
        left_layout.addWidget(self.cbo_symbol)
        left_layout.addWidget(lbl_interval)
        left_layout.addWidget(self.cbo_interval)

        left_layout.addSpacing(10)
        left_layout.addWidget(self.chk_custom_time)
        left_layout.addWidget(QLabel("From:"))
        left_layout.addWidget(self.dt_from)
        left_layout.addWidget(QLabel("To:"))
        left_layout.addWidget(self.dt_to)

        left_layout.addSpacing(20)
        left_layout.addWidget(self.btn_check_status)
        left_layout.addWidget(self.btn_check_all)
        left_layout.addSpacing(10)
        left_layout.addWidget(self.btn_sync_data)
        left_layout.addWidget(self.btn_sync_all_gaps)
        left_layout.addSpacing(10)
        left_layout.addWidget(self.btn_clear_data)
        left_layout.addStretch()

        # ==========================================
        # RIGHT COLUMN (Monitor)
        # ==========================================
        right_panel = QFrame()
        right_panel.setObjectName("MonitorPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(15)

        # 1. Status Table
        lbl_table = QLabel("Database Status:")
        self.table_status = QTableWidget(0, 7)
        self.table_status.setHorizontalHeaderLabels(
            [
                "Symbol",
                "Interval",
                "First Record",
                "Last Record",
                "Total Candles",
                "Status/Gaps",
                "Action",
            ]
        )

        # Apply Constraints
        self.table_status.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_status.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_status.setAlternatingRowColors(True)
        self.table_status.setShowGrid(False)
        self.table_status.verticalHeader().setVisible(False)
        header = self.table_status.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(
            6, QHeaderView.ResizeToContents
        )  # Make action column fit content

        self.table_status.setStyleSheet("""
            QTableWidget {
                background-color: transparent;
                alternate-background-color: #2b2b36;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 8px;
                outline: none;
            }
            QTableWidget::item {
                padding: 8px;
                border: none;
            }
            QHeaderView::section {
                background-color: #181825;
                color: #a6adc8;
                padding: 8px;
                border: none;
                font-weight: bold;
                border-bottom: 2px solid #313244;
            }
        """)

        # 2. Progress Bar (Indeterminate mode by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.hide()

        # 3. Log Output
        lbl_log = QLabel("Sync Logs:")
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)

        right_layout.addWidget(lbl_table)
        right_layout.addWidget(self.table_status, 2)
        right_layout.addWidget(self.progress_bar)
        right_layout.addWidget(lbl_log)
        right_layout.addWidget(self.txt_log, 1)

        # ==========================================
        # Add to Main Layout
        # ==========================================
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 3)

    def append_log(self, text: str):
        self.txt_log.append(text)

    def update_status_table(self, symbol, interval, first, last, total, status):
        """Updates or adds a row in the status table."""
        row_idx = -1
        # Search for existing row
        for i in range(self.table_status.rowCount()):
            item_symbol = self.table_status.item(i, 0)
            item_interval = self.table_status.item(i, 1)
            if (
                item_symbol
                and item_interval
                and item_symbol.text() == symbol
                and item_interval.text() == interval
            ):
                row_idx = i
                break

        # If not found, append a new row
        if row_idx == -1:
            row_idx = self.table_status.rowCount()
            self.table_status.insertRow(row_idx)

            # Add Action Button
            btn_sync = QPushButton("Sync")
            btn_sync.setMinimumHeight(25)
            btn_sync.clicked.connect(
                functools.partial(self._emit_sync_row, symbol, interval)
            )
            btn_sync.setStyleSheet("""
                QPushButton {
                    background-color: #313244;
                    color: #cdd6f4;
                    border-radius: 4px;
                    border: 1px solid #45475a;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #89b4fa;
                    color: #11111b;
                }
                QPushButton:pressed {
                    background-color: #b4befe;
                }
            """)
            self.table_status.setCellWidget(row_idx, 6, btn_sync)

        self.table_status.setItem(row_idx, 0, QTableWidgetItem(symbol))
        self.table_status.setItem(row_idx, 1, QTableWidgetItem(interval))
        self.table_status.setItem(row_idx, 2, QTableWidgetItem(str(first)))
        self.table_status.setItem(row_idx, 3, QTableWidgetItem(str(last)))
        self.table_status.setItem(row_idx, 4, QTableWidgetItem(str(total)))
        self.table_status.setItem(row_idx, 5, QTableWidgetItem(status))

    def _emit_sync_row(self, symbol: str, interval: str, checked: bool = False):
        self.sig_sync_row_clicked.emit(symbol, interval)

    def clear_table(self):
        self.table_status.setRowCount(0)

    def set_ui_matrix(self, matrix_config: dict) -> None:
        """Injects the configuration matrix for dynamic UI toggling."""
        self._ui_matrix = matrix_config

    def apply_ui_mode(self, mode: str) -> None:
        """Applies a specific UI mode dynamically using reflection."""
        if not hasattr(self, "_ui_matrix") or not self._ui_matrix:
            print("Warning: UI Matrix not set. Cannot apply mode.")
            return

        if mode not in self._ui_matrix:
            print(f"Warning: Mode '{mode}' not found in UI matrix.")
            return

        config = self._ui_matrix[mode]
        for widget_name, is_enabled in config.items():
            if hasattr(self, widget_name):
                widget = getattr(self, widget_name)
                # Ensure it's a QWidget with setEnabled capability
                if hasattr(widget, "setEnabled"):
                    widget.setEnabled(is_enabled)
            else:
                print(
                    f"Warning: Widget '{widget_name}' not found in DataManagementView."
                )
