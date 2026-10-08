"""`EPIC-035I` — a machine that slept is caught up like a stream that dropped.

Real `SleepWatch` and real executors over the simulated venue, both clocks moved
by the test. After a gap the watch asks every bot for the same reconcile
`EPIC-035B` runs after a stream gap, and checks the stop loss and take profit
against a price read fresh from the venue, never the last tick the sleep froze.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.sleep_watch import (
    DEFAULT_SLEEP_LIMITS,
    SleepLimits,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.gap_world import (
    filled_in_the_gap,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    SYMBOL,
    VENUE,
    grid_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.sleep_world import (
    ScriptedFreshPrice,
    Sleeper,
)

S = BotLifecycleState
_LIMITS = DEFAULT_SLEEP_LIMITS
_INSIDE_THE_BAND = Decimal(121)
_BELOW_STOP_LOSS = Decimal(89)
_ABOVE_TAKE_PROFIT = Decimal(151)
_NIGHT = timedelta(hours=8)


def test_the_default_limits_are_the_documented_ones() -> None:
    assert _LIMITS.check_every == timedelta(seconds=15)
    assert _LIMITS.gap_over == timedelta(seconds=60)
    assert _LIMITS.price_attempts == 4
    assert _LIMITS.price_retry_every == timedelta(seconds=15)


def test_a_clock_gap_triggers_a_reconcile_and_an_exit_check() -> None:
    """The journey (EPIC-035I acceptance): a BUY filled and the price fell
    through the stop loss while the machine slept."""
    s = Sleeper(ScriptedFreshPrice(_BELOW_STOP_LOSS))
    filled_in_the_gap(s.world, Decimal(110), "2.272")
    s.world.derive(str(s.world.runtime().inventory + Decimal("2.272")))
    s.world.hold(str(s.world.runtime().inventory + Decimal("2.272")))

    s.sleep(_NIGHT)

    assert s.world.state() is S.STOPPED
    assert s.world.runtime().reason is GridReason.STOP_LOSS
    assert s.world.book.open == {}, "the ladder was taken off"
    assert s.prices.reads == [(VENUE, SYMBOL)], "one fresh read for the symbol"


def test_a_gap_reconciles_a_fill_missed_in_sleep_before_the_price_is_checked() -> None:
    s = Sleeper(ScriptedFreshPrice(_INSIDE_THE_BAND))
    filled_in_the_gap(s.world, Decimal(110), "2.272")
    derived = str(s.world.runtime().inventory + Decimal("2.272"))
    s.world.derive(derived)
    s.world.hold(derived)
    requests = len(s.world.book.requests)

    s.sleep(_NIGHT)

    assert s.world.state() is S.RUNNING
    assert len(s.world.book.requests) == requests + 1, "the counter SELL was placed"
    assert Decimal(120) in s.world.open_ids_by_price()


def test_a_take_profit_crossed_in_sleep_is_taken_on_wake() -> None:
    s = Sleeper(ScriptedFreshPrice(_ABOVE_TAKE_PROFIT))

    s.sleep(_NIGHT)

    assert s.world.state() is S.STOPPED
    assert s.world.runtime().reason is GridReason.TAKE_PROFIT


def test_the_exit_check_reads_the_price_afresh_not_the_last_tick() -> None:
    """The last tick the bot heard before sleeping was inside the band; the
    stop loss is only crossed in the fresh read."""
    s = Sleeper(ScriptedFreshPrice(_BELOW_STOP_LOSS))
    s.world.executor.on_tick(_INSIDE_THE_BAND)

    s.sleep(_NIGHT)

    assert s.world.runtime().reason is GridReason.STOP_LOSS


def test_the_heartbeat_looks_every_interval_until_the_scheduler_closes() -> None:
    s = Sleeper(ScriptedFreshPrice(_INSIDE_THE_BAND))

    s.watch.begin()
    assert [r.delay for r in s.world.retries.pending] == [_LIMITS.check_every]
    s.world.retries.run_next()

    assert [r.delay for r in s.world.retries.pending] == [_LIMITS.check_every]
    s.world.retries.close()
    assert s.world.retries.pending == []


def test_ordinary_beats_do_nothing() -> None:
    s = Sleeper(ScriptedFreshPrice(_BELOW_STOP_LOSS))
    requests = len(s.world.book.requests)

    for _ in range(10):
        s.beat(_LIMITS.check_every)

    assert s.world.state() is S.RUNNING
    assert s.prices.reads == []
    assert len(s.world.book.requests) == requests
    assert s.notifier.events == []


def test_a_beat_late_by_exactly_the_limit_is_not_a_gap() -> None:
    """Boundary: 'longer than N seconds'."""
    s = Sleeper(ScriptedFreshPrice(_BELOW_STOP_LOSS))

    s.beat(_LIMITS.check_every + _LIMITS.gap_over)

    assert s.world.state() is S.RUNNING
    assert s.prices.reads == []


def test_a_beat_late_by_more_than_the_limit_is_a_gap() -> None:
    s = Sleeper(ScriptedFreshPrice(_BELOW_STOP_LOSS))

    s.beat(_LIMITS.check_every + _LIMITS.gap_over + timedelta(seconds=1))

    assert s.world.state() is S.STOPPED


def test_a_sleep_the_monotonic_clock_did_not_count_is_still_a_gap() -> None:
    """On Linux the monotonic clock stops while the machine is suspended; only
    the wall clock shows the night."""
    s = Sleeper(ScriptedFreshPrice(_BELOW_STOP_LOSS))

    s.sleep(_NIGHT, wall_only=True)

    assert s.world.state() is S.STOPPED


def test_a_wall_clock_set_back_is_not_a_gap() -> None:
    s = Sleeper(ScriptedFreshPrice(_BELOW_STOP_LOSS))
    s.world.clock.advance(-timedelta(hours=2))

    s.beat(_LIMITS.check_every)

    assert s.world.state() is S.RUNNING
    assert s.prices.reads == []


def test_one_sleep_is_one_catch_up() -> None:
    s = Sleeper(ScriptedFreshPrice(_INSIDE_THE_BAND))

    s.sleep(_NIGHT)
    s.beat(_LIMITS.check_every)

    assert len(s.prices.reads) == 1


def test_the_wake_is_logged_and_told_to_the_user() -> None:
    s = Sleeper(ScriptedFreshPrice(_INSIDE_THE_BAND))

    s.sleep(timedelta(hours=8, minutes=30))

    assert len(s.notifier.events) == 1
    headline, detail = s.notifier.events[0]
    assert "8 h 30 min" in headline
    assert "1 bot" in headline
    assert detail


def test_a_wake_with_no_bots_reads_no_price_and_tells_no_one() -> None:
    s = Sleeper(ScriptedFreshPrice(_INSIDE_THE_BAND), grid_world(state=S.STOPPED))
    s.executors.close_all()

    s.sleep(_NIGHT)

    assert s.prices.reads == []
    assert s.notifier.events == []


def test_a_price_the_venue_will_not_give_is_retried_until_it_does() -> None:
    """The network is often not back at the instant the machine wakes."""
    s = Sleeper(ScriptedFreshPrice(None, None, _BELOW_STOP_LOSS))

    s.sleep(_NIGHT)
    assert s.world.state() is S.RUNNING, "no price yet"
    s.run_price_retry()
    s.run_price_retry()

    assert s.world.state() is S.STOPPED
    assert len(s.prices.reads) == 3


def test_the_retries_are_bounded() -> None:
    s = Sleeper(ScriptedFreshPrice(None))

    s.sleep(_NIGHT)
    for _ in range(_LIMITS.price_attempts - 1):
        s.run_price_retry()
    with pytest.raises(AssertionError, match="no price retry"):
        s.run_price_retry()

    assert len(s.prices.reads) == _LIMITS.price_attempts
    assert s.world.state() is S.RUNNING, "the staleness rule (035A) takes it from here"


def test_a_bot_that_is_not_running_is_left_alone_by_a_wake() -> None:
    s = Sleeper(ScriptedFreshPrice(_BELOW_STOP_LOSS), grid_world(state=S.STOPPED))

    s.sleep(_NIGHT)

    assert s.world.state() is S.STOPPED
    assert s.world.book.requests == []


@pytest.mark.parametrize("seconds", [-1, 0])
def test_a_limit_must_be_positive(seconds: int) -> None:
    with pytest.raises(ValueError, match="gap_over"):
        SleepLimits(gap_over=timedelta(seconds=seconds))


def test_the_next_beat_is_armed_before_a_slow_wake_runs() -> None:
    """Review of PR 438: the wake's price reads run on the heartbeat's thread,
    and a venue that is slow to come back can make them last past the gap limit.
    The next beat is therefore armed before the wake, so the wake's own duration
    is never read as a second sleep."""
    pending_at_read: list[int] = []

    class _Watching(ScriptedFreshPrice):
        def read(self, venue, symbol):  # type: ignore[no-untyped-def]
            pending_at_read.append(len(s.world.retries.pending))
            return super().read(venue, symbol)

    s = Sleeper(_Watching(_INSIDE_THE_BAND))
    s.watch.begin()
    s.world.monotonic.advance(_NIGHT.total_seconds())
    s.world.clock.advance(_NIGHT)

    s.world.retries.run_next()

    assert pending_at_read == [1], "the next beat was already waiting during the read"
