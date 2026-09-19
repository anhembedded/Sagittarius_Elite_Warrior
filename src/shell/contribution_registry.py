"""The shell's side of the contribution mechanism (HLD §4, SDD-01b, SDD-03).

`IContributionRegistry` is what a module sees: two calls that take a descriptor
and give nothing back. `IContributionTable` is the reading half, which whoever
renders a surface sees. This class is the one object behind both, plus the
validation that makes a mistake fail while the stack still names the module that
made it — the same write-port / read-port split `CliRegistry` has (PR 1.3c-5),
and what let the surface host move to `support/ui_kit` without it importing the
shell (PR 1.4b).

**The panel half is rebuilt on the Engine's own registry (`EPIC-025F` PR 5.3,
`TASK-043` E1).** Identity/duplicate checking, storage and render ordering
(`(order, contributor_id, factory qualname)`) used to be a hand-rolled copy of
logic the Engine has since harvested and published as
`sagittarius_engine.extensions.pyside_mvc.runtime.ContributionRegistry` — this
class now delegates to one internally rather than keeping a second copy of the
same correctness code. What stays here, and could not move, is this app's own
**policy**: which surfaces exist and what each `gated_by` key means
(`shell/surfaces.py`), and the unknown-surface/place-not-accepted error
messages, both of which need this app's own richer `Surface` (`owner`,
`gated_by`) that the Engine's deliberately narrower `SurfaceDeclaration` does
not carry (that file's own docstring names this as the intended split: app
policy stays app-side, a one-line adapter crosses the boundary). `Place` and
`SizeHint` stay this app's own closed vocabularies too — `_to_engine_descriptor`/
`_from_engine_descriptor` are that one-line adapter, translating at the
boundary rather than widening either side's contract.

**Screens are untouched.** `contribute_screen()`/`screens()`/`default_route()`
have no Engine equivalent yet — routing is `NavigationService`'s concern
(`EPIC-025F` PR 5.1's in-app prototype), a separate mechanism from panel
placement.

**A gated-off surface drops its contributions.** `dev_board` when developer mode
is off is the normal user run, not an error: every panel and probe aimed at it is
dropped with one log line each, and the app boots.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.contribution_descriptor import (
    ContributionDescriptor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.errors import ContributionError
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_registry import (
    IContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_table import (
    IContributionTable,
)
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)
from Sagittarius_Elite_Warrior.src.core.contracts.size_hint import SizeHint
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface
from Sagittarius_Elite_Warrior.src.shell.surfaces import surface_is_open, surfaces_by_id
from sagittarius_engine.extensions.pyside_mvc.runtime.contribution_descriptor import (
    ContributionDescriptor as EngineContributionDescriptor,
)
from sagittarius_engine.extensions.pyside_mvc.runtime.contribution_error import (
    ContributionError as EngineContributionError,
)
from sagittarius_engine.extensions.pyside_mvc.runtime.contribution_registry import (
    ContributionRegistry as EngineContributionRegistry,
)
from sagittarius_engine.extensions.pyside_mvc.runtime.size_hint import (
    SizeHint as EngineSizeHint,
)
from sagittarius_engine.extensions.pyside_mvc.runtime.surface_declaration import (
    SurfaceDeclaration,
)

logger = logging.getLogger("App.Shell.ContributionRegistry")

#: This app's three buckets, mapped onto the Engine's own copy of them
#: (`TASK-043` E1 harvested `SizeHint` unchanged, but as its own class — the
#: runtime does not import this app's types). An explicit, exhaustive dict
#: rather than a by-name lookup: a member added to one side without the other
#: fails here, at import time, not with a `KeyError` mid-render.
_TO_ENGINE_SIZE_HINT: dict[SizeHint, EngineSizeHint] = {
    SizeHint.COMPACT: EngineSizeHint.COMPACT,
    SizeHint.REGULAR: EngineSizeHint.REGULAR,
    SizeHint.TALL: EngineSizeHint.TALL,
}
_FROM_ENGINE_SIZE_HINT: dict[EngineSizeHint, SizeHint] = {
    engine: app for app, engine in _TO_ENGINE_SIZE_HINT.items()
}


def _to_engine_descriptor(
    descriptor: ContributionDescriptor,
) -> EngineContributionDescriptor:
    return EngineContributionDescriptor(
        contributor_id=descriptor.contributor_id,
        surface_id=descriptor.surface_id,
        place=descriptor.place.value,
        order=descriptor.order,
        size_hint=_TO_ENGINE_SIZE_HINT[descriptor.size_hint],
        factory=descriptor.factory,
        title=descriptor.title,
    )


def _from_engine_descriptor(
    descriptor: EngineContributionDescriptor,
) -> ContributionDescriptor:
    return ContributionDescriptor(
        contributor_id=descriptor.contributor_id,
        surface_id=descriptor.surface_id,
        place=Place(descriptor.place),
        order=descriptor.order,
        size_hint=_FROM_ENGINE_SIZE_HINT[descriptor.size_hint],
        factory=descriptor.factory,
        title=descriptor.title,
    )


class ContributionRegistry(IContributionRegistry, IContributionTable):
    def __init__(
        self, *, dev_mode: bool, surfaces: dict[str, Surface] | None = None
    ) -> None:
        self._surfaces = surfaces_by_id() if surfaces is None else dict(surfaces)
        self._dev_mode = dev_mode
        self._engine_registry = EngineContributionRegistry(
            surfaces=(
                SurfaceDeclaration(
                    surface_id=surface.surface_id,
                    accepts=frozenset(place.value for place in surface.accepts),
                )
                for surface in self._surfaces.values()
            )
        )
        self._screens: dict[str, ScreenContribution] = {}
        self._default_route: str | None = None
        self._dropped = 0

    # -- the module-facing side (IContributionRegistry) --------------------

    def contribute(self, descriptor: ContributionDescriptor) -> None:
        surface = self._surfaces.get(descriptor.surface_id)
        if surface is None:
            raise ContributionError(
                f"{descriptor.contributor_id!r} contributed a {descriptor.place.value} to "
                f"the unknown surface {descriptor.surface_id!r}. Known surfaces: "
                f"{sorted(self._surfaces)}."
            )
        if descriptor.place not in surface.accepts:
            raise ContributionError(
                f"surface {surface.surface_id!r} does not accept "
                f"{descriptor.place.value} (asked for by {descriptor.contributor_id!r}); "
                f"it accepts {sorted(place.value for place in surface.accepts)}."
            )
        if not surface_is_open(surface, dev_mode=self._dev_mode):
            self._dropped += 1
            logger.info(
                "Dropped %s from %r: surface %r is gated off for this run (%s).",
                descriptor.place.value,
                descriptor.contributor_id,
                surface.surface_id,
                surface.gated_by,
            )
            return

        try:
            self._engine_registry.contribute(_to_engine_descriptor(descriptor))
        except EngineContributionError as exc:
            raise ContributionError(str(exc)) from exc

    def contribute_screen(self, contribution: ScreenContribution) -> None:
        if contribution.route in self._screens:
            claimed_by = self._screens[contribution.route].contributor_id
            raise ContributionError(
                f"route {contribution.route!r} is contributed twice: by "
                f"{claimed_by!r} and by {contribution.contributor_id!r}."
            )
        if contribution.is_default and self._default_route is not None:
            raise ContributionError(
                f"two default screens: {self._default_route!r} and "
                f"{contribution.route!r} (from {contribution.contributor_id!r})."
            )
        if contribution.is_default:
            self._default_route = contribution.route
        self._screens[contribution.route] = contribution

    # -- the reading side (IContributionTable) -----------------------------

    def surface(self, surface_id: str) -> Surface:
        """The surface declaration behind an id (PR 1.4c-1).

        The registry validates every contribution against this same table, so
        it is the one object that already knows both halves a renderer needs.
        """
        surface = self._surfaces.get(surface_id)
        if surface is None:
            raise ContributionError(
                f"no surface is declared with the id {surface_id!r}. Known "
                f"surfaces: {sorted(self._surfaces)}."
            )
        return surface

    def panels(
        self, surface_id: str, place: Place
    ) -> tuple[ContributionDescriptor, ...]:
        """Everything contributed to one place, in render order."""
        return tuple(
            _from_engine_descriptor(descriptor)
            for descriptor in self._engine_registry.panels(surface_id, place.value)
        )

    # -- what only the shell reads -----------------------------------------

    def screens(self) -> tuple[ScreenContribution, ...]:
        return tuple(self._screens.values())

    def default_route(self) -> str | None:
        return self._default_route

    def dropped_count(self) -> int:
        """How many contributions a gated-off surface swallowed this run."""
        return self._dropped
