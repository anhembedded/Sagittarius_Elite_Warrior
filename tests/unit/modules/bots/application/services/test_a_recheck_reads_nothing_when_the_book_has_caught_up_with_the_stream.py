"""`BUG-216` - the watch's re-read costs nothing when the fill it was waiting for has landed.

@details The account's report outruns the order's on the testnet, so the book differs from the
exchange for the seconds between them and trading reports a divergence. The watch waits five
seconds and re-reads; that re-read registers the budget again (positionRisk twice, the fills'
history, the open orders). By then the fill has landed and the book agrees with the figure the
stream last reported, which trading answers from memory: nothing is read. A book that still
disagrees is read as before, and a divergence the exchange confirms still halts the bot.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_risk_watch import (
    GridRiskWatch,
    RiskWatchParts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.risk_guard_futures import (
    FuturesRiskGuard,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.risk_reads_futures import (
    PositionRechecks,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_risk_reads import (
    IRiskSnapshotSource,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.risk_state import RiskSnapshot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    EMPTY_INVENTORY,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    EMPTY_POSITION,
    PositionDivergence,
    PositionDivergenceKind,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.test_grid_risk_watch import (
    SYMBOL,
    _advance,
)

D = Decimal
S = BotLifecycleState
_T = FuturesGridThresholds()


class _Clock(IBotClock):
    def __init__(self, rig: _Rig) -> None:
        self._rig = rig

    def now(self) -> datetime:
        return self._rig.world.clock.now()


class _Positions(IRiskSnapshotSource):
    """A position far from its liquidation price: the distance is not under test."""

    def __init__(self, clock: IBotClock) -> None:
        self._clock = clock

    def read(self) -> RiskSnapshot:
        return RiskSnapshot(D(1), D(100), D(50), self._clock.now())


class _Rig:
    """A running bot whose watch re-reads through the real `PositionRechecks` over the fake
    trading session; `registrations` counts the budgets it was asked to register again."""

    def __init__(self) -> None:
        self.registrations = 0
        self.world: GridWorld
        self.watch: GridRiskWatch
        #: What a registration after the start finds.
        self.exchange_divergence: PositionDivergence | None = _divergence()

        def build(context: GridRunContext) -> GridRiskWatch:
            self.watch = GridRiskWatch(
                context,
                RiskWatchParts(
                    FuturesRiskGuard(_T),
                    _Positions(_Clock(self)),
                    PositionRechecks(context),
                    _Clock(self),
                    _T,
                ),
            )
            return self.watch

        self.world = grid_world(risk_watch=build)
        self.world.executor.start()
        assert self.world.state() is S.RUNNING
        # Only registrations after the start are counted and answered by the test.
        self.world.session.register_owner_budget_answers_from(self._register)

    def _register(self) -> OwnerBudgetRegistrationResult:
        self.registrations += 1
        return OwnerBudgetRegistrationResult(
            None,
            EMPTY_INVENTORY,
            position=EMPTY_POSITION,
            divergence=self.exchange_divergence,
        )

    def report_and_wait_out_the_delay(self) -> None:
        self.world.executor.facts.on_position_divergence(_divergence())
        _advance(self, _T.position_recheck_delay.total_seconds() + 1)  # type: ignore[arg-type]
        self.world.executor.facts.on_price_age_check()


def _divergence() -> PositionDivergence:
    return PositionDivergence(
        PositionDivergenceKind.POSITION_CHANGED_UNORDERED,
        "bot",
        "tag",
        SYMBOL,
        D("0.5"),
        D(0),
    )


def test_a_book_that_caught_up_with_the_stream_is_not_read_again() -> None:
    rig = _Rig()
    rig.world.session.position_agrees_with_the_stream = True

    rig.report_and_wait_out_the_delay()

    assert rig.registrations == 0, "the fill landed: nothing is left to confirm"
    assert rig.world.state() is S.RUNNING


def test_a_book_that_still_differs_is_read_and_the_exchange_decides() -> None:
    rig = _Rig()
    rig.world.session.position_agrees_with_the_stream = False
    rig.exchange_divergence = None  # the registration finds the figures agree

    rig.report_and_wait_out_the_delay()

    assert rig.registrations == 1
    assert rig.world.state() is S.RUNNING


def test_a_divergence_the_exchange_confirms_still_halts_the_bot() -> None:
    """The in-memory answer can only close a divergence, never open or hide one: with the
    book not agreeing, the registration is read, and a position it still finds foreign halts."""
    rig = _Rig()
    rig.world.session.position_agrees_with_the_stream = False

    rig.report_and_wait_out_the_delay()

    assert rig.registrations == 1
    assert rig.world.state() is S.HALTED
    assert rig.world.runtime().reason is GridReason.FOREIGN_FILL
