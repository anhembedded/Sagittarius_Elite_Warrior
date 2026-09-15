"""Reading what was contributed, for whoever renders it (HLD §4, SDD-01b).

`IContributionRegistry` next door is the **writing** half: two calls a module
makes, both returning nothing. This is the reading half, and it exists for the
same reason `ICliCommandTable` does (`EPIC-025` PR 1.3c-5): the collector and
the consumer are two different jobs, and the consumer must not be able to
declare.

It is what let the surface host and its builder move out of `shell/` into
`support/ui_kit` (PR 1.4b): building a surface needs *what was contributed to
this place*, not the shell's concrete registry — and `support/*` cannot import
`shell/` at all. A legacy screen and a module's `ui/` may both import
`support/ui_kit`, which is what makes one host serve both during the strangler
period.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.core.contracts.contribution_descriptor import (
    ContributionDescriptor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface


class IContributionTable(ABC):
    """What was contributed, and to which surface, for whoever renders it."""

    @abstractmethod
    def surface(self, surface_id: str) -> Surface:
        """The surface declaration to render, by id.

        Here rather than on a registry of its own: whoever renders a surface
        needs *what this surface accepts* and *what was contributed to it*
        together, and the object that validated the contributions already
        holds both. A caller that only has an id — a legacy screen being
        converted, which may not import `shell/` — can then render without
        naming the application's surface list.

        Raises `ContributionError` for an id no surface declares, rather than
        answering `None`: a screen asking for a surface that does not exist is
        a wiring mistake, and a missing workbench is a worse way to find out.
        """

    @abstractmethod
    def panels(
        self, surface_id: str, place: Place
    ) -> tuple[ContributionDescriptor, ...]:
        """Everything contributed to one place of one surface.

        Sorted, and the sort is the contract: `(order, contributor_id, factory
        qualname)`, so two modules that both pick `order = 10` render in a
        fixed order rather than refusing to boot. `order` decides only the
        initial arrangement — after that the user's saved perspective wins
        (HLD §11.2).
        """
