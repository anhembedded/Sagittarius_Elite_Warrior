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

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.closer_futures import (
    PositionExposureCloser,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.exposure_check_futures import (
    PositionExposureCheck,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.futures_start_checks import (
    FuturesStartChecks,
    FuturesStartReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_budgets import (
    FuturesGridBudgets,
    GridBudgetsByProfile,
    SpotGridBudgets,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_exposures import (
    GridExposure,
    GridExposures,
    spot_exposure,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_risk_watch import (
    GridRiskWatch,
    RiskWatchParts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.mark_source_futures import (
    ExchangeMarkSource,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.opening_futures import (
    PositionOpening,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.order_flags_futures import (
    PositionOrderFlags,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk_guard_futures import (
    FuturesRiskGuard,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk_reads_futures import (
    PositionRechecks,
    PositionRiskSnapshots,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.symbol_brackets import (
    SymbolBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue_profiles_by_market import (
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)


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
) -> Callable[[GridRunContext], GridExposure]:
    """The builder of a position bot's `GridExposure`."""
    guard = FuturesRiskGuard(thresholds)

    def build(context: GridRunContext) -> GridExposure:
        reads = FuturesStartReads(context, ports, brackets, thresholds)
        checks = FuturesStartChecks(context, gate, guard, reads)
        return GridExposure(
            PositionOpening(context, checks),
            PositionExposureCloser(context),
            PositionExposureCheck(context),
            PositionOrderFlags(context.params.direction),
            exit_marks=ExchangeMarkSource(context, ports),
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
    ports: IVenueTradingPorts, clock: IBotClock, thresholds: FuturesGridThresholds
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
                    context, ports, ExchangeMarkSource(context, ports)
                ),
                PositionRechecks(context),
                clock,
                thresholds,
            ),
        )

    return build
