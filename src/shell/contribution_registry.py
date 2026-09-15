"""The shell's side of the contribution mechanism (HLD §4, SDD-01b, SDD-03).

`IContributionRegistry` is what a module sees: two calls that take a descriptor
and give nothing back. `IContributionTable` is the reading half, which whoever
renders a surface sees. This class is the one object behind both, plus the
validation that makes a mistake fail while the stack still names the module that
made it — the same write-port / read-port split `CliRegistry` has (PR 1.3c-5),
and what let the surface host move to `support/ui_kit` without it importing the
shell (PR 1.4b).

**Order is a sort key, not an identity.** Rendering order is the stable sort by
`(order, contributor_id, factory qualname)`, so two independently written modules
that both pick `order = 10` render in a fixed order rather than refusing to
boot. What may not repeat is `(surface_id, place, contributor_id, factory)`.

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
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface
from Sagittarius_Elite_Warrior.src.shell.surfaces import surface_is_open, surfaces_by_id

logger = logging.getLogger("App.Shell.ContributionRegistry")


class ContributionRegistry(IContributionRegistry, IContributionTable):
    def __init__(
        self, *, dev_mode: bool, surfaces: dict[str, Surface] | None = None
    ) -> None:
        self._surfaces = surfaces_by_id() if surfaces is None else dict(surfaces)
        self._dev_mode = dev_mode
        self._panels: list[ContributionDescriptor] = []
        self._identities: set[tuple[str, Place, str, str]] = set()
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

        identity = descriptor.identity()
        if identity in self._identities:
            raise ContributionError(
                f"{descriptor.contributor_id!r} contributed the same factory to "
                f"{descriptor.surface_id!r}/{descriptor.place.value} twice."
            )
        self._identities.add(identity)
        self._panels.append(descriptor)

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
        matching = [
            descriptor
            for descriptor in self._panels
            if descriptor.surface_id == surface_id and descriptor.place is place
        ]
        return tuple(sorted(matching, key=_render_key))

    # -- what only the shell reads -----------------------------------------

    def screens(self) -> tuple[ScreenContribution, ...]:
        return tuple(self._screens.values())

    def default_route(self) -> str | None:
        return self._default_route

    def dropped_count(self) -> int:
        """How many contributions a gated-off surface swallowed this run."""
        return self._dropped


def _render_key(descriptor: ContributionDescriptor) -> tuple[int, str, str]:
    factory_name = getattr(descriptor.factory, "__qualname__", repr(descriptor.factory))
    return (descriptor.order, descriptor.contributor_id, factory_name)
