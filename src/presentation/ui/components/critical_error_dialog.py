"""The dialog an uncaught exception ends in: what failed, and its traceback.

Stock parts in the platform's look (`ui-presentation-rule.md` §1, §7): the
platform's critical icon, the message in the system font made bold, a
"Show details" check box for the traceback (state is a check box, never a
checkable push button, §6), and a `QDialogButtonBox` whose one commit
button is Close, because a problem is never "OK" (§4). The details are in
the platform's fixed-pitch font, as every column of digits is. Nothing sets
a size the style should decide (§3); the dialog opens at a size that shows
the message and grows with its details.
"""

from __future__ import annotations

import traceback

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QStyle,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

_DEFAULT_DIALOG_WIDTH: int = 620
_DEFAULT_DIALOG_HEIGHT: int = 320
_EXPANDED_HEIGHT_DELTA: int = 200
_DEFAULT_ICON_SIZE: int = 40
SHOW_DETAILS_TEXT = "Show details"
COPY_TEXT = "Copy error"
COPIED_TEXT = "Copied"


class CriticalErrorDialog(QDialog):
    """
    @brief Resizable critical error dialog for uncaught UI and system exceptions.
    @details The person can resize and maximize it, show or hide the
    traceback, and copy the whole error to the clipboard.
    """

    def __init__(
        self,
        title: str = "Critical System Error",
        message: str = "An unexpected error occurred in the UI layer.",
        error_details: str = "",
        traceback_str: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(_DEFAULT_DIALOG_WIDTH, _DEFAULT_DIALOG_HEIGHT)
        self.setSizeGripEnabled(True)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self._traceback_str = traceback_str
        self._error_details = error_details
        self._show_details = QCheckBox(SHOW_DETAILS_TEXT, self)
        self._show_details.setObjectName("chkShowErrorDetails")
        self._details_edit = QTextEdit(self)
        self._details_edit.setObjectName("txtErrorDetails")
        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self._btn_copy = self._buttons.addButton(
            COPY_TEXT, QDialogButtonBox.ButtonRole.ActionRole
        )
        self._build(message, error_details, traceback_str)

    @property
    def copy_button(self) -> QPushButton:
        return self._btn_copy

    @property
    def show_details(self) -> QCheckBox:
        return self._show_details

    @property
    def details(self) -> QTextEdit:
        return self._details_edit

    def _build(self, message: str, error_details: str, traceback_str: str) -> None:
        column = QVBoxLayout(self)
        header = QHBoxLayout()
        header.setAlignment(Qt.AlignmentFlag.AlignTop)
        icon_label = plain_label(parent=self)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)
        icon_label.setPixmap(icon.pixmap(_DEFAULT_ICON_SIZE, _DEFAULT_ICON_SIZE))
        header.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        title_lbl = plain_label(message, self)
        title_font = title_lbl.font()
        title_font.setBold(True)
        title_lbl.setFont(title_font)
        title_lbl.setWordWrap(True)
        text.addWidget(title_lbl)
        if error_details:
            details_lbl = plain_label(error_details, self)
            details_lbl.setWordWrap(True)
            text.addWidget(details_lbl)
        header.addLayout(text, 1)
        column.addLayout(header)
        column.addWidget(self._show_details)
        self._details_edit.setReadOnly(True)
        self._details_edit.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self._details_edit.setText(traceback_str or error_details)
        self._details_edit.setVisible(False)
        column.addWidget(self._details_edit, 1)
        column.addWidget(self._buttons)
        self._buttons.button(QDialogButtonBox.StandardButton.Close).setDefault(True)
        self._buttons.rejected.connect(self.reject)
        self._btn_copy.clicked.connect(self._copy_to_clipboard)
        self._show_details.toggled.connect(self._toggle_details)

    def _toggle_details(self, shown: bool) -> None:
        self._details_edit.setVisible(shown)
        if shown:
            self.resize(self.width(), self.height() + _EXPANDED_HEIGHT_DELTA)
        else:
            self.adjustSize()

    def _copy_to_clipboard(self) -> None:
        full_text = (
            f"Error: {self._error_details}\n\nTraceback:\n{self._traceback_str}"
            if self._traceback_str
            else self._error_details
        )
        QGuiApplication.clipboard().setText(full_text)
        self._btn_copy.setText(COPIED_TEXT)


def show_critical_error_dialog(
    exc_type: type[BaseException] | None,
    exc_value: BaseException | None,
    exc_tb,
    title: str = "Critical System Error",
    message: str = "An unexpected error occurred in the UI layer.",
    parent: QWidget | None = None,
) -> int:
    """Convenience helper to construct and show a CriticalErrorDialog from an exception."""
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
