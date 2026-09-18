"""The Settings surface's own Presenter: fills the host, owns nothing else.

Every field that used to live on the old monolithic Settings screen now
belongs to the module that owns its config keys (`trading`'s venue,
credentials and connection check; `market_data`'s venue and sync defaults) —
each contributes its own `SETTINGS_SECTION` widget, complete with its own
Presenter, the same way `dev_board`'s probes are each a module's own
factory. This class has no field of its own to load, save or validate: it
exists only to read what was contributed and place it, exactly once, at
construction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_table import (
    IContributionTable,
)
from Sagittarius_Elite_Warrior.src.shell.settings.settings_view import SettingsView
from Sagittarius_Elite_Warrior.src.support.ui_kit.surface_building import (
    fill_settings_surface,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

SETTINGS_SURFACE_ID = "settings"


class SettingsPresenter(BasePresenter):
    """@brief Fills the Settings surface with every module's contributed section."""

    def __init__(self, view: SettingsView, container: IContainer) -> None:
        super().__init__(view, container)
        contributions = container.resolve(IContributionTable)
        fill_settings_surface(
            view.surface, SETTINGS_SURFACE_ID, contributions, container
        )
