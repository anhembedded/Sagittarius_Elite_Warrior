"""A notice above the Backtest figures: an icon, a message, and at most one
action (`EPIC-033L` stage 4).

Built from stock parts: a styled-panel `QFrame`, the platform's own
information or warning icon (`QStyle.StandardPixmap`), a word-wrapped
`QLabel` and a `QPushButton`. It replaces the kit `Banner`, a panel painted
in a severity colour with an icon tinted from the app palette. The icon and
the words carry the severity, so it reads the same in High Contrast.

One consumer, so it lives with it; a second mode wanting a notice moves it
to `support/ui_kit`.
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QWidget,
)


class NoticeKind(Enum):
    """Which of the platform's message icons a notice shows."""

    INFORMATION = QStyle.StandardPixmap.SP_MessageBoxInformation
    WARNING = QStyle.StandardPixmap.SP_MessageBoxWarning
    CRITICAL = QStyle.StandardPixmap.SP_MessageBoxCritical


class NoticeBar(QFrame):
    """@brief A message the person should see, and what they can do about it."""

    def __init__(
        self,
        kind: NoticeKind,
        object_name: str,
        action_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        icon = QLabel()
        size = self.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)
        icon.setPixmap(self.style().standardIcon(kind.value).pixmap(size, size))
        self._message = QLabel()
        self._message.setWordWrap(True)
        self.action_button = QPushButton(action_text)
        self.action_button.setVisible(bool(action_text))
        row = QHBoxLayout(self)
        row.addWidget(icon)
        row.addWidget(self._message, 1)
        row.addWidget(self.action_button)

    @property
    def text(self) -> str:
        return self._message.text()

    @text.setter
    def text(self, value: str) -> None:
        self._message.setText(value)
