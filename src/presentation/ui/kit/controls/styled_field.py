"""
@brief `StyledField` — a `QLineEdit` with the app's field chrome.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QWidget

from ..style import StyleRole, apply_role


class StyledField(QLineEdit):
    """A `QLineEdit` styled to match the app's field chrome."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        apply_role(self, StyleRole.FIELD)
