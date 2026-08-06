from PySide6.QtWidgets import QTextEdit, QPushButton
from PySide6.QtCore import Signal, QSize
from datetime import datetime
from Binace_Bot.src.presentation.ui.components.base_card import BaseCard
from Binace_Bot.src.presentation.ui.assets import IconTheme, get_icon_loader

# level -> (Lucide icon name, theme color)
_LEVEL_ICONS = {
    "info": ("info", IconTheme.MUTED),
    "error": ("triangle-alert", IconTheme.DANGER),
    "success": ("circle-check-big", IconTheme.SUCCESS),
}
_LOG_ICON_SIZE = 14


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
        self.btn_clear.setIcon(
            get_icon_loader().get_icon("trash-2", color=IconTheme.MUTED)
        )
        self.btn_clear.setIconSize(QSize(14, 14))
        self.btn_clear.setMaximumWidth(80)
        self.btn_clear.clicked.connect(self.clear_logs_clicked.emit)
        self.add_to_header(self.btn_clear)

        # Log Text Area in the body
        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("terminal_log")
        self.text_edit.setReadOnly(True)

        self.body_layout.addWidget(self.text_edit)

    def append_log(self, message: str, level: str = "info") -> None:
        """
        @param level One of "info" (default), "error", "success" — selects the inline
        icon shown next to the log line. Unknown levels fall back to "info".
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        icon_name, color = _LEVEL_ICONS.get(level, _LEVEL_ICONS["info"])
        icon_uri = get_icon_loader().get_icon_data_uri(
            icon_name, color=color, size=_LOG_ICON_SIZE
        )
        self.text_edit.append(
            f'<img src="{icon_uri}" width="{_LOG_ICON_SIZE}" height="{_LOG_ICON_SIZE}"/> '
            f"[{timestamp}] {message}"
        )

    def clear_logs(self) -> None:
        self.text_edit.clear()
