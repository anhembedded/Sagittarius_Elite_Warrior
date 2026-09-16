"""
@brief `DateTimeField` — a `QDateTimeEdit` with the app's field chrome.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDateTimeEdit, QWidget

from ..style import StyleRole, apply_role


class DateTimeField(QDateTimeEdit):
    """
    @brief A `QDateTimeEdit` styled to match the app's field chrome — the
    QtWidgets replacement for the QML kit's hand-rolled `DateTimePicker`
    (400 LOC), most of which was reimplementing calendar/time popups
    `QDateTimeEdit` already provides.

    @details Extends `QDateTimeEdit`, **not** `StyledField`: `QDateTimeEdit`
    inherits `QAbstractSpinBox`, not `QLineEdit` (verified against the real
    Qt class hierarchy; an earlier draft of this package's architecture had
    this wrong, for the same reason its first draft wrongly gave `Overlay`
    two Qt bases).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        apply_role(self, StyleRole.FIELD)
