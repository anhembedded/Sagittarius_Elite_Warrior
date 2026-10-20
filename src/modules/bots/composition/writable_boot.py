"""What the bots module starts on a copy that may trade (`EPIC-029E`, `EPIC-035A`-`035I`).

A copy that only reads (`bot list`, `bot show`) boots none of this, and imports none of it:
`BotsModule.boot()` reaches `boot_writable` by `Deferred` after its read-only return, so the
router, the watches, the boot recovery and the grid executors behind them (about 0.2 s of
imports) are paid by the run that uses them (`PRO-014`).

The order of the steps is the order `BotsModule.boot()` always had: restore, subscribe the
router, start the price watch, begin the two watches, then recover - after the subscription,
so a fill that arrives while a restored bot reads the exchange finds its executor built.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.i_close_objections import (
    ICloseObjections,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.event_handlers.bot_event_router import (
    BotEventRouter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_boot_recovery import (
    BotBootRecovery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_restore_service import (
    BotRestoreService,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.running_bots_objection import (
    RunningBotsObjection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.loss_cap.account_loss_cap import (
    SAMPLE_EVERY_SECONDS,
    AccountLossCap,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.watches.bot_price_watch import (
    BotPriceWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.watches.sleep_watch import (
    SleepWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.watches.user_stream_status import (
    UserStreamStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.watches.user_stream_watch import (
    UserStreamWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.composition.executor_bindings import (
    build_sleep_watch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_ticker import (
    IBotTicker,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.funding_charged_event import (
    FundingChargedEvent,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.owner_position_diverged_event import (
    OwnerPositionDivergedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
)
from sagittarius_engine.interfaces.i_engine_context import IEngineContext

logger = logging.getLogger("App.BotsModule")


@dataclass(frozen=True, slots=True)
class BotWatches:
    """What a writable boot started, held by the module until it shuts down."""

    router: BotEventRouter
    price_watch: BotPriceWatch
    user_stream_watch: UserStreamWatch
    sleep_watch: SleepWatch
    loss_cap: AccountLossCap


def boot_writable(context: IEngineContext) -> BotWatches:
    """Applies the restart rule, subscribes the bots to what they hear, starts the watches and
    recovers what a restart cut short. `context` is the Engine's, as `BotsModule.boot()` got it."""
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
    bus.on(FundingChargedEvent, router.on_funding)
    bus.on(OwnerPositionDivergedEvent, router.on_position_diverged)
    bus.on(MarketTickEvent, router.on_tick)
    bus.on(TradingSwitchChangedEvent, router.on_switch)
    logger.info(
        "Bots subscribed to fills, ends, rejections, funding, position divergences, "
        "ticks and the switch"
    )
    price_watch = container.resolve(BotPriceWatch)
    bus.on(BotChangedEvent, price_watch.on_bot_changed)
    price_watch.start()
    user_stream_watch = UserStreamWatch(
        container.resolve(BotExecutors),
        container.resolve(IBotClock),
        container.resolve(IBotRetryScheduler),
        status=container.resolve(UserStreamStatus),
    )
    bus.on(UserStreamHealthEvent, user_stream_watch.on_health)
    user_stream_watch.begin()
    logger.info("Bots watch the user-data stream's health")
    sleep_watch = build_sleep_watch(container)
    sleep_watch.begin()
    logger.info("Bots watch for the machine's sleep")
    loss_cap = container.resolve(AccountLossCap)
    container.resolve(IBotTicker).every(SAMPLE_EVERY_SECONDS, loss_cap.sample)
    logger.info("Bots are watched by the account-level loss cap")
    # After the subscription: a fill that arrives while a restored bot
    # reads the exchange finds its executor already built.
    BotBootRecovery(container.resolve(IBotStore), container.resolve(BotExecutors)).run()
    container.resolve(ICloseObjections).register(
        RunningBotsObjection(container.resolve(IBotStore))
    )
    return BotWatches(router, price_watch, user_stream_watch, sleep_watch, loss_cap)
