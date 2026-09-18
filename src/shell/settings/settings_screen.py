"""The Settings screen as a contribution — the shell's own (`EPIC-025` PR 4.4e).

Like `welcome_screen()`, arrives through the same `ScreenContribution` every
other screen does. Unlike Welcome, this surface's own `WORKSPACE`/`HEADER`
carry nothing the shell built itself — every field a user sees here is a
`SETTINGS_SECTION` some *other* module contributed (HLD §4.3), which is what
"settings becomes a surface" (`EPIC-025E` §3.15(e)) means: the shell only
owns the frame, never the fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.contribution_descriptor import (
    SHELL_CONTRIBUTOR_ID,
)
from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import (
    NavLocation,
    NavMetadata,
)
from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)
from sagittarius_engine.interfaces.i_container import IContainer

if TYPE_CHECKING:
    from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView

SETTINGS_ROUTE = "settings"

#: Pinned to the sidebar's bottom action row, same position the legacy
#: `SettingsScreenModule` held (`item_sequence=10`), so the move is invisible
#: to the user's muscle memory.
_NAV = NavMetadata(
    title="Settings",
    icon="settings",
    location=NavLocation.BOTTOM_ACTION,
    item_sequence=10,
)


def _build_settings_view() -> BaseView:
    """Builds the view, importing it only now — the same lazy shape
    `welcome_screen.py` uses and for the same reason: this file is imported
    by `shell/contribution_assembly.py`, which the headless entry point
    imports too."""
    from Sagittarius_Elite_Warrior.src.shell.settings.settings_view import (
        SettingsView,
    )

    return SettingsView()


def _build_settings_presenter(view: BaseView, container: IContainer) -> BasePresenter:
    """Builds the Presenter, checking the view it was handed — the same real
    check `welcome_screen.py`'s own factory makes, for the same reason: a
    wiring mistake here would otherwise fail later inside a slot with an
    `AttributeError` naming nothing useful."""
    from Sagittarius_Elite_Warrior.src.shell.settings.settings_presenter import (
        SettingsPresenter,
    )
    from Sagittarius_Elite_Warrior.src.shell.settings.settings_view import (
        SettingsView,
    )

    if not isinstance(view, SettingsView):
        raise TypeError(
            f"the Settings screen's presenter was handed a {type(view).__name__}, "
            "not a SettingsView"
        )
    return SettingsPresenter(view, container)


def settings_screen() -> ScreenContribution:
    """The shell's Settings screen, described the way a module would
    describe one."""
    return ScreenContribution(
        contributor_id=SHELL_CONTRIBUTOR_ID,
        route=SETTINGS_ROUTE,
        view_factory=_build_settings_view,
        presenter_factory=_build_settings_presenter,
        nav=_NAV,
    )
