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
Then `BotEventRouter` is subscribed to the five events a bot hears: fills,
ends and rejections of its orders, its symbol's ticks, and the trading switch.
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
from typing import Any

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_close_objections import (
    ICloseObjections,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_registry import (
    IContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.event_handlers.bot_event_router import (
    BotEventRouter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_boot_recovery import (
    BotBootRecovery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_price_watch import (
    BotPriceWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_restore_service import (
    BotRestoreService,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.running_bots_objection import (
    RunningBotsObjection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.sleep_watch import (
    SleepWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.user_stream_watch import (
    UserStreamWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.composition.command_bindings import (
    bind_commands,
)
from Sagittarius_Elite_Warrior.src.modules.bots.composition.executor_bindings import (
    bind_executors,
    build_sleep_watch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.composition.query_bindings import (
    bind_queries,
)
from Sagittarius_Elite_Warrior.src.modules.bots.composition.state_bindings import (
    bind_state,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
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
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_ended_event import (
    OrderEndedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_rejected_event import (
    OrderRejectedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
)

logger = logging.getLogger("App.BotsModule")


class BotsModule(BoundedContextModule):
    """Bots: their store, their lifecycle and their tab."""

    module_id = "bots"

    #: Checked by `test_module_declarations.py` against the contracts actually
    #: imported under `modules/bots/`: `trading` for the rounding policy the
    #: planner shares with order submission (`EPIC-029C`).
    dependencies: list[str] = ["trading", "market_data"]  # noqa: RUF012 — the Engine reads a plain attribute

    #: The bots' one bus listener, held for the life of the module.
    _router: BotEventRouter | None = None
    #: `EPIC-035B` — the user-stream watch, held for the life of the module.
    _watch: UserStreamWatch | None = None
    #: `EPIC-035I` — the sleep watch, held for the life of the module.
    _sleep: SleepWatch | None = None

    #: Gives each bot that is not at rest its own price stream (`EPIC-035A`),
    #: held for the life of the module like the router.
    _price_watch: BotPriceWatch | None = None

    def register(self, context: Any) -> None:
        bind_state(context.container)
        bind_executors(context.container)
        bind_commands(context.container)
        bind_queries(context.container)

    def boot(self, context: Any) -> None:
        container = context.container
        container.resolve(BotRestoreService).restore_all()
        logger.info("Bots restored after start-up")
        router = BotEventRouter(
            container.resolve(IBotStore), container.resolve(BotExecutors)
        )
        bus = context.event_bus
        bus.on(OrderFilledEvent, router.on_fill)
        bus.on(OrderEndedEvent, router.on_end)
        bus.on(OrderRejectedEvent, router.on_rejected)
        bus.on(MarketTickEvent, router.on_tick)
        bus.on(TradingSwitchChangedEvent, router.on_switch)
        self._router = router
        logger.info("Bots subscribed to fills, ends, rejections, ticks and the switch")
        price_watch = container.resolve(BotPriceWatch)
        bus.on(BotChangedEvent, price_watch.on_bot_changed)
        self._price_watch = price_watch
        price_watch.start()
        watch = UserStreamWatch(
            container.resolve(BotExecutors),
            container.resolve(IBotClock),
            container.resolve(IBotRetryScheduler),
        )
        bus.on(UserStreamHealthEvent, watch.on_health)
        watch.begin()
        self._watch = watch
        logger.info("Bots watch the user-data stream's health")
        sleep = build_sleep_watch(container)
        sleep.begin()
        self._sleep = sleep
        logger.info("Bots watch for the machine's sleep")
        # After the subscription: a fill that arrives while a restored bot
        # reads the exchange finds its executor already built.
        BotBootRecovery(
            container.resolve(IBotStore), container.resolve(BotExecutors)
        ).run()
        container.resolve(ICloseObjections).register(
            RunningBotsObjection(container.resolve(IBotStore))
        )

    def contribute(self, registry: IContributionRegistry) -> None:
        """The Bots tab (`EPIC-029F`, ADR D19), lazy: no widget module is
        imported until the route opens."""
        registry.contribute_screen(bots_screen())
        # `EPIC-033D` — the Bots mode's commands.
        for command in bots_commands(BOTS_ROUTE):
            registry.contribute_command(command)

    def shutdown(self, context: Any) -> None:
        """Close every bot's worker: each runs what is queued, then stops, so
        the app exits with no bot thread left and nothing half-written."""
        # The scheduler first: a retry that fired after a worker closed would
        # be posted to a queue that drops it.
        context.container.resolve(IBotRetryScheduler).close()
        context.container.resolve(BotPriceWatch).close()
        context.container.resolve(BotExecutors).close_all()
        logger.info("Bot price streams released, workers closed")
