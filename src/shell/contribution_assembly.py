"""Everything that was contributed to this run, collected once (SDD boot 6–7).

Three kinds of contributor exist during the strangler period and this is the
one place that knows all three: the five legacy screens the shell still carries
(`legacy_screen_adapter.py`), the bounded contexts, which contribute panels,
dialogs and probes through `BoundedContextModule.contribute()`, and the shell's
own Welcome screen (PR 1.5a) — a surface about the *application*, which is what
HLD §4.6 says belongs to the shell rather than to any context.

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
from Sagittarius_Elite_Warrior.src.shell.modules import RegisteredModules
from Sagittarius_Elite_Warrior.src.shell.screen_wiring import contribute_legacy_screens
from Sagittarius_Elite_Warrior.src.shell.welcome.welcome_screen import welcome_screen
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
    contributions.contribute_screen(welcome_screen())
    contribute_legacy_screens(contributions, container)
    for module in container.resolve(RegisteredModules).modules:
        module.contribute(contributions)
    container.singleton(IContributionTable, contributions)
    logger.info(
        "Contributions collected: %d screen(s), %d dropped by a gated surface.",
        len(contributions.screens()),
        contributions.dropped_count(),
    )
    return contributions
