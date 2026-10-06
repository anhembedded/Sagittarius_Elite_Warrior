"""`EPIC-028J` — a desk's account summary: a short list of labelled
figures, and a stale mark when they can no longer be trusted.

@details The stale mark is a sentence above the figures, with the reason
`AccountSummaryStaleEvent` carries (`EPIC-028Q`), not a colour: ADR D21
leaves colour to the system colour scheme. The figures stay visible while stale, as
the last ones read, because the mark says what they are.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.readout_slot import (
    Readout,
    ReadoutSlot,
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
        self._figures = ReadoutSlot()
        self._figures.setObjectName("roAccountSummary")
        layout = QVBoxLayout(self)
        layout.addWidget(self._stale)
        layout.addWidget(self._unread)
        layout.addWidget(self._figures)
        layout.addStretch(1)

    def show_readout(self, readout: Readout | None) -> None:
        """The figures, or none while the account is unread."""
        if readout is None:
            self._figures.clear()
        else:
            self._figures.show_readout(readout)
        self._unread.setVisible(readout is None)

    def mark_stale(self, reason: str) -> None:
        self._stale.setText(f"Out of date: {reason}")
        self._stale.show()

    def clear_stale(self) -> None:
        self._stale.clear()
        self._stale.hide()

    @property
    def stale_text(self) -> str:
        return "" if self._stale.isHidden() else self._stale.text()

    def value_of(self, key: str) -> str | None:
        """The text shown for the row `key`, or `None` when it is not shown."""
        return self._figures.value_text(key)
