"""`EPIC-035D`, `EPIC-042F` — a rate limit holds a bot for as long as the exchange asked, then it resumes.

`-1003`, `-1015`, HTTP 429 and 418 used to end in ERROR (a request that raised),
which needs a manual Stop and Start. They are a named, temporary wait:
`GridReason.RATE_LIMITED`, the pause the exchange stated in the bot's reason. Since `EPIC-042F`
the wait is the halt-recovery mechanism's (AWAITING_RECOVERY): the probe says *clear* when the
pause has ended, the recovery run attempts after the dwell (the margin), and the attempt is the
propose-and-confirm a user's Resume runs, so the budget is re-derived and every tagged order taken
off before a fresh ladder goes out. While a rate limit holds, nothing is sent: the waiting bot's
ladder is not cancelled (the cancels would be refused), and a stop that was waiting on the exchange
waits for the pause.

The clocks are the fakes of `EPIC-035C` and `EPIC-042C`: a test moves the price watch's beat
(`beats`); nothing sleeps. The scheduler still runs a stop's retry.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_stop_retry import (
    STOP_RETRY_DELAYS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_auto_recovered_event import (
    BotAutoRecoveredEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
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
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    DEFAULT_RULE,
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
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.halt_recovery_world import (
    BEAT,
    attempts_of,
    beats,
    events_of,
)

S = BotLifecycleState
_PAUSE = timedelta(seconds=60)
_SWITCH = TradingSwitchCause.EMERGENCY_STOP
#: Seconds to the beat that finds the pause over, and to the one after the dwell that attempts.
_PAST_THE_PAUSE = int(_PAUSE.total_seconds()) + 2 * BEAT


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


def _waiting_for_the_limit(pause: timedelta = _PAUSE) -> GridWorld:
    """A bot whose ladder was being laid when the exchange said slow down."""
    world = grid_world()
    world.book.raise_next = [_limited(pause)]
    world.executor.start()
    assert world.state() is S.AWAITING_RECOVERY
    world.derive("0")
    return world


def test_a_rate_limited_order_holds_the_bot_with_a_named_reason_not_error() -> None:
    world = _waiting_for_the_limit()

    assert world.state() is S.AWAITING_RECOVERY
    runtime = world.runtime()
    assert runtime.reason is GridReason.RATE_LIMITED
    assert "60 s" in runtime.reason_detail
    assert "resumes by itself" in runtime.reason_detail


def test_nothing_is_scheduled_the_wait_is_the_recovery_runs_own() -> None:
    world = _waiting_for_the_limit()

    assert world.retries.pending == []


def test_the_bot_does_not_resume_before_the_pause_ends_and_does_after_it_plus_the_margin() -> (
    None
):
    world = _waiting_for_the_limit()
    world.book.requests.clear()

    beats(world, int(_PAUSE.total_seconds()) - BEAT)
    assert world.state() is S.AWAITING_RECOVERY, "the pause still runs"
    assert world.book.requests == [], "nothing is sent while it runs"
    assert attempts_of(world) == 0

    beats(world, 2 * BEAT + int(AUTO_RESUME_MARGIN.total_seconds()))

    assert world.state() is S.RUNNING
    assert attempts_of(world) == 1


def test_a_halt_for_a_rate_limit_does_not_try_to_cancel_into_the_pause() -> None:
    """The cancels would be refused; the attempt cancels everything tagged."""
    world = _running()
    world.book.raise_next = [_limited()]

    _fill_whole(world, Decimal(110))

    assert world.state() is S.AWAITING_RECOVERY
    assert world.runtime().reason is GridReason.RATE_LIMITED
    assert world.book.cancels == []


def test_the_bot_resumes_by_itself_when_the_pause_ends() -> None:
    world = _waiting_for_the_limit()
    world.book.requests.clear()

    beats(world, _PAST_THE_PAUSE)

    assert world.state() is S.RUNNING
    assert len(world.book.open) == 2, "a fresh ladder, no inventory: the buys"
    assert world.runtime().reason is not GridReason.RATE_LIMITED
    recovered = events_of(world, BotAutoRecoveredEvent)
    assert [e.reason for e in recovered] == ["rate_limited"]


def test_the_resume_takes_off_what_the_waiting_ladder_left_resting() -> None:
    world = _running()
    world.book.raise_next = [_limited()]
    _fill_whole(world, Decimal(110))
    rested = set(world.book.open)
    assert world.state() is S.AWAITING_RECOVERY
    assert rested, "the rest of the ladder stays on the exchange during the pause"

    beats(world, _PAST_THE_PAUSE)

    assert rested <= set(world.book.cancels)
    assert world.state() is S.RUNNING
    assert not rested & set(world.book.open), "none of the old orders remains"


def test_a_counter_order_that_is_rate_limited_waits_then_resumes() -> None:
    world = _running()
    world.book.raise_next = [_limited()]

    _fill_whole(world, Decimal(110))

    assert world.state() is S.AWAITING_RECOVERY
    assert world.runtime().reason is GridReason.RATE_LIMITED
    beats(world, _PAST_THE_PAUSE)
    assert world.state() is S.RUNNING


def test_a_resume_the_user_asked_for_that_hit_the_limit_leaves_the_wait_to_finish_by_itself() -> (
    None
):
    world = _waiting_for_the_limit()
    world.activity.open_orders_error = _limited()

    world.executor.resume()

    assert world.state() is S.AWAITING_RECOVERY
    assert world.runtime().reason is GridReason.RATE_LIMITED
    assert attempts_of(world) == 0, "a person's Resume is never counted"
    world.activity.open_orders_error = None
    beats(world, 2 * _PAST_THE_PAUSE)
    assert world.state() is S.RUNNING


def test_a_pause_that_has_not_really_ended_waits_again_and_spends_an_attempt() -> None:
    world = _waiting_for_the_limit()
    world.activity.open_orders_error = _limited(timedelta(seconds=30))

    beats(world, _PAST_THE_PAUSE)

    assert world.state() is S.AWAITING_RECOVERY
    assert world.runtime().reason is GridReason.RATE_LIMITED
    assert attempts_of(world) == 1
    world.activity.open_orders_error = None
    beats(world, 30 + 3 * BEAT)
    assert world.state() is S.RUNNING
    assert attempts_of(world) == 2


def test_the_automatic_resumes_are_bounded_by_the_budget_and_the_last_one_says_so() -> (
    None
):
    world = _waiting_for_the_limit()
    world.activity.open_orders_error = _limited()

    for _ in range(DEFAULT_RULE.max_attempts + 1):
        beats(world, _PAST_THE_PAUSE)

    assert world.state() is S.HALTED
    assert attempts_of(world) == DEFAULT_RULE.max_attempts
    assert "automatic recoveries allowed are used up" in world.runtime().reason_detail
    assert world.retries.pending == []


def test_a_ban_longer_than_the_wait_is_left_to_the_user() -> None:
    long_ban = MAX_AUTO_RESUME_WAIT + timedelta(minutes=1)
    world = grid_world()
    world.book.raise_next = [_limited(long_ban)]
    world.executor.start()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.RATE_LIMITED
    assert "resume by hand" in world.runtime().reason_detail
    beats(world, _PAST_THE_PAUSE)
    assert world.state() is S.HALTED, "nothing recovers it by itself"


def test_a_task_that_meets_a_ban_longer_than_the_wait_halts_for_a_person() -> None:
    world = _running()

    def meets_the_ban() -> None:
        raise _limited(MAX_AUTO_RESUME_WAIT + timedelta(minutes=1), banned=True)

    world.executor._post("a read", meets_the_ban)

    assert world.state() is S.HALTED
    assert "resume by hand" in world.runtime().reason_detail


def test_a_pause_of_exactly_the_longest_wait_is_still_waited_for() -> None:
    world = _waiting_for_the_limit(MAX_AUTO_RESUME_WAIT)
    assert world.state() is S.AWAITING_RECOVERY


def test_a_stop_pressed_during_the_pause_is_not_undone_by_the_resume() -> None:
    world = _waiting_for_the_limit()
    world.executor.stop(ExposureHandling.KEEP)
    assert world.state() is S.STOPPED

    beats(world, _PAST_THE_PAUSE)

    assert world.state() is S.STOPPED
    assert world.book.open == {}


def test_a_resume_the_user_confirmed_first_leaves_the_wait_nothing_to_do() -> None:
    world = _waiting_for_the_limit()
    world.executor.resume()
    world.executor.confirm_resume()
    assert world.state() is S.RUNNING
    laid = dict(world.book.open)

    beats(world, _PAST_THE_PAUSE)

    assert world.state() is S.RUNNING
    assert world.book.open == laid
    assert attempts_of(world) == 0


def test_a_limit_reached_by_a_second_task_does_not_start_a_second_wait() -> None:
    world = _waiting_for_the_limit()

    world.executor.facts.on_price_age_check()
    world.executor.facts.on_switch(True, _SWITCH)

    assert world.retries.pending == []
    assert attempts_of(world) == 0
    beats(world, _PAST_THE_PAUSE)
    assert world.state() is S.RUNNING
    assert attempts_of(world) == 1


def test_a_stop_whose_cancel_is_rate_limited_waits_for_the_pause() -> None:
    world = _running()
    world.book.cancel_raises = [_limited(timedelta(seconds=90))]

    world.executor.stop(ExposureHandling.KEEP)

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

    world.executor.stop(ExposureHandling.CLOSE_AT_MARKET)

    assert world.state() is S.STOPPING
    assert world.retries.pending, "the stop is retried"
    world.retries.run_next()
    assert world.state() is S.STOPPED
    assert [r for r in world.book.requests if r.order_type is OrderType.MARKET]


@pytest.mark.parametrize("pause", [timedelta(seconds=1), timedelta(minutes=10)])
def test_the_reason_names_the_pause_in_seconds(pause: timedelta) -> None:
    world = _waiting_for_the_limit(pause)
    assert f"{int(pause.total_seconds())} s" in world.runtime().reason_detail


# -- a pause met reading the price (a tick too old to use) is still a pause ------


def test_a_stop_whose_price_read_meets_a_pause_waits_instead_of_failing() -> None:
    """The tick is hours old, so the stop reads the book; the book is rate limited
    (review of PR #439: the pause lost its type on that read and ended in ERROR)."""
    world = _running()
    world.executor.facts.on_tick(PriceTick.at(Decimal(121)))
    world.monotonic.advance(3 * 3600)
    world.terms.ask_for_a_pause("BTCUSDT", timedelta(seconds=45))

    world.executor.stop(ExposureHandling.CLOSE_AT_MARKET)

    assert world.state() is S.STOPPING
    assert [r.delay for r in world.retries.pending] == [
        max(STOP_RETRY_DELAYS[0], timedelta(seconds=45) + AUTO_RESUME_MARGIN)
    ]
    quote_at(world, Decimal(121))
    world.retries.run_next()
    assert world.state() is S.STOPPED


def test_a_confirmation_whose_price_read_meets_a_pause_halts_for_a_person() -> None:
    """The bot is HALTED, a state the mechanism never recovers (ADR 042): the person who asked
    for the Resume is told to ask again once the pause ends, and no timer is left behind."""
    world = grid_world()
    world.executor.start()
    world.executor.facts.on_switch(False, _SWITCH)
    world.derive("0")
    world.executor.resume()
    world.terms.ask_for_a_pause("BTCUSDT", timedelta(seconds=30))

    world.executor.confirm_resume()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.RATE_LIMITED
    assert "resume by hand" in world.runtime().reason_detail
    assert world.retries.pending == []
    beats(world, _PAST_THE_PAUSE)
    assert world.state() is S.HALTED, "nothing recovers a HALTED bot by itself"
    quote_at(world, Decimal(121))
    world.executor.resume()
    world.executor.confirm_resume()
    assert world.state() is S.RUNNING


def test_an_automatic_resume_whose_price_read_meets_a_pause_waits_again() -> None:
    world = _waiting_for_the_limit()
    world.terms.ask_for_a_pause("BTCUSDT", timedelta(seconds=30))

    beats(world, _PAST_THE_PAUSE)

    assert world.state() is S.AWAITING_RECOVERY
    assert world.runtime().reason is GridReason.RATE_LIMITED
    assert attempts_of(world) == 1
    quote_at(world, Decimal(121))
    beats(world, 30 + 3 * BEAT)
    assert world.state() is S.RUNNING
    assert attempts_of(world) == 2
