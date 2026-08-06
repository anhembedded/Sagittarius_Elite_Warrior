from PySide6.QtWidgets import (
    QPushButton,
    QFormLayout,
    QGroupBox,
    QComboBox,
    QDateTimeEdit,
    QHBoxLayout,
    QApplication,
)
from PySide6.QtCore import Signal, QDateTime, QSize
from Binace_Bot.src.presentation.ui.components.base_card import BaseCard
from Binace_Bot.src.presentation.ui.assets import IconTheme, get_icon_loader
from sagittarius_engine.extensions.pyside_mvc.ui_matrix_mixin import UIMatrixMixin
import sys


class ControlCard(BaseCard, UIMatrixMixin):
    """
    @brief Widget for User Controls on the Dashboard.n buttons and settings for controlling the bot.
    @details Inherits from BaseCard. Follows Rule 1: No DB imports, no business logic.
    """

    # Custom signals for UI interactions
    sig_load_clicked = Signal()
    sig_start_clicked = Signal()
    sig_stop_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(title="System Controls", parent=parent)
        self.setObjectName("TradingControlCard")
        self._setup_content()

    def _setup_content(self):
        # 1. Market Settings GroupBox
        group_market = QGroupBox("Thị trường")
        layout_market = QFormLayout(group_market)

        self.market_dropdown = QComboBox()
        self.market_dropdown.addItems(["Spot", "Futures"])

        self.symbol_dropdown = QComboBox()
        self.symbol_dropdown.setEditable(True)
        self.symbol_dropdown.addItems(["BTCUSDT", "ETHUSDT"])

        self.timeframe_dropdown = QComboBox()
        self.timeframe_dropdown.addItems(["1m", "5m", "15m", "1h", "1d"])

        layout_market.addRow("Market:", self.market_dropdown)
        layout_market.addRow("Symbol:", self.symbol_dropdown)
        layout_market.addRow("Timeframe:", self.timeframe_dropdown)

        # 2. Strategy & Range GroupBox
        group_strategy = QGroupBox("Chiến lược & Dữ liệu")
        layout_strategy = QFormLayout(group_strategy)

        self.strategy_dropdown = QComboBox()
        self.strategy_dropdown.addItems(["Manual", "SMA Crossover"])

        self.start_date_picker = QDateTimeEdit(QDateTime.currentDateTime().addDays(-7))
        self.start_date_picker.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.start_date_picker.setCalendarPopup(True)

        self.end_date_picker = QDateTimeEdit(QDateTime.currentDateTime())
        self.end_date_picker.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.end_date_picker.setCalendarPopup(True)

        layout_strategy.addRow("Strategy:", self.strategy_dropdown)
        layout_strategy.addRow("Start Date:", self.start_date_picker)
        layout_strategy.addRow("End Date:", self.end_date_picker)

        # 3. Action Triggers GroupBox
        group_actions = QGroupBox("Điều khiển")
        layout_actions = QHBoxLayout(group_actions)

        icon_loader = get_icon_loader()
        icon_size = QSize(16, 16)

        self.load_history_button = QPushButton("Load History")
        self.load_history_button.setObjectName("btnLoadHistory")
        self.load_history_button.setIcon(
            icon_loader.get_icon("clock", color=IconTheme.MUTED)
        )
        self.load_history_button.setIconSize(icon_size)

        self.start_stream_button = QPushButton("Start Live")
        self.start_stream_button.setObjectName("btnStart")
        self.start_stream_button.setIcon(
            icon_loader.get_icon("play", color=IconTheme.SUCCESS)
        )
        self.start_stream_button.setIconSize(icon_size)

        self.stop_stream_button = QPushButton("Stop")
        self.stop_stream_button.setObjectName("btnStop")
        self.stop_stream_button.setIcon(
            icon_loader.get_icon("square", color=IconTheme.DANGER)
        )
        self.stop_stream_button.setIconSize(icon_size)
        self.stop_stream_button.setEnabled(False)  # Disabled by default

        layout_actions.addWidget(self.load_history_button)
        layout_actions.addWidget(self.start_stream_button)
        layout_actions.addWidget(self.stop_stream_button)

        # Add groups to the BaseCard's body layout
        self.body_layout.addWidget(group_market)
        self.body_layout.addWidget(group_strategy)
        self.body_layout.addWidget(group_actions)
        self.body_layout.addStretch()

        # Connect button click events to signals
        self.load_history_button.clicked.connect(self.sig_load_clicked)
        self.start_stream_button.clicked.connect(self.sig_start_clicked)
        self.stop_stream_button.clicked.connect(self.sig_stop_clicked)

        # Removed manual set_ui_matrix and apply_ui_mode as they are provided by UIMatrixMixin


# Test block for independent rendering
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Optional: Set a basic style or theme
    app.setStyle("Fusion")

    window = ControlCard()
    window.setWindowTitle("Trading Control Card Test")
    window.resize(300, 450)
    window.show()

    sys.exit(app.exec())
