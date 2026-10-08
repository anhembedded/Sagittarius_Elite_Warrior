"""`EPIC-035B` — what the bots module does about the user-data stream's health.

Real `UserStreamWatch` and real executors over the simulated venue, with the
bot clock moved by the test: a stream that comes back catches every bot on the
venue up, a stream that stays down too long halts them and takes their ladders
off, and one that returns afterwards resumes nothing.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.user_stream_watch import (
    DEFAULT_USER_STREAM_LIMITS,
    UserStreamWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_retry_scheduler import (
    FakeBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.gap_world import (
    filled_in_the_gap,
    running,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    VENUE,
    GridWorld,
    grid_world,
)

S = BotLifecycleState
_LIMITS = DEFAULT_USER_STREAM_LIMITS


class _Watched:
    """A running bot behind a `BotExecutors`, and the watch over them."""

    def __init__(self, world: GridWorld | None = None) -> None:
        self.world = world if world is not None else running()
        self.executors = BotExecutors(self.world.factory)
        bot = self.world.store.load(BotId(BOT)).bot
        self.executors.for_bot(bot)
        self.retries = FakeBotRetryScheduler()
        self.watch = UserStreamWatch(self.executors, self.world.clock, self.retries)

    def tell(
        self,
        state: UserStreamState,
        *,
        since_ago: timedelta = timedelta(0),
        venue: TradingVenue = VENUE,
    ) -> None:
        self.watch.on_health(
            UserStreamHealthEvent(
                state=state, since=self.world.clock.now() - since_ago, venue=venue
            )
        )

    def pass_time(self, by: timedelta) -> None:
        self.world.clock.advance(by)
        self.watch.check()

    def missed_a_fill(self) -> None:
        filled_in_the_gap(self.world, Decimal(110), "2.272")
        derived = str(self.world.runtime().inventory + Decimal("2.272"))
        self.world.derive(derived)
        self.world.hold(derived)


def test_the_default_limits_are_the_documented_ones() -> None:
    assert _LIMITS.down_limit == timedelta(seconds=120)
    assert _LIMITS.reconcile_every == timedelta(seconds=300)
    assert _LIMITS.check_every == timedelta(seconds=15)


def test_a_fill_missed_in_the_gap_is_recovered_when_the_stream_reconnects() -> None:
    """The journey: the stream drops, a BUY fills, the stream returns, and the
    SELL that BUY owes is placed (EPIC-035B acceptance, unit tier)."""
    w = _Watched()
    w.tell(UserStreamState.RECONNECTING)
    w.missed_a_fill()
    requests = len(w.world.book.requests)

    w.tell(UserStreamState.CONNECTED)

    assert w.world.state() is S.RUNNING
    assert len(w.world.book.requests) == requests + 1
    assert Decimal(120) in w.world.open_ids_by_price()


def test_a_connected_stream_of_another_venue_catches_no_bot_up() -> None:
    w = _Watched()
    w.missed_a_fill()
    requests = len(w.world.book.requests)

    w.tell(UserStreamState.CONNECTED, venue=TradingVenue.FUTURES_TESTNET)

    assert len(w.world.book.requests) == requests


def test_a_stream_down_past_the_limit_halts_bots_and_parks_the_ladder() -> None:
    w = _Watched()
    w.tell(UserStreamState.RECONNECTING)

    w.pass_time(_LIMITS.down_limit + timedelta(seconds=1))

    assert w.world.state() is S.HALTED
    assert w.world.runtime().reason is GridReason.USER_STREAM_DOWN
    assert w.world.book.open == {}, "the tagged orders were cancelled"


def test_a_stream_down_exactly_the_limit_is_not_yet_halted() -> None:
    """Boundary: 'longer than N seconds'."""
    w = _Watched()
    w.tell(UserStreamState.RECONNECTING)

    w.pass_time(_LIMITS.down_limit)

    assert w.world.state() is S.RUNNING


def test_the_outage_is_measured_from_when_it_began_not_from_the_last_retry() -> None:
    w = _Watched()
    w.tell(UserStreamState.RECONNECTING, since_ago=_LIMITS.down_limit)
    w.tell(UserStreamState.RECONNECTING, since_ago=_LIMITS.down_limit)

    w.pass_time(timedelta(seconds=1))

    assert w.world.state() is S.HALTED


def test_a_stream_that_never_connects_halts_a_running_bot() -> None:
    w = _Watched()
    w.tell(UserStreamState.CONNECTING)

    w.pass_time(_LIMITS.down_limit + timedelta(seconds=1))

    assert w.world.state() is S.HALTED


def test_a_stream_that_returns_does_not_resume_a_halted_bot() -> None:
    w = _Watched()
    w.tell(UserStreamState.RECONNECTING)
    w.pass_time(_LIMITS.down_limit + timedelta(seconds=1))
    assert w.world.state() is S.HALTED
    requests = len(w.world.book.requests)

    w.tell(UserStreamState.CONNECTED)
    w.pass_time(_LIMITS.reconcile_every * 2)

    assert w.world.state() is S.HALTED
    assert len(w.world.book.requests) == requests, "nothing was placed"


def test_an_outage_that_ended_in_time_never_halts() -> None:
    w = _Watched()
    w.tell(UserStreamState.RECONNECTING)
    w.pass_time(timedelta(seconds=100))
    w.tell(UserStreamState.CONNECTED)

    w.pass_time(timedelta(seconds=250))

    assert w.world.state() is S.RUNNING


def test_a_stopped_stream_is_not_an_outage() -> None:
    """A stopped stream is an Emergency Stop or a closed session; the bots were
    halted by that, and no timer should halt them again for a stream nobody
    wants."""
    w = _Watched()
    w.tell(UserStreamState.RECONNECTING)
    w.tell(UserStreamState.STOPPED)

    w.pass_time(_LIMITS.down_limit * 3)

    assert w.world.state() is S.RUNNING


def test_a_down_stream_halts_a_paused_bot_too() -> None:
    world = running()
    world.executor.pause()
    w = _Watched(world)
    w.tell(UserStreamState.RECONNECTING)

    w.pass_time(_LIMITS.down_limit + timedelta(seconds=1))

    assert w.world.state() is S.HALTED


def test_a_bot_that_is_not_running_is_left_alone_by_an_outage() -> None:
    w = _Watched(grid_world(state=S.STOPPED))
    w.tell(UserStreamState.RECONNECTING)

    w.pass_time(_LIMITS.down_limit * 2)

    assert w.world.state() is S.STOPPED


def test_the_periodic_reconcile_runs_when_due_and_not_before() -> None:
    w = _Watched()
    w.tell(UserStreamState.CONNECTED)
    w.missed_a_fill()
    requests = len(w.world.book.requests)

    w.pass_time(_LIMITS.reconcile_every - timedelta(seconds=1))
    assert len(w.world.book.requests) == requests, "not due yet"

    w.pass_time(timedelta(seconds=1))
    assert len(w.world.book.requests) == requests + 1, "due: the counter is placed"


def test_the_periodic_reconcile_repeats_every_interval() -> None:
    w = _Watched()
    w.tell(UserStreamState.CONNECTED)
    w.pass_time(_LIMITS.reconcile_every)
    w.missed_a_fill()
    requests = len(w.world.book.requests)

    w.pass_time(_LIMITS.reconcile_every - timedelta(seconds=1))
    assert len(w.world.book.requests) == requests

    w.pass_time(timedelta(seconds=1))
    assert len(w.world.book.requests) == requests + 1


def test_no_periodic_reconcile_runs_for_a_stream_nobody_reported_connected() -> None:
    w = _Watched()
    w.missed_a_fill()
    requests = len(w.world.book.requests)

    w.pass_time(_LIMITS.reconcile_every * 3)

    assert len(w.world.book.requests) == requests


def test_no_periodic_reconcile_runs_while_the_stream_is_reconnecting() -> None:
    w = _Watched()
    w.tell(UserStreamState.CONNECTED)
    w.tell(UserStreamState.RECONNECTING)
    w.missed_a_fill()
    requests = len(w.world.book.requests)

    w.pass_time(_LIMITS.reconcile_every + timedelta(seconds=1))

    assert len(w.world.book.requests) == requests


def test_the_heartbeat_checks_and_re_arms_itself_until_the_scheduler_closes() -> None:
    w = _Watched()
    w.tell(UserStreamState.RECONNECTING)
    w.world.clock.advance(_LIMITS.down_limit + timedelta(seconds=1))

    w.watch.begin()
    assert [r.delay for r in w.retries.pending] == [_LIMITS.check_every]
    w.retries.run_next()  # one beat: the outage is overdue, so the bot halts

    assert w.world.state() is S.HALTED
    assert [r.delay for r in w.retries.pending] == [_LIMITS.check_every], "re-armed"
    w.retries.close()
    assert w.retries.pending == []


def test_a_beat_that_raises_still_re_arms() -> None:
    w = _Watched()
    w.watch.check = lambda: (_ for _ in ()).throw(RuntimeError("one bad pass"))  # type: ignore[method-assign]
    w.watch.begin()

    with pytest.raises(RuntimeError):
        w.retries.run_next()

    assert len(w.retries.pending) == 1
