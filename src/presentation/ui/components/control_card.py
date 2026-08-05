from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Signal
from Binace_Bot.src.presentation.ui.components.base_card import BaseCard

class ControlCard(BaseCard):
    """
    @brief A dumb component containing action buttons for controlling the bot.
    @details Inherits from BaseCard. Follows Rule 1: No DB imports, no business logic.
    """
    
    start_stream_clicked = Signal()
    stop_stream_clicked = Signal()
    run_backtest_clicked = Signal()
    stop_backtest_clicked = Signal()
    load_history_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(title="System Controls", parent=parent)
        self._setup_content()
        self.set_stream_active(False)
        self.set_backtest_active(False)

    def _setup_content(self):
        # Action Buttons
        self.btn_load_history = QPushButton("Load Local History")
        self.btn_start_stream = QPushButton("Start Live Stream")
        self.btn_stop_stream = QPushButton("Stop Live Stream")
        self.btn_run_backtest = QPushButton("Run Backtest")
        self.btn_stop_backtest = QPushButton("Stop Backtest")

        # Connect button click events
        self.btn_load_history.clicked.connect(self.load_history_clicked.emit)
        self.btn_start_stream.clicked.connect(self.start_stream_clicked.emit)
        self.btn_stop_stream.clicked.connect(self.stop_stream_clicked.emit)
        self.btn_run_backtest.clicked.connect(self.run_backtest_clicked.emit)
        self.btn_stop_backtest.clicked.connect(self.stop_backtest_clicked.emit)

        # Add buttons to the BaseCard's body layout
        self.body_layout.addWidget(self.btn_load_history)
        self.body_layout.addWidget(self.btn_start_stream)
        self.body_layout.addWidget(self.btn_stop_stream)
        self.body_layout.addWidget(self.btn_run_backtest)
        self.body_layout.addWidget(self.btn_stop_backtest)
        self.body_layout.addStretch()

    def set_stream_active(self, is_active: bool) -> None:
        self.btn_start_stream.setEnabled(not is_active)
        self.btn_stop_stream.setEnabled(is_active)
        
    def set_backtest_active(self, is_active: bool) -> None:
        self.btn_run_backtest.setEnabled(not is_active)
        self.btn_stop_backtest.setEnabled(is_active)
