"""`EPIC-039F` - a running position bot watches its liquidation distance and its own position.

@details Business promises: a warning is one event per transition and re-arms when the bot is
safe again; a critical distance halts with `LIQUIDATION_RISK`; a position that moved with no
order of the bot's halts with `FOREIGN_FILL` **only if a re-read still shows it**; Spot's
guard is never asked. The world is the Spot executor world with the watch bound by the
factory's seam, as `EPIC-039H` binds it for Futures; the exchange is a hand-set source."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_risk_watch import (
    GridRiskWatch,
    RiskWatchParts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk_guard_futures import (
    FuturesRiskGuard,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk_guard_spot import (
    SpotRiskGuard,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_risk_changed_event import (
    BotRiskChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_risk_reads import (
    IPositionRecheck,
    IRiskSnapshotSource,
    RiskReadError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.risk_state import (
    RiskLevel,
    RiskSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    PositionDivergence,
    PositionDivergenceKind,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    SYMBOL,
    grid_world,
)

S = BotLifecycleState
D = Decimal
_T = FuturesGridThresholds()


class _WorldClock(IBotClock):
    """The world's clock, looked up when asked: the watch is built before the world is."""

    def __init__(self, rig: _Rig) -> None:
        self._rig = rig

    def now(self) -> datetime:
        return self._rig.world.clock.now()


class _Exchange(IRiskSnapshotSource, IPositionRecheck):
    """What the exchange says now: a test sets it."""

    def __init__(self, clock: IBotClock) -> None:
        self._clock = clock
        self.mark = D(100)
        self.liquidation: Decimal | None = D(90)
        self.position = D(1)
        self.unreadable = False
        self.rechecks = 0
        self.still_diverged: PositionDivergence | None = None
        self.read_at: datetime | None = None

    def read(self) -> RiskSnapshot:
        if self.unreadable:
            raise RiskReadError("positionRisk timed out")
        return RiskSnapshot(
            self.position,
            self.mark,
            self.liquidation,
            self.read_at or self._clock.now(),
        )

    def recheck(self, divergence: PositionDivergence) -> PositionDivergence | None:
        self.rechecks += 1
        if self.unreadable:
            raise RiskReadError("positionRisk timed out")
        return self.still_diverged


class _Rig:
    def __init__(self, guard_is_spot: bool = False) -> None:
        self.exchange: _Exchange
        self.watch: GridRiskWatch

        def build(context: GridRunContext) -> GridRiskWatch:
            clock = _WorldClock(self)
            self.exchange = _Exchange(clock)
            self.watch = GridRiskWatch(
                context,
                RiskWatchParts(
                    SpotRiskGuard() if guard_is_spot else FuturesRiskGuard(_T),
                    self.exchange,
                    self.exchange,
                    clock,
                    _T,
                ),
            )
            return self.watch

        self.world = grid_world(risk_watch=build)
        self.world.executor.start()
        assert self.world.state() is S.RUNNING

    def beat(self) -> None:
        self.world.executor.facts.on_price_age_check()

    def events(self) -> list[RiskLevel]:
        return [
            e.level
            for e in self.world.events.events
            if isinstance(e, BotRiskChangedEvent)
        ]


def _divergence(
    kind: PositionDivergenceKind = PositionDivergenceKind.POSITION_CHANGED_UNORDERED,
) -> PositionDivergence:
    return PositionDivergence(kind, "bot", "tag", SYMBOL, D("0.5"), D(0))


def test_a_safe_distance_publishes_nothing() -> None:
    rig = _Rig()

    rig.beat()

    assert rig.events() == []
    assert rig.world.state() is S.RUNNING


def test_a_warn_publishes_once_per_transition_and_rearms_on_safe() -> None:
    rig = _Rig()
    rig.exchange.liquidation = D(96)  # 4 %

    rig.beat()
    rig.beat()
    rig.exchange.liquidation = D(90)  # safe again
    rig.beat()
    rig.exchange.liquidation = D(96)
    rig.beat()

    assert rig.events() == [RiskLevel.WARN, RiskLevel.SAFE, RiskLevel.WARN]
    assert rig.world.state() is S.RUNNING


def test_a_critical_state_halts_with_liquidation_risk_and_says_the_distance() -> None:
    rig = _Rig()
    rig.exchange.liquidation = D("98.5")

    rig.beat()

    assert rig.events() == [RiskLevel.CRITICAL]
    assert rig.world.state() is S.HALTED
    runtime = rig.world.runtime()
    assert runtime.reason is GridReason.LIQUIDATION_RISK
    assert "1.50%" in runtime.reason_detail


def test_an_ageing_snapshot_becomes_unknown_never_safe() -> None:
    rig = _Rig()
    rig.beat()
    rig.exchange.unreadable = True
    rig.world.clock.advance(timedelta(seconds=61))

    rig.beat()

    assert rig.events() == [RiskLevel.UNKNOWN]
    assert rig.world.state() is S.RUNNING


def test_a_failed_read_alone_changes_nothing_while_the_last_reading_is_fresh() -> None:
    rig = _Rig()
    rig.beat()
    rig.exchange.unreadable = True

    rig.beat()

    assert rig.events() == []


def test_a_fill_the_bot_did_not_order_halts_with_foreign_fill_after_a_recheck() -> None:
    rig = _Rig()
    rig.exchange.still_diverged = _divergence()

    rig.world.executor.facts.on_position_divergence(_divergence())
    rig.beat()  # inside the delay: nothing is read yet
    assert rig.exchange.rechecks == 0
    assert rig.world.state() is S.RUNNING
    rig.world.monotonic.advance(5)
    rig.beat()

    assert rig.exchange.rechecks == 1
    assert rig.world.state() is S.HALTED
    assert rig.world.runtime().reason is GridReason.FOREIGN_FILL


def test_a_divergence_the_stream_explained_is_logged_and_the_bot_runs_on() -> None:
    rig = _Rig()
    rig.exchange.still_diverged = None  # the matching fill arrived in between

    rig.world.executor.facts.on_position_divergence(_divergence())
    rig.world.monotonic.advance(5)
    rig.beat()
    rig.beat()

    assert rig.exchange.rechecks == 1
    assert rig.world.state() is S.RUNNING


def test_a_confirmed_position_mismatch_halts_with_position_mismatch() -> None:
    rig = _Rig()
    mismatch = _divergence(PositionDivergenceKind.POSITION_MISMATCH)
    rig.exchange.still_diverged = mismatch

    rig.world.executor.facts.on_position_divergence(mismatch)
    rig.world.monotonic.advance(5)
    rig.beat()

    assert rig.world.runtime().reason is GridReason.POSITION_MISMATCH


def test_a_recheck_that_cannot_read_waits_and_asks_again() -> None:
    rig = _Rig()
    rig.exchange.unreadable = True
    rig.world.executor.facts.on_position_divergence(_divergence())
    rig.world.monotonic.advance(5)

    rig.beat()
    assert rig.world.state() is S.RUNNING
    rig.exchange.unreadable = False
    rig.exchange.still_diverged = _divergence()
    rig.beat()

    assert rig.exchange.rechecks == 2
    assert rig.world.runtime().reason is GridReason.FOREIGN_FILL


def test_spots_guard_never_raises_a_level() -> None:
    rig = _Rig(guard_is_spot=True)
    rig.exchange.liquidation = D("99.9")

    rig.beat()

    assert rig.events() == []
    assert rig.world.state() is S.RUNNING


def test_a_bot_without_a_risk_watch_ignores_a_divergence_and_the_beat() -> None:
    world = grid_world()
    world.executor.start()

    world.executor.facts.on_position_divergence(_divergence())
    world.executor.facts.on_price_age_check()

    assert world.state() is S.RUNNING
