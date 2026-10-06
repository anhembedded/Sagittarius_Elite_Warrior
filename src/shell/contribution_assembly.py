"""Everything that was contributed to this run, collected once (SDD boot 6–7).

Every contributor is a bounded context: panels, dialogs, probes, pages of
Tools → Options (`EPIC-033E`) and — since `EPIC-025F` PR 5.2, the last of the
strangler-period screens this function used to hand-carry through
`legacy_screen_adapter.py` (deleted in that pull request) — whole navigable
screens, all through `BoundedContextModule.contribute()`. The shell's own
screens (Welcome, Settings) are gone (`EPIC-033C`, `EPIC-033E`); what is about
the application itself lives in the workbench window and its Options dialog,
and in the Developer mode, which only developer mode has (`EPIC-033P`).

**Why here and not in `create_app()`.** `contribute()` runs *after* `boot()`
(SDD's hook table), and `boot()` is the entry point's call, not the composition
root's — `create_app()` returns before the app is booted. So the composition
root builds the graph and records the module instances (`RegisteredModules`),
and the entry point calls this function once the app is up.

**Why the GUI entry point only.** A headless `sync` has no window to render
into, and `contribute()` would build nothing for it anyway. It is not wasted
work that is avoided so much as a claim that is not made: nothing in a headless
run has a surface, so nothing asks what was contributed to one.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_table import (
    IContributionTable,
)
from Sagittarius_Elite_Warrior.src.shell.contribution_registry import (
    ContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.shell.developer_mode.developer_screen import (
    developer_screen,
)
from Sagittarius_Elite_Warrior.src.shell.modules import RegisteredModules
from sagittarius_engine.interfaces.i_container import IContainer

logger = logging.getLogger("App.Shell.Contributions")


def assemble_contributions(
    container: IContainer, *, dev_mode: bool
) -> ContributionRegistry:
    """Collects every contribution of this run and binds the reading port.

    `IContributionTable` is bound, not `ContributionRegistry`: whoever renders a
    surface may read what was contributed and must not be able to declare
    anything (PR 1.3c-5 made the same split for prompt commands). The concrete
    registry is returned for the caller that still needs its screen half.
    """
    contributions = ContributionRegistry(dev_mode=dev_mode)
    for module in container.resolve(RegisteredModules).modules:
        module.contribute(contributions)
    # The shell's own mode, after every module's (`EPIC-033P`); the registry
    # drops it when developer mode is off.
    contributions.contribute_screen(developer_screen())
    container.singleton(IContributionTable, contributions)
    logger.info(
        "Contributions collected: %d screen(s), %d dropped by a gated surface.",
        len(contributions.screens()),
        contributions.dropped_count(),
    )
    return contributions
