"""`bots` as one Engine extension (`EPIC-029`, ADR D1).

This is the only file under `modules/bots/` that `shell/` may import.

**The context's one question:** *which bots exist, what is each one doing, and
are its parameters reasonable?* A bot is a persisted aggregate with a kind
(Grid first) and a declared lifecycle (`domain/bot_lifecycle_fsm_matrix.py`).
How an order reaches the venue stays `trading`'s: a bot will ask for it through
`trading/contracts/` like any other customer (ADR D1), so `trading` remains the
only module that sends orders.

@par `dependencies` is empty, and that is a measurement
ADR D1 expects this module to read `trading`'s and `market_data`'s contracts,
and it will once the executor (`EPIC-029E`) and the bot chart (`EPIC-029G`)
arrive. `EPIC-029B` imports neither. The list grows with the first import,
which `test_module_declarations.py` enforces both ways.

@par `register()` binds the store, the clock and the handlers
`composition/`'s three files. No kind and no executor is bound yet: the only
kind, Grid, needs its executor factory (`EPIC-029E`) to be constructed.

@par `boot()` applies the restart rule (ADR D12)
`BotRestoreService.restore_all()` moves RUNNING and PAUSED bots to RECOVERING
and STARTING bots to HALTED, saving each changed file, and places nothing.

@par No `contribute()` yet
The Bots tab is `EPIC-029F`.
"""

from __future__ import annotations

import logging
from typing import Any

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_restore_service import (
    BotRestoreService,
)
from Sagittarius_Elite_Warrior.src.modules.bots.composition.command_bindings import (
    bind_commands,
)
from Sagittarius_Elite_Warrior.src.modules.bots.composition.query_bindings import (
    bind_queries,
)
from Sagittarius_Elite_Warrior.src.modules.bots.composition.state_bindings import (
    bind_state,
)

logger = logging.getLogger("App.BotsModule")


class BotsModule(BoundedContextModule):
    """Bots: their store, their lifecycle and, from `EPIC-029F`, their tab."""

    module_id = "bots"

    #: Checked by `test_module_declarations.py` against the contracts actually
    #: imported under `modules/bots/`. Empty until the first contract import.
    dependencies: list[str] = []  # noqa: RUF012 — the Engine reads a plain attribute

    def register(self, context: Any) -> None:
        bind_state(context.container)
        bind_commands(context.container)
        bind_queries(context.container)

    def boot(self, context: Any) -> None:
        context.container.resolve(BotRestoreService).restore_all()
        logger.info("Bots restored after start-up")
