"""`EnvironmentBanner` — the "which venue am I in" banner, filled from a
`EnvironmentBannerContent` (`EPIC-021K`)."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

from .environment_banner_content import BannerSeverity, EnvironmentBannerContent


class EnvironmentBanner(QFrame):
    """@brief The "which venue am I in" banner, one line of stock labels in a
    platform-styled frame, placed once per mode by the workbench host
    (`WorkbenchSurface.set_environment_banner_factory`). Never constructed by
    a screen directly.

    @details Severity is carried by the icon and the message's weight, never
    by a colour of its own: the frame, the text and the background are the
    platform's.
    """

    def __init__(
        self, content: EnvironmentBannerContent, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("environmentBanner")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._severity = content.severity

        self._icon_label = plain_label(content.icon)
        self._icon_label.setVisible(bool(content.icon))
        self._message_label = plain_label(content.message)
        self._message_label.setWordWrap(True)
        if content.severity is BannerSeverity.DANGER:
            font = self._message_label.font()
            font.setBold(True)
            self._message_label.setFont(font)

        row = QHBoxLayout(self)
        row.addWidget(self._icon_label)
        row.addWidget(self._message_label, 1)

    @property
    def severity(self) -> BannerSeverity:
        return self._severity

    @property
    def message(self) -> str:
        return self._message_label.text()

    @property
    def icon(self) -> str:
        return self._icon_label.text()
