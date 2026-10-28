"""`EPIC-047E` - the VPS Bots tab as a contribution of the shell, which owns the link.

@details The tab is the Bots screen's own view and presenter classes (charter O4, AC7) built over the VPS host's link, so the
screen is `bots_screen()` with another route, other commands (the Bots tab's, under `bots.vps` ids) and a presenter factory
that hands the Bots presenter a container carrying the tab's session. Lazy, as every `ScreenContribution` must be: the
factories are `Deferred` paths and nothing here imports Qt.

The shell contributes it, not the Bots module: the module may not hold the transport (`IVpsTab` is its door) and the link is
the shell's (`shell/vps_tab/vps_tab_session.py`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)
from Sagittarius_Elite_Warrior.src.core.contracts.deferred import Deferred
from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import NavMetadata
from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)
from Sagittarius_Elite_Warrior.src.shell.surfaces import (
    VPS_BOTS_SURFACE_ID,
    surfaces_by_id,
)

if TYPE_CHECKING:
    from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView

#: Also the id of the tab's surface (`shell/surfaces.py`): `test_the_vps_tab_is_the_bots_screen.py` holds the two equal.
VPS_BOTS_ROUTE = "vps_bots"
#: Right after the Bots tab (18).
_NAV = NavMetadata(
    title="VPS Bots",
    access_key="v",
    icon="bot",
    section_sequence=10,
    item_sequence=19,
)
_BOTS_UI = "Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen"
#: The Bots screen's view on this mode's own surface and Output pane channel (`BotsView(surface, channel_title)`).
_VIEW: Deferred[BaseView] = Deferred(
    f"{_BOTS_UI}.bots_view:BotsView", surfaces_by_id()[VPS_BOTS_SURFACE_ID], _NAV.title
)
_COMMANDS: Deferred[tuple[CommandContribution, ...]] = Deferred(
    f"{_BOTS_UI}.vps_command_ids:vps_commands"
)
_PRESENTER: Deferred[BasePresenter] = Deferred(
    "Sagittarius_Elite_Warrior.src.shell.vps_tab.vps_tab_builder:build_vps_presenter"
)


def vps_bots_screen() -> ScreenContribution:
    return ScreenContribution(
        contributor_id="shell",
        route=VPS_BOTS_ROUTE,
        view_factory=_VIEW,
        presenter_factory=_PRESENTER,
        nav=_NAV,
    )


def vps_bots_commands() -> tuple[CommandContribution, ...]:
    """The Bots tab's commands, under the VPS tab's ids, in the VPS tab's mode."""
    return _COMMANDS(VPS_BOTS_ROUTE)
