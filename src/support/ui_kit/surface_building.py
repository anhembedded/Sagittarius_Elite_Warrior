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
from Sagittarius_Elite_Warrior.src.support.ui_kit.settings_surface import (
    SettingsSurface,
)
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
    surface_id: str,
    contributions: IContributionTable,
    container: IContainer,
    *,
    parent: object | None = None,
) -> WorkbenchSurface:
    """Builds the surface named `surface_id` and fills every place it accepts,
    in `_FILL_ORDER`.

    An id rather than a `Surface`: the table that knows what was contributed
    knows the declaration too (PR 1.4c-1), and asking it for both is what lets
    a caller render a surface without naming this application's surface list —
    which `shell/` owns and neither `support/*` nor a legacy screen may
    import.
    """
    host = WorkbenchSurface(contributions.surface(surface_id), parent)  # type: ignore[arg-type]
    fill_surface(host, contributions, container)
    return host


def fill_surface(
    host: WorkbenchSurface,
    contributions: IContributionTable,
    container: IContainer,
) -> int:
    """Fills a host that already exists, and answers how many widgets it
    placed.

    Split out of `build_surface` in PR 1.4c-1 for the screens being converted:
    a legacy `View` builds its own host and places its own widgets — the
    chart, the toolbars, the log — and then wants whatever a module
    contributed *added to that same host*. Building a second one would give
    the user two workbenches, one of them empty.
    """
    surface = host.surface_id
    placed = 0
    for place in _FILL_ORDER:
        if place not in host.accepts():
            continue
        for descriptor in contributions.panels(surface, place):
            host.place_widget(
                place,
                descriptor.factory(container),
                title=descriptor.title,
            )
            placed += 1
    logger.info(
        "Surface %r filled with %d contributed widget(s).",
        surface,
        placed,
    )
    return placed


def build_settings_surface(
    surface_id: str,
    contributions: IContributionTable,
    container: IContainer,
    *,
    parent: object | None = None,
) -> SettingsSurface:
    """Builds the `SETTINGS_SECTION`-only surface named `surface_id`, filled.

    A separate function from `build_surface` rather than one more branch in
    it: `SettingsSurface` is not a `WorkbenchSurface`, and `_FILL_ORDER`'s
    walk only ever asks a `WorkbenchSurface` to place a widget — reusing that
    loop for a host it was never typed against would be a `type: ignore` away
    from `fill_surface`'s own comment about a factory that raises: the
    traceback would name the wrong host.
    """
    host = SettingsSurface(contributions.surface(surface_id), parent)  # type: ignore[arg-type]
    fill_settings_surface(host, surface_id, contributions, container)
    return host


def fill_settings_surface(
    host: SettingsSurface,
    surface_id: str,
    contributions: IContributionTable,
    container: IContainer,
) -> int:
    """Fills a `SettingsSurface` that already exists, and answers how many
    sections it placed.

    Split from `build_settings_surface` the same way `fill_surface` is split
    from `build_surface`: the View builds the (empty) host at `view_factory()`
    time, which takes no `container`, and the Presenter — the one place that
    has one — fills it once constructed.
    """
    placed = 0
    for descriptor in contributions.panels(surface_id, Place.SETTINGS_SECTION):
        host.place_widget(
            Place.SETTINGS_SECTION,
            descriptor.factory(container),
            title=descriptor.title,
        )
        placed += 1
    logger.info(
        "Settings surface %r filled with %d contributed section(s).",
        surface_id,
        placed,
    )
    return placed
