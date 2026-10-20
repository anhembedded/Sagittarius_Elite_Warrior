"""A notice above a panel's content: an icon, a message, and at most one
action (`EPIC-033L` stage 4).

Built from stock parts: a styled-panel `QFrame`, the platform's own
information or warning icon (`QStyle.StandardPixmap`), a word-wrapped
`QLabel` and a `QPushButton`. It replaces the kit `Banner`, a panel painted
in a severity colour with an icon tinted from the app's own colours. The icon and
the words carry the severity, so it reads the same in High Contrast.

Two consumers (the Backtest figures and the Bots Plan dock's status banner, `BOT-209`), so it
lives here. `show_notice` re-words a bar whose severity changes; its action is optional.

Capability: A message with a severity icon and at most one action, above a panel's content
    Also: banner, inline message, notice, status banner, info bar, warning bar
    Use: NoticeBar, NoticeKind
    User: src/modules/bots/ui/bots_screen/plan_status_banner.py
    Status: stable
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QStyle,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label


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
        self._icon = plain_label()
        self._kind = kind
        self._show_icon()
        self._message = plain_label()
        self._message.setWordWrap(True)
        self.action_button = QPushButton(action_text)
        self.action_button.setVisible(bool(action_text))
        row = QHBoxLayout(self)
        row.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self._message, 1)
        row.addWidget(self.action_button)

    @property
    def text(self) -> str:
        return self._message.text()

    @text.setter
    def text(self, value: str) -> None:
        self._message.setText(value)

    @property
    def kind(self) -> NoticeKind:
        return self._kind

    def show_notice(
        self, kind: NoticeKind, text: str, accessible_name: str = ""
    ) -> None:
        """Says `text` under `kind`'s icon. The icon's words go to a screen reader: the kit's
        own ("Error" for a critical notice), or `accessible_name` where the consumer knows what
        the notice means on its screen ("Blocks Start")."""
        self._kind = kind
        self._show_icon()
        self._icon.setAccessibleName(accessible_name or _ACCESSIBLE_NAME[kind])
        self.text = text

    def _show_icon(self) -> None:
        size = self.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)
        self._icon.setPixmap(
            self.style().standardIcon(self._kind.value).pixmap(size, size)
        )
        self._icon.setAccessibleName(_ACCESSIBLE_NAME[self._kind])


_ACCESSIBLE_NAME = {
    NoticeKind.INFORMATION: "Information",
    NoticeKind.WARNING: "Warning",
    NoticeKind.CRITICAL: "Error",
}
