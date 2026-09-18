"""The Settings surface's own View: an empty host, filled by the Presenter.

`ScreenContribution.view_factory` takes no `container` (`core/contracts/
screen_contribution.py`), so this class cannot read what was contributed —
only `SettingsPresenter`, built with one, can. Mirrors `WelcomeView`'s split:
the View owns the host and nothing about who fills it.

A `PageShell` like every other screen (the deleted monolithic
`SettingsView` was one too) — not a `WorkbenchSurface`: this screen has no
rail/console/chart, and `PageShell`'s header band is what carries the
`EPIC-021K` environment banner every navigable screen must show
(`tests/unit/presentation/ui/test_environment_banner_all_screens.py`).
"""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import PageShell
from Sagittarius_Elite_Warrior.src.support.ui_kit.settings_surface import (
    SettingsSurface,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView


class SettingsView(BaseView):
    """@brief The Settings surface's one widget: a `SettingsSurface` host."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._surface = SettingsSurface(surfaces_by_id()["settings"])

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        shell = PageShell()
        shell.set_header("Settings", "Each module's own configuration")
        shell.set_workspace(self._surface)
        outer.addWidget(shell)

    @property
    def surface(self) -> SettingsSurface:
        """For the Presenter to fill, and for a test to inspect."""
        return self._surface
