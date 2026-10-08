"""`EPIC-029E` — builds the actor that runs one Grid bot (ADR D2, D9).

Everything a running Grid needs is assembled here, once per bot: its venue's
ports, its record (the stored ladder decoded, or a fresh one), its gateway to
trading under its own owner id and tag, its pacer at the budget's spacing, and
its own work queue.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_exchange_terms import (
    exchange_terms_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_order_gateway import (
    BotIdentity,
    BotOrderGateway,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_run_state import (
    BotRunState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_budget import (
    bot_owner_id,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_executor import (
    GridExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_price_age import (
    GridPriceAge,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_reference_price import (
    GridReferencePrice,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
    LazyExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    decode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    IBotExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_work_queue import (
    IBotWorkQueue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_fresh_price_reader import (
    IFreshPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)


@dataclass(frozen=True, slots=True)
class GridExecutorDeps:
    """What every Grid executor is built from."""

    ports: IVenueTradingPorts
    store: IBotStore
    clock: IBotClock
    caps: OwnerBudgetCaps
    #: A fresh queue for one bot, given its name.
    queues: Callable[[str], IBotWorkQueue]
    #: A fresh pacer at one spacing.
    pacers: Callable[[timedelta], IOrderPacer]
    #: Where a stop that waits on the exchange schedules its retries; shared by
    #: every bot (`EPIC-035C`).
    retries: IBotRetryScheduler
    #: What a bot's price age is measured on (`EPIC-035A`).
    monotonic: IMonotonicClock
    #: Where a price too old to use is read from (`EPIC-035J`): the one read of a
    #: symbol's price from its venue (`EPIC-035I`), not a second one.
    prices: IFreshPriceReader


class GridExecutorFactory(IBotExecutorFactory):
    """Builds `GridExecutor`s."""

    def __init__(self, deps: GridExecutorDeps) -> None:
        self._deps = deps

    def create(self, bot: Bot) -> GridExecutor:
        deps = self._deps
        bot_id = bot.bot_id.value
        symbol = bot.definition.symbol
        ports = deps.ports.get(bot.definition.venue)
        stored = deps.store.load(bot.bot_id)
        runtime = decode_runtime(stored.runtime) if stored.runtime else GridRuntime(())
        gateway = BotOrderGateway(
            ports,
            BotIdentity(bot_owner_id(bot_id), bot_id, symbol),
            deps.pacers(deps.caps.min_order_spacing),
        )
        context = GridRunContext(
            state=BotRunState(stored.bot, runtime, deps.store, deps.clock),
            gateway=gateway,
            session=ports.trading_session,
            params=GridParams.from_config(bot.definition.config),
            terms_source=LazyExchangeTerms(
                lambda: exchange_terms_for(ports.order_entry_terms, symbol, deps.caps)
            ),
            caps=deps.caps,
            price_age=GridPriceAge(deps.monotonic),
            reference_price=GridReferencePrice(
                deps.monotonic, lambda: deps.prices.read(bot.definition.venue, symbol)
            ),
        )
        return GridExecutor(context, deps.queues(f"bot-{bot_id}"), deps.retries)
