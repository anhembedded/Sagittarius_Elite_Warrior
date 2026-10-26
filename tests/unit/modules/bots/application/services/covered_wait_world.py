"""`BUG-270` - the shared world of the covered-wait tests: a running Long Futures grid whose stop coverage a test sets.

The executor, the guard and the recovery run are the real ones over `a_position_world`'s simulated
venue; what is substituted is the answer of `IExposureProtection.read_coverage` (`Protection`) and the
exchange's position (the bot's market buys less its sales). `the_feed_dies` is the incident: no tick
and no readable mark for the limit.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_stop_coverage import (
    StopCoverage,
    StopCoverageReading,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_protection import (
    IExposureProtection,
    ProtectionVerdict,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_user_stream_status import (
    IUserStreamStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.price_freshness import (
    PRICE_STALE_AFTER_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.request_priority import (
    RequestPriority,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.position_world import (
    Marks,
    a_long_position,
    a_position_world,
)

S = BotLifecycleState
D = Decimal
BEAT = 5
#: The wait reads the stop's coverage once in this many seconds (`COVERAGE_READ_EVERYBEATS` beats).
COVERAGE_READ_EVERY = 15
FUTURES = TradingVenue.FUTURES_TESTNET


class Protection(IExposureProtection):
    """The stop on the exchange as the test says it: what a fresh read of its coverage answers."""

    def __init__(self, coverage: StopCoverage = StopCoverage.COVERED) -> None:
        self.coverage = coverage
        self.reads = 0

    def protect(self, plan: GridPlan) -> bool:
        return True

    def supervise(self) -> ProtectionVerdict:
        return ProtectionVerdict.OK

    def describe_stop(self) -> str:
        return "its protective stop stands on the exchange"

    def read_coverage(self) -> StopCoverageReading:
        self.reads += 1
        return StopCoverageReading(self.coverage, f"the stop is {self.coverage.value}")

    def release(self) -> bool:
        return True


def a_covered_world(
    protection: Protection,
    monkeypatch: pytest.MonkeyPatch,
    user_streams: IUserStreamStatus | None = None,
) -> tuple[GridWorld, Marks]:
    """A running Long Futures grid holding what its opening bought, under `protection`; a sale reduces what it holds."""
    marks = Marks("121")
    world, _ = a_position_world(
        marks=marks,
        venue=FUTURES,
        protection=protection,
        opens_positions=True,
        user_streams=user_streams,
    )
    world.executor.start()
    assert world.state() is S.RUNNING
    the_exchange_holds_what_the_market_orders_net(world, monkeypatch)
    return world, marks


def the_exchange_holds_what_the_market_orders_net(
    world: GridWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exchange's position: the bot's market buys less its market sales (a long)."""

    def positions(
        priority: RequestPriority = RequestPriority.ROUTINE,
    ) -> tuple[LivePosition, ...]:
        net = sum(
            (
                r.quantity if r.side is OrderSide.BUY else -r.quantity
                for r in world.book.requests
                if r.order_type is OrderType.MARKET
            ),
            D(0),
        )
        return (a_long_position(str(net)),) if net != 0 else ()

    monkeypatch.setattr(world.snapshot, "open_positions", positions)


def beats(world: GridWorld, seconds: int) -> None:
    for _ in range(0, seconds, BEAT):
        world.monotonic.advance(BEAT)
        world.executor.facts.on_price_age_check()


def closing_orders(world: GridWorld) -> list:
    """The market sales of a Long grid: what a close of its position sends."""
    return [
        r
        for r in world.book.requests
        if r.order_type is OrderType.MARKET and r.side is OrderSide.SELL
    ]


def the_feed_dies(world: GridWorld, marks: Marks) -> int:
    """No tick and no mark for the limit: the halt of the incident. Returns the ladder's size."""
    ladder = len(world.book.open)
    assert ladder > 0
    marks.unreadable = "no answer"
    beats(world, int(PRICE_STALE_AFTER_SECONDS) + BEAT)
    return ladder
