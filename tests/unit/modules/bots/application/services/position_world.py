"""`EPIC-039H` - a simulated venue whose executor runs the position venue's collaborators.

@details The executor is the real one over `grid_world`'s simulated venue; what is substituted is
the table of exposure collaborators (the venue is Spot-priced, which does not matter: the
collaborators read the position from the account snapshot and send market orders the simulated
book records). `Gate`, `Guard` and `Reads` are the venue's settings, the plan-time risk guard and
the facts it is judged with, as a test says them.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_exposures import (
    GridExposure,
    GridExposures,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
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
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.futures_start_checks import (
    FuturesStartChecks,
    FuturesStartReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.venue_profiles_by_market import (
    VenueProfilesByMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_mark_source import (
    IMarkSource,
    MarkReadError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_risk_guard import IRiskGuard
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_settings_gate import (
    IVenueSettingsGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.risk_state import (
    RiskLevel,
    RiskSnapshot,
    RiskState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_settings_gate_result import (
    ENSURED,
    GateRequest,
    GateResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_plan_risk_inputs import (
    PlanRiskInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    OwnerPosition,
    PositionDivergence,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.futures_world import (
    BRACKETS,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    LAST_PRICE,
    GridWorld,
    grid_world,
)

D = Decimal
_AT = datetime(2026, 10, 13, 9, tzinfo=UTC)


class Gate(IVenueSettingsGate):
    """A venue whose settings answer as the test says."""

    def __init__(self, answer: GateResult = ENSURED) -> None:
        self.answer = answer
        self.requests: list[GateRequest] = []

    def ensure(self, request: GateRequest) -> GateResult:
        self.requests.append(request)
        return self.answer

    def verify(self, request: GateRequest) -> GateResult:
        return self.answer


class Guard(IRiskGuard):
    def __init__(self, verdicts: tuple[Verdict, ...] = ()) -> None:
        self.verdicts = verdicts

    def judge_plan(self, inputs: PlanRiskInputs) -> tuple[Verdict, ...]:
        return self.verdicts

    def watch(
        self, snapshot: RiskSnapshot, now: datetime, previous: RiskLevel
    ) -> RiskState:
        return RiskState(RiskLevel.SAFE, "")


class Reads(FuturesStartReads):
    """The facts the plan-time guard reads, as the test says (or why they cannot be)."""

    def __init__(self, context: GridRunContext, unreadable: str | None = None) -> None:
        self._context = context
        self._unreadable = unreadable

    def risk_inputs(self, plan: GridPlan) -> PlanRiskInputs | str:
        if self._unreadable is not None:
            return self._unreadable
        setting = FuturesSymbolSetting("BTCUSDT", 1, MarginType.ISOLATED, D(1_000_000))
        return PlanRiskInputs(
            self._context.params,
            plan,
            setting,
            BRACKETS,
            LAST_PRICE,
            FuturesGridThresholds(),
        )


class Marks(IMarkSource):
    """The mark price a position venue judges its exits on, as the test says (or why it cannot)."""

    def __init__(self, mark: str = "121") -> None:
        self.mark = D(mark)
        self.unreadable: str | None = None
        self.reads = 0

    def read(self) -> Decimal:
        self.reads += 1
        if self.unreadable is not None:
            raise MarkReadError(self.unreadable)
        return self.mark


def a_position_world(
    gate: Gate | None = None,
    guard: Guard | None = None,
    unreadable: str | None = None,
    marks: Marks | None = None,
    state: BotLifecycleState = BotLifecycleState.STARTING,
    config: Mapping[str, str] | None = None,
) -> tuple[GridWorld, Gate]:
    gate = gate or Gate()
    guard = guard or Guard()

    def build(context: GridRunContext) -> GridExposure:
        checks = FuturesStartChecks(context, gate, guard, Reads(context, unreadable))
        return GridExposure(
            PositionOpening(context, checks),
            PositionExposureCloser(context),
            PositionExposureCheck(context),
            PositionOrderFlags(context.params.direction),
            exit_marks=marks,
        )

    exposures = GridExposures(VenueProfilesByMarket(), {ExposureKind.INVENTORY: build})
    world = grid_world(state=state, exposures=exposures, config=config)
    # A position venue's registration always answers a derived position; a bot that has done
    # nothing yet derives none.
    world.session.register_owner_budget_answers(a_registration("0"))
    return world, gate


def a_long_position(quantity: str) -> LivePosition:
    return LivePosition(
        symbol="BTCUSDT",
        position_amt=D(quantity),
        entry_price=LAST_PRICE,
        mark_price=LAST_PRICE,
        unrealized_pnl=D(0),
        leverage=1,
        margin_type=MarginType.ISOLATED,
        liquidation_price=None,
        updated_at=_AT,
    )


def a_registration(held: str, divergence: PositionDivergence | None = None):
    position = OwnerPosition(D(held), LAST_PRICE if D(held) else None, D(0), D(0))
    return OwnerBudgetRegistrationResult(None, position=position, divergence=divergence)


def closer_of(world: GridWorld) -> PositionExposureCloser:
    return PositionExposureCloser(world.executor._context)


def flat_once_sold(
    world: GridWorld, monkeypatch: pytest.MonkeyPatch, held: str
) -> None:
    """The exchange reports `held` until a market order was sent, and flat after."""

    def positions() -> tuple[LivePosition, ...]:
        sold = any(r.order_type is OrderType.MARKET for r in world.book.requests)
        return () if sold else (a_long_position(held),)

    monkeypatch.setattr(world.snapshot, "open_positions", positions)


def exchange_holds_less_after_each_sale(
    world: GridWorld, monkeypatch: pytest.MonkeyPatch, held: str
) -> None:
    """The exchange reports `held`, less what the bot's market orders sold since (a long)."""

    def positions() -> tuple[LivePosition, ...]:
        sold = sum(
            (
                r.quantity
                for r in world.book.requests
                if r.order_type is OrderType.MARKET
            ),
            D(0),
        )
        left = D(held) - sold
        return (a_long_position(str(left)),) if left != 0 else ()

    monkeypatch.setattr(world.snapshot, "open_positions", positions)
