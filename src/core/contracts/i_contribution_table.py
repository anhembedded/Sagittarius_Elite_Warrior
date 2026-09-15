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


class IContributionTable(ABC):
    """What was contributed, in render order."""

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
