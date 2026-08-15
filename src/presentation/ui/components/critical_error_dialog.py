from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QTextEdit,
    QVBoxLayout,
)


class CriticalErrorDialog(QDialog):
    """
    @brief Resizable critical error dialog for uncaught UI and system exceptions.
    @details Allows user to freely resize, maximize, toggle details, and copy full
    tracebacks to clipboard without getting clipped or locked to a rigid fixed size.
    """

    def __init__(
        self,
        title: str = "Critical System Error",
        message: str = "An unexpected error occurred in the UI layer.",
        error_details: str = "",
        traceback_str: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(540, 240)
        self.resize(620, 320)
        self.setSizeGripEnabled(True)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )

        self._traceback_str = traceback_str
        self._error_details = error_details

        self._init_ui(message, error_details, traceback_str)

    def _init_ui(self, message: str, error_details: str, traceback_str: str) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header Row with Icon and Error Summary
        header_row = QHBoxLayout()
        header_row.setSpacing(14)
        header_row.setAlignment(Qt.AlignmentFlag.AlignTop)

        icon_label = QLabel(self)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)
        icon_label.setPixmap(icon.pixmap(40, 40))
        icon_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        header_row.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(6)

        title_lbl = QLabel(message, self)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        title_lbl.setFont(title_font)
        title_lbl.setWordWrap(True)
        text_layout.addWidget(title_lbl)

        if error_details:
            details_lbl = QLabel(error_details, self)
            details_lbl.setWordWrap(True)
            text_layout.addWidget(details_lbl)

        header_row.addLayout(text_layout)
        main_layout.addLayout(header_row)

        # Action Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self._btn_copy = QPushButton("Copy Error", self)
        self._btn_copy.clicked.connect(self._copy_to_clipboard)
        btn_row.addWidget(self._btn_copy)

        self._btn_details = QPushButton("Show Details...", self)
        self._btn_details.setCheckable(True)
        self._btn_details.clicked.connect(self._toggle_details)
        btn_row.addWidget(self._btn_details)

        self._btn_ok = QPushButton("OK", self)
        self._btn_ok.setDefault(True)
        self._btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(self._btn_ok)

        main_layout.addLayout(btn_row)

        # Details Text Edit (Hidden initially, expandable when toggled)
        self._details_edit = QTextEdit(self)
        self._details_edit.setReadOnly(True)
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._details_edit.setFont(font)
        self._details_edit.setText(traceback_str or error_details)
        self._details_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._details_edit.setVisible(False)
        main_layout.addWidget(self._details_edit, 1)

    def _toggle_details(self) -> None:
        is_visible = self._btn_details.isChecked()
        self._details_edit.setVisible(is_visible)
        self._btn_details.setText(
            "Hide Details..." if is_visible else "Show Details..."
        )
        if is_visible:
            self.resize(max(self.width(), 650), max(self.height() + 200, 480))
        else:
            self.resize(self.width(), max(self.minimumHeight(), 260))

    def _copy_to_clipboard(self) -> None:
        full_text = (
            f"Error: {self._error_details}\n\nTraceback:\n{self._traceback_str}"
            if self._traceback_str
            else self._error_details
        )
        QGuiApplication.clipboard().setText(full_text)
        self._btn_copy.setText("Copied!")


def show_critical_error_dialog(
    exc_type: type[BaseException] | None,
    exc_value: BaseException | None,
    exc_tb,
    title: str = "Critical System Error",
    message: str = "An unexpected error occurred in the UI layer.",
    parent=None,
) -> int:
    """Convenience helper to construct and show a CriticalErrorDialog from an exception."""
    import traceback

    tb_str = (
        "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        if exc_type
        else ""
    )
    dialog = CriticalErrorDialog(
        title=title,
        message=message,
        error_details=str(exc_value) if exc_value else "",
        traceback_str=tb_str,
        parent=parent,
    )
    return dialog.exec()
