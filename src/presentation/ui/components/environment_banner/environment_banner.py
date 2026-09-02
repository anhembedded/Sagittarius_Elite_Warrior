"""`EnvironmentBanner` — a `kit.Banner` pre-filled from a `VenueAlignment`
(`EPIC-021K`)."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.kit.surfaces.banner import Banner

from .environment_banner_content import EnvironmentBannerContent


class EnvironmentBanner(Banner):
    """@brief The "which venue am I in" banner, shown once per screen via
    `PageShell`'s own header — see `page_shell.py`'s
    `set_environment_banner_factory`. Never constructed by a screen
    directly."""

    def __init__(
        self, content: EnvironmentBannerContent, parent: QWidget | None = None
    ) -> None:
        super().__init__(
            content.message,
            severity=content.severity,
            icon=content.icon,
            parent=parent,
        )
        self.setObjectName("environmentBanner")
