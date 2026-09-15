"""Turning contributions into a rendered surface (`EPIC-025` PR 1.4a).

One function, so there is exactly one path from "a module contributed a panel"
to "the user can see it" — the same reasoning `screen_wiring.py` gives for
being one function.

@par Why this is not a method on the host
`WorkbenchSurface` renders a widget into a place and knows nothing about who
contributed it, which is what lets a test drive it directly and a `preview.py`
build one with two hand-made widgets. Reading the registry and calling the
factories is the shell's job, and keeping it here is what stops the host from
growing a dependency on the contribution mechanism it is supposed to be
indifferent to.

@par Order, and what happens after it
`ContributionRegistry.panels()` already sorts by `(order, contributor_id,
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

from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.shell.contribution_registry import (
    ContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.shell.surfaces import Surface
from Sagittarius_Elite_Warrior.src.shell.workbench_surface import WorkbenchSurface
from sagittarius_engine.interfaces.i_container import IContainer

logger = logging.getLogger("App.Shell.SurfaceBuilding")

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
    contributions: ContributionRegistry,
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
