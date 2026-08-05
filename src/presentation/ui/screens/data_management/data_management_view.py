from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel, 
    QComboBox, QPushButton, QTableWidget, QProgressBar, QTextEdit, QTableWidgetItem,
    QAbstractItemView, QHeaderView
)
from PySide6.QtCore import Qt

class DataManagementView(QWidget):
    """
    @brief The View for the Data Management Screen.
    @details Allows the user to select symbols, view DB status, and trigger syncs.
    """
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
        self.cbo_symbol.addItems(["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"])

        lbl_interval = QLabel("Interval:")
        self.cbo_interval = QComboBox()
        self.cbo_interval.addItems(["1m", "5m", "15m", "1h", "1d", "1w"])

        self.btn_check_status = QPushButton("🔍 Scan DB Status")
        self.btn_sync_data = QPushButton("⬇️ Sync from Binance")
        self.btn_clear_data = QPushButton("🗑️ Clear Local Data")

        left_layout.addWidget(lbl_title)
        left_layout.addWidget(lbl_symbol)
        left_layout.addWidget(self.cbo_symbol)
        left_layout.addWidget(lbl_interval)
        left_layout.addWidget(self.cbo_interval)
        left_layout.addSpacing(20)
        left_layout.addWidget(self.btn_check_status)
        left_layout.addWidget(self.btn_sync_data)
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
        self.table_status = QTableWidget(0, 6)
        self.table_status.setHorizontalHeaderLabels([
            "Symbol", "Interval", "First Record", "Last Record", "Total Candles", "Status/Gaps"
        ])
        
        # Apply Constraints
        self.table_status.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_status.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_status.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

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
        self.table_status.setRowCount(0) 
        self.table_status.insertRow(0)
        self.table_status.setItem(0, 0, QTableWidgetItem(symbol))
        self.table_status.setItem(0, 1, QTableWidgetItem(interval))
        self.table_status.setItem(0, 2, QTableWidgetItem(str(first)))
        self.table_status.setItem(0, 3, QTableWidgetItem(str(last)))
        self.table_status.setItem(0, 4, QTableWidgetItem(str(total)))
        self.table_status.setItem(0, 5, QTableWidgetItem(status))
