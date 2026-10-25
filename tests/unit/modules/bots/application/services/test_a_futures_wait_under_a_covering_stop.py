"""`BUG-269` - a Futures bot whose protective stop covers its position waits out a dead price feed.

The incident: a Futures bot with a stop standing on the exchange was halted by `price_feed_stale`
and the halt cancelled its ladder and closed the position at market. On a Futures venue that reason
now recovers by itself (the rule of `rate_limited`'s kind: a dwell, three attempts in 24 h) **only
while a stop on the exchange covers the position**; the wait keeps the ladder and the stop, closes
nothing, and ends in the existing path (cancel the ladder, close at market) when the stop stops
covering, the attempts are used up, or the wait outlasts 15 minutes (the owner's limit).
Without a covering stop the halt is the one it always was.
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
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
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.halt_recovery_world import (
    attempts_of,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.position_world import (
    Marks,
    a_long_position,
    a_position_world,
)

S = BotLifecycleState
D = Decimal
_BEAT = 5
_FUTURES = TradingVenue.FUTURES_TESTNET


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


def _world(
    protection: Protection, monkeypatch: pytest.MonkeyPatch
) -> tuple[GridWorld, Marks]:
    """A running Long Futures grid holding what its opening bought, under `protection`; a sale reduces what it holds."""
    marks = Marks("121")
    world, _ = a_position_world(
        marks=marks, venue=_FUTURES, protection=protection, opens_positions=True
    )
    world.executor.start()
    assert world.state() is S.RUNNING
    _the_exchange_holds_what_the_market_orders_net(world, monkeypatch)
    return world, marks


def _the_exchange_holds_what_the_market_orders_net(
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


def _beats(world: GridWorld, seconds: int) -> None:
    for _ in range(0, seconds, _BEAT):
        world.monotonic.advance(_BEAT)
        world.executor.facts.on_price_age_check()


def _closing_orders(world: GridWorld) -> list:
    """The market sales of a Long grid: what a close of its position sends."""
    return [
        r
        for r in world.book.requests
        if r.order_type is OrderType.MARKET and r.side is OrderSide.SELL
    ]


def _the_feed_dies(world: GridWorld, marks: Marks) -> int:
    """No tick and no mark for the limit: the halt of the incident. Returns the ladder's size."""
    ladder = len(world.book.open)
    assert ladder > 0
    marks.unreadable = "no answer"
    _beats(world, int(PRICE_STALE_AFTER_SECONDS) + _BEAT)
    return ladder


def test_a_covered_futures_bot_waits_and_keeps_its_ladder_and_closes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, marks = _world(Protection(StopCoverage.COVERED), monkeypatch)
    markets_before = len(_closing_orders(world))

    ladder = _the_feed_dies(world, marks)

    assert world.state() is S.AWAITING_RECOVERY
    assert world.runtime().reason is GridReason.PRICE_FEED_STALE
    assert len(world.book.open) == ladder, "the ladder rests on the exchange"
    assert len(_closing_orders(world)) == markets_before, "nothing is closed at market"


@pytest.mark.parametrize(
    "coverage",
    [StopCoverage.UNCOVERED, StopCoverage.UNREAD, StopCoverage.NOTHING_EXPOSED],
    ids=lambda c: c.value,
)
def test_without_a_covering_stop_the_halt_still_closes_at_market(
    coverage: StopCoverage, monkeypatch: pytest.MonkeyPatch
) -> None:
    world, marks = _world(Protection(coverage), monkeypatch)
    markets_before = len(_closing_orders(world))

    _the_feed_dies(world, marks)

    assert world.state() is not S.AWAITING_RECOVERY
    assert world.book.open == {}, "the ladder is taken off"
    assert len(_closing_orders(world)) > markets_before, (
        "the position is closed at market"
    )


def test_the_wait_recovers_by_itself_once_the_price_has_stayed_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, marks = _world(Protection(StopCoverage.COVERED), monkeypatch)
    _the_feed_dies(world, marks)
    marks.unreadable = None

    _beats(world, 130)

    assert world.state() is S.RUNNING
    assert attempts_of(world) == 1


def test_a_wait_whose_stop_stops_covering_ends_in_the_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protection = Protection(StopCoverage.COVERED)
    world, marks = _world(protection, monkeypatch)
    markets_before = len(_closing_orders(world))
    _the_feed_dies(world, marks)
    assert world.state() is S.AWAITING_RECOVERY
    protection.coverage = StopCoverage.UNCOVERED

    _beats(world, _BEAT)

    assert world.state() is not S.AWAITING_RECOVERY
    assert world.book.open == {}
    assert len(_closing_orders(world)) > markets_before


def test_a_wait_outlasting_fifteen_minutes_ends_in_the_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, marks = _world(Protection(StopCoverage.COVERED), monkeypatch)
    markets_before = len(_closing_orders(world))
    _the_feed_dies(world, marks)

    _beats(world, 14 * 60)
    assert world.state() is S.AWAITING_RECOVERY
    assert len(_closing_orders(world)) == markets_before

    _beats(world, 2 * 60)

    assert world.state() is not S.AWAITING_RECOVERY
    assert world.book.open == {}
    assert len(_closing_orders(world)) > markets_before
