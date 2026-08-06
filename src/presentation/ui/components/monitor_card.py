from PySide6.QtWidgets import QTextEdit, QPushButton
from PySide6.QtCore import Signal, Qt
from datetime import datetime
from Binace_Bot.src.presentation.ui.components.base_card import BaseCard


class MonitorCard(BaseCard):
    """
    @brief A dumb component containing a QTextEdit for displaying logs.
    @details Inherits from BaseCard. Follows Rule 1: No DB imports, no business logic.
    """

    # Signal emitted when the user clicks the clear button
    clear_logs_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(title="System Monitor", parent=parent)
        self._setup_content()

    def _setup_content(self):
        # Add clear button to the header of the BaseCard
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setMaximumWidth(80)
        self.btn_clear.setToolTip("Clear all system logs")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self.clear_logs_clicked.emit)
        self.add_to_header(self.btn_clear)

        # Log Text Area in the body
        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("terminal_log")
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlaceholderText("System logs will appear here...")

        self.body_layout.addWidget(self.text_edit)

    def append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.text_edit.append(f"[{timestamp}] {message}")

    def clear_logs(self) -> None:
        self.text_edit.clear()
