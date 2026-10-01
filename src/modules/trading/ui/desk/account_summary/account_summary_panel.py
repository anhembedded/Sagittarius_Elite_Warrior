"""`EPIC-028J` — a desk's account summary: a short list of labelled
figures, and a stale mark when they can no longer be trusted.

@details The stale mark is a sentence above the figures, with the reason
`AccountSummaryStaleEvent` carries (`EPIC-028Q`), not a colour: ADR D21
leaves colour to the OS palette. The figures stay visible while stale, as
the last ones read, because the mark says what they are.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_summary.summary_lines import (
    SummaryLine,
)

_UNREAD_TEXT = "The account has not been read yet."


class AccountSummaryPanel(QWidget):  # base-exempt: a container, not a surface
    """@brief One desk's account figures."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._stale = QLabel()
        self._stale.setObjectName("lblAccountSummaryStale")
        self._stale.setWordWrap(True)
        self._stale.hide()
        self._unread = QLabel(_UNREAD_TEXT)
        self._unread.setObjectName("lblAccountSummaryUnread")
        self._unread.setWordWrap(True)
        self._figures = QFormLayout()
        self._values: dict[str, QLabel] = {}
        layout = QVBoxLayout(self)
        layout.addWidget(self._stale)
        layout.addWidget(self._unread)
        layout.addLayout(self._figures)
        layout.addStretch(1)

    def set_lines(self, lines: Sequence[SummaryLine]) -> None:
        while self._figures.rowCount():
            self._figures.removeRow(0)
        self._values = {}
        for line in lines:
            value = QLabel(line.value_text)
            value.setObjectName(f"lblSummary{line.label.replace(' ', '')}")
            self._figures.addRow(f"{line.label}:", value)
            self._values[line.label] = value
        self._unread.setVisible(not lines)

    def mark_stale(self, reason: str) -> None:
        self._stale.setText(f"Out of date: {reason}")
        self._stale.show()

    def clear_stale(self) -> None:
        self._stale.clear()
        self._stale.hide()

    @property
    def stale_text(self) -> str:
        return "" if self._stale.isHidden() else self._stale.text()

    def value_of(self, label: str) -> str | None:
        """The text shown for `label`, or `None` when it is not shown."""
        value = self._values.get(label)
        return value.text() if value is not None else None
