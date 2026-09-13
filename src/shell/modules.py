"""The module list — Martin's "Main" component (HLD §3.1, SDD boot step 3).

This tuple is the **source of truth** for which bounded contexts exist and in
what order they are registered. The Engine can sort extensions by their declared
`dependencies`, and it will; this list is still the mechanism, because
`contribute()` runs in list order and that order is observable (a rail's panels
appear in it). A sort that is only implied by metadata is a behaviour nobody can
read.

`test_module_declarations.py` checks it both ways: every package under
`src/modules/` appears here, and every entry here exists on disk. A module that
exists but is not listed is dead code that looks alive; a listed module that
does not exist is a boot crash waiting for the next run.

Phase 0 PR 0.2 ships the mechanism with an empty list — `market_data` is the
first entry and arrives in PR 0.4. The list is empty rather than absent so the
two-way guard is live before the first module, not after it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)

MODULES: tuple[type[BoundedContextModule], ...] = ()
