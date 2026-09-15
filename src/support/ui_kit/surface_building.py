"""Turning contributions into a rendered surface (`EPIC-025` PR 1.4a).

One function, so there is exactly one path from "a module contributed a panel"
to "the user can see it" — the same reasoning `screen_wiring.py` gives for
being one function.

@par Why it lives beside the host rather than in the shell
It was written in `shell/` (PR 1.4a) and moved here (PR 1.4b) for a measured
reason: during the strangler period a *legacy screen* and a *module's `ui/`*
both need to render a surface, and neither may import `shell/` — the shell is
*Main*, so a dependency on it is a cycle by definition. Both may import
`support/ui_kit` whole, which is the zone HLD §6.1 named for exactly this. What
stayed in the shell is the policy: which surfaces exist, and the registry that
collects what was contributed to them.

@par Why this is not a method on the host
`WorkbenchSurface` renders a widget into a place and knows nothing about who
contributed it, which is what lets a test drive it directly and a `preview.py`
build one with two hand-made widgets. Reading the table and calling the
factories is a separate job, and keeping it in a separate function is what
stops the host from growing a dependency on the contribution mechanism it is
supposed to be indifferent to.

@par Order, and what happens after it
`IContributionTable.panels()` already sorts by `(order, contributor_id,
factory)`, so this walks places in a fixed sequence and lets that sort decide
within each. From then on the user's saved perspective wins — `order` is the
initial arrangement, not a layout (HLD §11.2).

@par A factory that raises
It takes the surface down, deliberately, and nothing here catches it. A panel
that cannot be built is a programming error in the module that contributed it,
and the descriptor's whole point is that the factory runs late enough to name
the module in the traceback. Swallowing it would show the user a workbench
with a hole where a panel should be and no way to find out why.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_table import (
    IContributionTable,
)
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)
from sagittarius_engine.interfaces.i_container import IContainer

logger = logging.getLogger("App.UiKit.SurfaceBuilding")

#: The order places are filled in. Not cosmetic: the workspace must exist
#: before the docks so Qt sizes the dock areas around a real central widget,
#: and the context bar's row is created after the header's (see the host).
_FILL_ORDER: tuple[Place, ...] = (
    Place.HEADER,
    Place.CONTEXT_BAR,
    Place.WORKSPACE,
    Place.RAIL,
    Place.CONSOLE,
    Place.DEV_PROBE,
    Place.STATUS_TILE,
    Place.MODAL,
)


def build_surface(
    surface: Surface,
    contributions: IContributionTable,
    container: IContainer,
    *,
    parent: object | None = None,
) -> WorkbenchSurface:
    """Builds `surface` and fills every place it accepts, in `_FILL_ORDER`."""
    host = WorkbenchSurface(surface, parent)  # type: ignore[arg-type]
    placed = 0
    for place in _FILL_ORDER:
        if place not in surface.accepts:
            continue
        for descriptor in contributions.panels(surface.surface_id, place):
            host.place_widget(
                place,
                descriptor.factory(container),
                title=descriptor.title,
            )
            placed += 1
    logger.info(
        "Surface %r built with %d contributed widget(s).",
        surface.surface_id,
        placed,
    )
    return host
