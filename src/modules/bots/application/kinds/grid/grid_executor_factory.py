"""`EPIC-029E` — builds the actor that runs one Grid bot (ADR D2, D9).

Everything a running Grid needs is assembled here, once per bot: its venue's
ports, its record (the stored ladder decoded, or a fresh one), its gateway to
trading under its own owner id and tag, its pacer at the budget's spacing, and
its own work queue.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from functools import partial

from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_budget import (
    bot_owner_id,
    grid_budget,
    grid_pacing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_executor import (
    GridExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_exposures import (
    GridExposures,
    spot_only_exposures,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_margin_mode import (
    GRID_MARGIN_MODE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_reference_price import (
    GridReferencePrice,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
    LazyExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_runtime_codec import (
    decode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_price_age import (
    GridPriceAge,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_risk_watch import (
    GridRiskWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_run_state import (
    BotRunState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.halt_recovery_director import (
    HaltRecoveryDirector,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_order_gateway import (
    BotIdentity,
    BotOrderGateway,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_shared_reads import (
    BotSharedReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.shared_mark_reads import (
    SharedMarkReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.shared_position_reads import (
    SharedPositionReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.bot_exchange_terms import (
    exchange_terms_for,
    fresh_exchange_terms_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.venue_settings_gate_spot import (
    SpotSettingsGate,
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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_entry_readiness import (
    IEntryReadiness,
    NoEntryReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_fresh_price_reader import (
    IFreshPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_grid_budgets import (
    IGridBudgets,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
    OrderPacing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_user_stream_status import (
    IUserStreamStatus,
    NoUserStreamStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_settings_gate import (
    IVenueSettingsGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    exposure_limits_of,
    recovery_policy_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_settings_gate_result import (
    GateRequest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_MARKETS,
    GRID_RECOVERY_LAYER,
)
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    BUDGET_QUOTE_ASSET,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
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
    #: The pacer of one venue at one pacing, shared by the venue's bots (`EPIC-029J` J1b).
    pacers: Callable[[TradingVenue, OrderPacing], IOrderPacer]
    #: Where a stop that waits on the exchange schedules its retries; shared by
    #: every bot (`EPIC-035C`).
    retries: IBotRetryScheduler
    #: What a bot's price age is measured on (`EPIC-035A`).
    monotonic: IMonotonicClock
    #: Where a price too old to use is read from (`EPIC-035J`): the one read of a
    #: symbol's price from its venue (`EPIC-035I`), not a second one.
    prices: IFreshPriceReader
    #: Where a bot announces its price leaving its range (`EPIC-035L`).
    events: IEventPublisher
    #: The owner budget a bot registers, chosen by its venue's profile (`EPIC-039H`).
    budgets: IGridBudgets
    #: The venue's settings gate (`EPIC-039E`): a running bot asks it, read-only, whether the
    #: venue still holds its leverage and margin type. Spot's holds nothing to check.
    settings_gate: IVenueSettingsGate = field(default_factory=SpotSettingsGate)
    #: Builds a position venue's liquidation and divergence watch for one bot's context
    #: (`EPIC-039F`); `EPIC-039H` binds it for Futures. `None`: Spot has neither.
    risk_watch: Callable[[GridRunContext], GridRiskWatch | None] | None = None
    #: The exposure-shaped collaborators, chosen by the bot's venue profile (`EPIC-039H`).
    exposures: GridExposures = field(default_factory=spot_only_exposures)
    #: Whether a venue's user-data stream is connected (`EPIC-042C`): what a halt for the stream
    #: recovers on. The default knows no stream is connected, so that halt never recovers.
    user_streams: IUserStreamStatus = field(default_factory=NoUserStreamStatus)
    #: The venue's shared reading of its open positions, which the bots of a venue's idle watches
    #: take instead of one read each (`BOT-184`). `None`: every bot reads for itself.
    positions: SharedPositionReads | None = None
    #: The shared reading of each symbol's mark price, which the exit watch and the risk watch of
    #: a bot take instead of one read each (`BOT-221`). `None`: each reads for itself.
    marks: SharedMarkReads | None = None
    #: What a Grid waiting for its range asks at the price that enters it (`EPIC-044`).
    entry_readiness: IEntryReadiness = field(default_factory=NoEntryReadiness)


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
        params = GridParams.from_config(bot.definition.config)
        gateway = BotOrderGateway(
            ports,
            BotIdentity(bot_owner_id(bot_id), bot_id, symbol),
            deps.pacers(
                bot.definition.venue, grid_pacing(grid_budget(params, deps.caps))
            ),
            BotSharedReads(
                deps.positions.of(bot.definition.venue)
                if deps.positions is not None
                else None,
                deps.marks.of(bot.definition.venue, symbol)
                if deps.marks is not None
                else None,
            ),
        )
        halts = HaltRecoveryDirector(
            recovery_policy_of(GRID_RECOVERY_LAYER, bot.definition.venue)
        )
        context = GridRunContext(
            state=BotRunState(stored.bot, runtime, deps.store, deps.clock, halts),
            gateway=gateway,
            session=ports.trading_session,
            params=params,
            terms_source=LazyExchangeTerms(
                lambda: exchange_terms_for(ports.order_entry_terms, symbol, deps.caps),
                lambda: fresh_exchange_terms_for(
                    ports.order_entry_terms, symbol, deps.caps
                ),
            ),
            caps=deps.caps,
            price_age=GridPriceAge(deps.monotonic),
            reference_price=GridReferencePrice(
                deps.monotonic, lambda: deps.prices.read(bot.definition.venue, symbol)
            ),
            monotonic=deps.monotonic,
            events=deps.events,
            asset_price=lambda asset: deps.prices.read(
                bot.definition.venue, f"{asset}{BUDGET_QUOTE_ASSET}"
            ),
            budget=lambda: deps.budgets.budget_of(bot.definition.venue, symbol, params),
            limits=exposure_limits_of(bot.definition.venue, GRID_MARKETS),
            halts=halts,
            streams=deps.user_streams,
            entry_readiness=deps.entry_readiness,
            settings_check=partial(
                deps.settings_gate.verify,
                GateRequest(
                    bot.definition.venue,
                    symbol,
                    params.leverage,
                    GRID_MARGIN_MODE,
                    bot_owner_id(bot_id),
                ),
            ),
        )
        exposure = deps.exposures.build(context)
        if deps.risk_watch is not None:
            exposure = replace(exposure, risk_watch=deps.risk_watch(context))
        return GridExecutor(
            context, deps.queues(f"bot-{bot_id}"), deps.retries, exposure
        )
