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

PR 0.4a brings the first entry. `market_data` is first because it depends on no
other context — every other one reads prices, and it reads nobody. The rest of
the app is still carried by `binance_bot_module.py` during the strangler period
and joins this list one context per phase.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.module import MarketDataModule

MODULES: tuple[type[BoundedContextModule], ...] = (MarketDataModule,)
