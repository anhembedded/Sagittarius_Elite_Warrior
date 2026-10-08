"""`EPIC-035D` (M3) — a rate limit halts a bot for as long as the exchange asked, then it resumes.

`-1003`, `-1015`, HTTP 429 and 418 used to end in ERROR (a request that raised),
which needs a manual Stop and Start. They are now a named, temporary HALT:
`GridReason.RATE_LIMITED`, the pause the exchange stated in the bot's reason, and
a resume that the bot's retry scheduler runs when the pause ends — the same
propose-and-confirm a user's Resume runs, so the budget is re-derived and every
tagged order taken off before a fresh ladder goes out. While a rate limit holds,
nothing is sent: a halted bot's ladder is not cancelled (the cancels would be
refused), and a stop that was waiting on the exchange waits for the pause.

The scheduler is the fake of `EPIC-035C`: a test runs the retry when the pause
"ends", and nothing sleeps.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stop_retry import (
    STOP_RETRY_DELAYS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.rate_limit_pause import (
    AUTO_RESUME_MARGIN,
    MAX_AUTO_RESUME_WAIT,
    MAX_AUTO_RESUMES,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
    quote_at,
)

S = BotLifecycleState
_PAUSE = timedelta(seconds=60)
_SWITCH = TradingSwitchCause.EMERGENCY_STOP


def _limited(
    pause: timedelta = _PAUSE, *, banned: bool = False
) -> ExchangeRateLimitedError:
    return ExchangeRateLimitedError(
        pause, banned=banned, raw_message=f"the exchange asked for {pause}"
    )


def _running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    assert world.state() is S.RUNNING
    world.derive("0")
    return world


def _fill_whole(world: GridWorld, price: Decimal) -> None:
    """The order resting at `price` fills completely."""
    order = world.book.open[world.open_ids_by_price()[price]]
    world.fill(price, str(order.quantity))


def _halted_by_the_limit(pause: timedelta = _PAUSE) -> GridWorld:
    """A bot whose ladder was being laid when the exchange said slow down."""
    world = grid_world()
    world.book.raise_next = [_limited(pause)]
    world.executor.start()
    assert world.state() is S.HALTED
    world.derive("0")
    return world


def test_a_rate_limited_order_halts_the_bot_with_a_named_reason_not_error() -> None:
    world = _halted_by_the_limit()

    assert world.state() is S.HALTED
    runtime = world.runtime()
    assert runtime.reason is GridReason.RATE_LIMITED
    assert "60 s" in runtime.reason_detail
    assert "resumes by itself" in runtime.reason_detail


def test_the_resume_is_scheduled_for_the_end_of_the_pause_plus_a_margin() -> None:
    world = _halted_by_the_limit()

    assert [r.delay for r in world.retries.pending] == [_PAUSE + AUTO_RESUME_MARGIN]


def test_a_halt_for_a_rate_limit_does_not_try_to_cancel_into_the_pause() -> None:
    """The cancels would be refused; the resume cancels everything tagged."""
    world = _running()
    world.book.raise_next = [_limited()]

    _fill_whole(world, Decimal(110))

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.RATE_LIMITED
    assert world.book.cancels == []


def test_the_bot_resumes_by_itself_when_the_pause_ends() -> None:
    world = _halted_by_the_limit()
    world.book.requests.clear()

    world.retries.run_next()

    assert world.state() is S.RUNNING
    assert len(world.book.open) == 2, "a fresh ladder, no inventory: the buys"
    assert world.runtime().reason is not GridReason.RATE_LIMITED


def test_the_resume_takes_off_what_the_halted_ladder_left_resting() -> None:
    world = _running()
    world.book.raise_next = [_limited()]
    _fill_whole(world, Decimal(110))
    rested = set(world.book.open)
    assert world.state() is S.HALTED
    assert rested, "the rest of the ladder stays on the exchange during the pause"

    world.retries.run_next()

    assert rested <= set(world.book.cancels)
    assert world.state() is S.RUNNING
    assert not rested & set(world.book.open), "none of the old orders remains"


def test_a_counter_order_that_is_rate_limited_halts_then_resumes() -> None:
    world = _running()
    world.book.raise_next = [_limited()]

    _fill_whole(world, Decimal(110))

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.RATE_LIMITED
    world.retries.run_next()
    assert world.state() is S.RUNNING


def test_a_resume_the_user_asked_for_that_hit_the_limit_finishes_by_itself() -> None:
    world = _halted_by_the_limit()
    world.retries.pending.clear()
    world.activity.open_orders_error = _limited()

    world.executor.resume()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.RATE_LIMITED
    assert len(world.retries.pending) == 1
    world.activity.open_orders_error = None
    world.retries.run_next()
    assert world.state() is S.RUNNING


def test_a_pause_that_has_not_really_ended_waits_again() -> None:
    world = _halted_by_the_limit()
    world.activity.open_orders_error = _limited(timedelta(seconds=30))

    world.retries.run_next()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.RATE_LIMITED
    assert [r.delay for r in world.retries.pending] == [
        timedelta(seconds=30) + AUTO_RESUME_MARGIN
    ]
    world.activity.open_orders_error = None
    world.retries.run_next()
    assert world.state() is S.RUNNING


def test_the_automatic_resumes_are_bounded_and_the_last_one_says_so() -> None:
    world = _halted_by_the_limit()
    world.activity.open_orders_error = _limited()

    for _ in range(MAX_AUTO_RESUMES):
        assert world.retries.pending, "another is scheduled while any are left"
        world.retries.run_next()

    assert world.retries.pending == []
    assert world.state() is S.HALTED
    assert "automatic resumes are used up" in world.runtime().reason_detail


def test_a_ban_longer_than_the_wait_a_timer_may_hold_is_left_to_the_user() -> None:
    long_ban = MAX_AUTO_RESUME_WAIT + timedelta(minutes=1)
    world = _halted_by_the_limit(long_ban)

    assert world.retries.pending == []
    detail = world.runtime().reason_detail
    assert "resume by hand" in detail
    assert world.state() is S.HALTED


def test_a_pause_of_exactly_the_longest_wait_is_still_scheduled() -> None:
    world = _halted_by_the_limit(MAX_AUTO_RESUME_WAIT)
    assert len(world.retries.pending) == 1


def test_a_stop_pressed_during_the_pause_is_not_undone_by_the_resume() -> None:
    world = _halted_by_the_limit()
    world.executor.stop(BaseHandling.KEEP)
    assert world.state() is S.STOPPED

    world.retries.run_next()

    assert world.state() is S.STOPPED
    assert world.book.open == {}


def test_a_resume_the_user_confirmed_first_leaves_the_timer_nothing_to_do() -> None:
    world = _halted_by_the_limit()
    world.executor.resume()
    world.executor.confirm_resume()
    assert world.state() is S.RUNNING
    laid = dict(world.book.open)

    world.retries.run_next()

    assert world.state() is S.RUNNING
    assert world.book.open == laid


def test_a_limit_reached_by_a_second_task_does_not_schedule_a_second_resume() -> None:
    world = _halted_by_the_limit()
    assert len(world.retries.pending) == 1

    world.executor.facts.on_price_age_check()
    world.executor.facts.on_switch(True, _SWITCH)

    assert len(world.retries.pending) == 1


def test_a_stop_whose_cancel_is_rate_limited_waits_for_the_pause() -> None:
    world = _running()
    world.book.cancel_raises = [_limited(timedelta(seconds=90))]

    world.executor.stop(BaseHandling.KEEP)

    assert world.state() is S.STOPPING
    assert world.runtime().reason is not GridReason.RATE_LIMITED
    assert [r.delay for r in world.retries.pending] == [
        max(STOP_RETRY_DELAYS[0], timedelta(seconds=90) + AUTO_RESUME_MARGIN)
    ]
    world.retries.run_next()
    assert world.state() is S.STOPPED


def test_a_stop_selling_the_base_waits_when_a_slice_is_rate_limited() -> None:
    world = _running()
    world.derive("4.9")
    world.book.raise_next = [_limited(timedelta(seconds=45))]

    world.executor.stop(BaseHandling.SELL_AT_MARKET)

    assert world.state() is S.STOPPING
    assert world.retries.pending, "the stop is retried"
    world.retries.run_next()
    assert world.state() is S.STOPPED
    assert [r for r in world.book.requests if r.order_type is OrderType.MARKET]


@pytest.mark.parametrize("pause", [timedelta(seconds=1), timedelta(minutes=10)])
def test_the_reason_names_the_pause_in_seconds(pause: timedelta) -> None:
    world = _halted_by_the_limit(pause)
    assert f"{int(pause.total_seconds())} s" in world.runtime().reason_detail


# -- a pause met reading the price (a tick too old to use) is still a pause ------


def test_a_stop_whose_price_read_meets_a_pause_waits_instead_of_failing() -> None:
    """The tick is hours old, so the stop reads the book; the book is rate limited
    (review of PR #439: the pause lost its type on that read and ended in ERROR)."""
    world = _running()
    world.executor.facts.on_tick(Decimal(121))
    world.monotonic.advance(3 * 3600)
    world.terms.ask_for_a_pause("BTCUSDT", timedelta(seconds=45))

    world.executor.stop(BaseHandling.SELL_AT_MARKET)

    assert world.state() is S.STOPPING
    assert [r.delay for r in world.retries.pending] == [
        max(STOP_RETRY_DELAYS[0], timedelta(seconds=45) + AUTO_RESUME_MARGIN)
    ]
    quote_at(world, Decimal(121))
    world.retries.run_next()
    assert world.state() is S.STOPPED


def test_a_confirmation_whose_price_read_meets_a_pause_halts_for_it() -> None:
    world = grid_world()
    world.executor.start()
    world.executor.facts.on_switch(False, _SWITCH)
    world.derive("0")
    world.executor.resume()
    world.terms.ask_for_a_pause("BTCUSDT", timedelta(seconds=30))

    world.executor.confirm_resume()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.RATE_LIMITED
    assert len(world.retries.pending) == 1, "the automatic resume is kept"
    quote_at(world, Decimal(121))
    world.retries.run_next()
    assert world.state() is S.RUNNING


def test_an_automatic_resume_whose_price_read_meets_a_pause_waits_again() -> None:
    world = _halted_by_the_limit()
    world.terms.ask_for_a_pause("BTCUSDT", timedelta(seconds=30))

    world.retries.run_next()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.RATE_LIMITED
    assert [r.delay for r in world.retries.pending] == [
        timedelta(seconds=30) + AUTO_RESUME_MARGIN
    ]
    quote_at(world, Decimal(121))
    world.retries.run_next()
    assert world.state() is S.RUNNING
