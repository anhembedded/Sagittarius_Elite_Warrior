"""`EPIC-039H` — the position venue's parts of a Grid executor, built from the container.

@details `executor_bindings.py` binds the running side; what only a position (Futures) venue
adds is built here so that file stays under the size ratchet and reads as the shared wiring:

  · `futures_exposure` — the four exposure collaborators (`GridExposure`): the opening with its
    start checks (settings gate, plan-time risk guard), the reduce-only close, the position check,
    the reduce-only order flags;
  · `risk_watches` — the liquidation and divergence watch of a position venue's bot, `None` for an
    inventory venue (`GridExecutorDeps.risk_watch`);
  · `grid_budgets` — the owner budget by the venue's exposure kind.

Every thing a position bot reads is read through the venue's ports, per bot, and nothing here sends
an order.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.daily_atr_reader import (
    DailyAtrReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_budgets import (
    FuturesGridBudgets,
    GridBudgetsByProfile,
    SpotGridBudgets,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_exposures import (
    GridExposure,
    GridExposures,
    spot_exposure,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection.protected_closer import (
    ProtectedCloser,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection.protection_futures import (
    ProtectiveStopService,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_risk_watch import (
    GridRiskWatch,
    RiskWatchParts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.order_flags_futures import (
    PositionOrderFlags,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.positions.closer_futures import (
    PositionExposureCloser,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.positions.exposure_check_futures import (
    PositionExposureCheck,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.positions.opening_futures import (
    PositionOpening,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.risk_guard_futures import (
    FuturesRiskGuard,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.risk_reads_futures import (
    PositionRechecks,
    PositionRiskSnapshots,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.shared_position_reads import (
    SharedPositionReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.futures_start_checks import (
    FuturesStartChecks,
    FuturesStartReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.mark_source_futures import (
    ExchangeMarkSource,
    WatchedMarkSource,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.symbol_brackets import (
    SymbolBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.venue_profiles_by_market import (
    VenueProfilesByMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_grid_budgets import (
    IGridBudgets,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_profiles import (
    IVenueProfiles,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_settings_gate import (
    IVenueSettingsGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from sagittarius_engine.interfaces.i_container import IContainer


def grid_budgets(
    profiles: IVenueProfiles, caps: OwnerBudgetCaps, brackets: SymbolBrackets
) -> IGridBudgets:
    return GridBudgetsByProfile(
        profiles,
        {
            ExposureKind.INVENTORY: SpotGridBudgets(caps),
            ExposureKind.POSITION: FuturesGridBudgets(caps, brackets),
        },
    )


def futures_exposure(
    ports: IVenueTradingPorts,
    gate: IVenueSettingsGate,
    brackets: SymbolBrackets,
    thresholds: FuturesGridThresholds,
    sources: Callable[[], IMarketDataSources],
) -> Callable[[GridRunContext], GridExposure]:
    """The builder of a position bot's `GridExposure`."""
    guard = FuturesRiskGuard(thresholds)
    daily_atr = DailyAtrReader(sources)

    def build(context: GridRunContext) -> GridExposure:
        reads = FuturesStartReads(context, ports, brackets, thresholds, daily_atr)
        checks = FuturesStartChecks(context, gate, guard, reads)
        # The protective stop is placed on a mark read now, not on the watches' shared one.
        protection = ProtectiveStopService(context, ExchangeMarkSource(context, ports))
        return GridExposure(
            PositionOpening(context, checks),
            ProtectedCloser(context, PositionExposureCloser(context), protection),
            PositionExposureCheck(context),
            PositionOrderFlags(context.params.direction),
            exit_marks=WatchedMarkSource(context, ports),
            protection=protection,
        )

    return build


def grid_exposures(
    profiles: IVenueProfiles,
    futures: Callable[[GridRunContext], GridExposure],
) -> GridExposures:
    return GridExposures(
        profiles,
        {ExposureKind.INVENTORY: spot_exposure, ExposureKind.POSITION: futures},
    )


def risk_watches(
    ports: IVenueTradingPorts,
    clock: IBotClock,
    thresholds: FuturesGridThresholds,
    positions: SharedPositionReads,
) -> Callable[[GridRunContext], GridRiskWatch | None]:
    """The risk watch of a bot: a position venue's, `None` for an inventory venue's."""
    profiles = VenueProfilesByMarket()
    guard = FuturesRiskGuard(thresholds)

    def build(context: GridRunContext) -> GridRiskWatch | None:
        profile = profiles.for_venue(context.state.bot.definition.venue)
        if profile.exposure_kind is not ExposureKind.POSITION:
            return None
        return GridRiskWatch(
            context,
            RiskWatchParts(
                guard,
                PositionRiskSnapshots(
                    context, positions, WatchedMarkSource(context, ports)
                ),
                PositionRechecks(context),
                clock,
                thresholds,
            ),
        )

    return build


def build_grid_exposures(
    container: IContainer, thresholds: FuturesGridThresholds
) -> GridExposures:
    """The exposure collaborators of each venue profile (`EPIC-039H`)."""
    return grid_exposures(
        container.resolve(IVenueProfiles),
        futures_exposure(
            container.resolve(IVenueTradingPorts),
            container.resolve(IVenueSettingsGate),
            container.resolve(SymbolBrackets),
            thresholds,
            lambda: container.resolve(IMarketDataSources),
        ),
    )
