"""`bots` as one Engine extension (`EPIC-029`, ADR D1).

This is the only file under `modules/bots/` that `shell/` may import.

**The context's one question:** *which bots exist, what is each one doing, and
are its parameters reasonable?* A bot is a persisted aggregate with a kind
(Grid first) and a declared lifecycle (`domain/bot_lifecycle_fsm_matrix.py`).
How an order reaches the venue stays `trading`'s: a bot will ask for it through
`trading/contracts/` like any other customer (ADR D1), so `trading` remains the
only module that sends orders.

@par `dependencies` are `trading` and `market_data`, and that is a measurement
ADR D1 expects this module to read both contexts' contracts. `EPIC-029C`
brought the first: the Grid planner rounds prices and quantities with
trading's own `OrderQuantityRoundingPolicy`, so a level is rounded by the same
rule trading will hold its order to, not by a copy. `market_data` joined with
the bot chart (`EPIC-029G`): its candle feed and its `MarketTickEvent`.
`test_module_declarations.py` enforces the list both ways.

@par `register()` binds the store, the clock, the executors and the handlers
`composition/`'s four files. `EPIC-029E` adds the executors: one actor per
running bot (`BotExecutors`), the runner the use cases hand commands to, and
the lock that makes the D20 check and a start one step.

@par `boot()` applies the restart rule (ADR D12), then subscribes the bots
`BotRestoreService.restore_all()` moves RUNNING and PAUSED bots to RECOVERING
and STARTING bots to HALTED, saving each changed file, and places nothing.
Then `BotEventRouter` is subscribed to the seven events a bot hears: fills,
ends and rejections of its orders, its symbol's funding fees, a divergence of its position
from the exchange's (`EPIC-039F`), its symbol's ticks, and the trading switch.
It is held for the life of the module (the reason `StrategyModule` gives for
its tick handler), and it only copies and queues: the bots' own workers act.

@par `boot()` also starts the price watch (`EPIC-035A`)
`BotPriceWatch` gives every bot that is not DRAFT or STOPPED its own price stream
through market_data's `IMarketStream`, so stop loss and take profit are watched
with no chart open, and halts a bot whose feed goes quiet. It follows the bots'
own `BotChangedEvent`, and `shutdown()` releases every stream it opened.

@par `boot()` also watches the user-data stream (`EPIC-035B`)
`UserStreamWatch` hears trading's `UserStreamHealthEvent`: a reconnect catches
every bot on the venue up, a stream down too long halts them. A daemon thread
re-arms its `check()` on the retry scheduler, which `shutdown()` closes.

@par `boot()` also watches for sleep (`EPIC-035I`)
`SleepWatch` looks at the monotonic and wall clocks on the same retry scheduler's
heartbeat. A gap longer than a minute is a suspended machine: every bot is
reconciled through the entry point the user-stream watch uses, and its stop loss
and take profit meet a price read fresh from the venue.

@par A second copy of the app boots none of this (`EPIC-035H`)
When another copy holds the data root (`IInstanceAccess.read_only`), `boot()`
returns before the restart rule, the router and every watch: the first copy's
bots stay as it left them. The store and the runner are read-only wrappers.

@par `contribute()` offers the Bots tab (`EPIC-029F`, ADR D19)
The route `bots`, NAVIGATION item 18, built lazily from `ui/bots_screen/`.

@par `boot()` then reads what a restart left (`EPIC-035C`, H6)
`BotBootRecovery` has every RECOVERING bot report what the exchange holds
(read-only) and every bot whose start the restart cut short cancel its tagged
orders, each on the bot's own worker. The order session is closed at boot, so
the cancel usually waits for the switch-on, which repeats it until it is paid.

@par `boot()` also registers the close objection (ADR O4)
`RunningBotsObjection` names every bot not at rest when the user closes the
window, so closing with a ladder on the exchange is a choice, not an accident.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.core.contracts.deferred import Deferred
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_registry import (
    CliCommandDescriptor,
    ICliRegistry,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_registry import (
    IContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    HealthContributorDescriptor,
    IOperationsRegistry,
    PreflightCheckDescriptor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_files_readable_check import (
    CHECK_ID as BOT_FILES_CHECK_ID,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_files_readable_check import (
    BotFilesReadableCheck,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bots_health_contributor import (
    SECTION_NAME,
    BotsHealthContributor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.watches.bot_price_watch import (
    BotPriceWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_cli_handler import (
    BotCliHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.composition.command_bindings import (
    bind_commands,
)
from Sagittarius_Elite_Warrior.src.modules.bots.composition.executor_bindings import (
    bind_executors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.composition.query_bindings import (
    bind_queries,
)
from Sagittarius_Elite_Warrior.src.modules.bots.composition.state_bindings import (
    bind_state,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    bots_commands,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
    bots_screen,
)

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.modules.bots.composition.writable_boot import (
        BotWatches,
    )

logger = logging.getLogger("App.BotsModule")

#: The boot of a copy that may trade, imported when one boots (`PRO-014`): the read-only copies
#: `bot list` and `bot show` start none of it and should not pay its ~0.2 s of imports.
_WRITABLE_BOOT: Deferred[BotWatches] = Deferred(
    "Sagittarius_Elite_Warrior.src.modules.bots.composition.writable_boot:boot_writable"
)


class BotsModule(BoundedContextModule):
    """Bots: their store, their lifecycle and their tab."""

    module_id = "bots"

    #: Checked by `test_module_declarations.py` against the contracts actually
    #: imported under `modules/bots/`: `trading` for the rounding policy the
    #: planner shares with order submission (`EPIC-029C`).
    dependencies: list[str] = ["trading", "market_data"]  # noqa: RUF012 — the Engine reads a plain attribute

    #: What a writable boot started, held for the life of the module: the router (the bots' one
    #: bus listener), the price stream per bot (`EPIC-035A`), the user-stream watch
    #: (`EPIC-035B`) and the sleep watch (`EPIC-035I`). `None` on a copy that only reads.
    _watches: BotWatches | None = None

    def register(self, context: Any) -> None:
        bind_state(context.container)
        bind_executors(context.container)
        bind_commands(context.container)
        bind_queries(context.container)

    def boot(self, context: Any) -> None:
        container = context.container
        instance = container.resolve(IInstanceAccess)
        if instance.read_only:
            # `EPIC-035H`: the restart rule would rewrite the first copy's running
            # bots, and a watch would answer their fills. This copy reads only.
            logger.info("Bots are read-only on this copy: %s", instance.reason)
            return
        self._watches = _WRITABLE_BOOT(context)

    def contribute(self, registry: IContributionRegistry) -> None:
        """The Bots tab (`EPIC-029F`, ADR D19), lazy: no widget module is
        imported until the route opens."""
        registry.contribute_screen(bots_screen())
        # `EPIC-033D` — the Bots mode's commands.
        for command in bots_commands(BOTS_ROUTE):
            registry.contribute_command(command)

    def declare_cli(self, registry: ICliRegistry) -> None:
        """`bot list` and `bot show` (`EPIC-038C`): the command line's view of
        the bots, read through the queries the Bots tab reads through."""
        registry.declare(
            CliCommandDescriptor(
                name="bot", handler=BotCliHandler, contributor_id=self.module_id
            )
        )

    def declare_operations(self, registry: IOperationsRegistry) -> None:
        """The bots' section of the health snapshot (`EPIC-038C`) and the pre-flight check
        that every bot file can be read by this build (`EPIC-038H`)."""
        registry.declare_preflight(
            PreflightCheckDescriptor(
                BOT_FILES_CHECK_ID,
                lambda resolver: BotFilesReadableCheck(
                    resolver.resolve(IBotStore)  # type: ignore[type-abstract]
                ),
                self.module_id,
            )
        )
        registry.declare_health(
            HealthContributorDescriptor(
                SECTION_NAME,
                lambda resolver: BotsHealthContributor(
                    resolver.resolve(ICommandDispatcher)  # type: ignore[type-abstract]
                ),
                self.module_id,
            )
        )

    def shutdown(self, context: Any) -> None:
        """Close every bot's worker: each runs what is queued, then stops, so
        the app exits with no bot thread left and nothing half-written."""
        # The scheduler first: a retry that fired after a worker closed would
        # be posted to a queue that drops it.
        context.container.resolve(IBotRetryScheduler).close()
        context.container.resolve(BotPriceWatch).close()
        context.container.resolve(BotExecutors).close_all()
        logger.info("Bot price streams released, workers closed")
