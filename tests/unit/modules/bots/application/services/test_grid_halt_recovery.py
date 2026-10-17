"""`EPIC-042C` - a Spot Grid halted by a quiet feed or a down stream resumes itself (ADR 042 §2.1).

The incident of 2026-10-17: the feed came back within minutes and the bot stayed HALTED. Here the
same bot waits in AWAITING_RECOVERY, resumes through the person's Resume path once the cause has
stayed clear for the dwell, and ends as a Stop if the stop loss or take profit was crossed. The
clocks are the fakes a test moves; nothing sleeps. The ladder, the cancels and the registration
are the simulated venue's, so what is asserted is what the exchange would hold.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_auto_recovered_event import (
    BotAutoRecoveredEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_recovery_stalled_event import (
    BotRecoveryStalledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.price_freshness import (
    PRICE_START_GRACE_SECONDS,
    RECOVERY_TICK_MAX_AGE_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    DEFAULT_RULE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    FakeUserStreamStatus,
    GridWorld,
    grid_world,
    quote_at,
)

S = BotLifecycleState
_INSIDE = Decimal(121)
_BEAT = 5
_DWELL = int(DEFAULT_RULE.dwell.total_seconds())


def _running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    assert world.state() is S.RUNNING
    world.derive("0")
    return world


def _beats(world: GridWorld, seconds: int, *, tick_every: int | None = _BEAT) -> None:
    """The price watch's beat for `seconds`; a tick every `tick_every` seconds, or none."""
    for elapsed in range(_BEAT, seconds + 1, _BEAT):
        world.monotonic.advance(_BEAT)
        if tick_every is not None and elapsed % tick_every == 0:
            world.executor.facts.on_tick(PriceTick.at(_INSIDE))
        world.executor.facts.on_price_age_check()


def _go_quiet(world: GridWorld) -> None:
    """The feed says nothing for the start grace: the halt of the incident."""
    world.monotonic.advance(PRICE_START_GRACE_SECONDS)
    world.executor.facts.on_price_age_check()


def _waiting() -> GridWorld:
    world = _running()
    _go_quiet(world)
    assert world.state() is S.AWAITING_RECOVERY
    return world


def _events(world: GridWorld, kind: type) -> list:
    return [e for e in world.events.events if isinstance(e, kind)]


def _attempts(world: GridWorld) -> int:
    return len(world.store.load(BotId(BOT)).bot.lifecycle.recovery_attempts)


def test_a_quiet_feed_puts_a_running_bot_in_the_wait_with_its_ladder_off() -> None:
    world = _running()
    assert world.book.open

    _go_quiet(world)

    assert world.state() is S.AWAITING_RECOVERY
    assert world.runtime().reason is GridReason.PRICE_FEED_STALE
    assert world.book.open == {}, "the ladder is off the exchange while the bot waits"
    assert world.runtime().open_orders == ()


def test_a_paused_bot_is_halted_not_left_to_recover_by_itself() -> None:
    """The owner's Pause is never undone by a machine (ADR 042 D8)."""
    world = _running()
    world.executor.pause()

    _go_quiet(world)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.PRICE_FEED_STALE


def test_the_incident_the_feed_returns_and_the_bot_runs_again_with_a_fresh_ladder() -> (
    None
):
    world = _waiting()

    _beats(world, _DWELL + 2 * _BEAT)

    assert world.state() is S.RUNNING
    assert len(world.book.open) == 2, (
        "a fresh ladder: with nothing held, its two BUY levels"
    )
    assert _attempts(world) == 1
    [recovered] = _events(world, BotAutoRecoveredEvent)
    assert (recovered.reason, recovered.attempt, recovered.max_attempts) == (
        "price_feed_stale",
        1,
        3,
    )


def test_the_dwell_is_not_over_before_it_is_over() -> None:
    world = _waiting()

    _beats(world, _DWELL - 2 * _BEAT)

    assert world.state() is S.AWAITING_RECOVERY
    assert _attempts(world) == 0


def test_a_gap_inside_the_dwell_restarts_the_dwell() -> None:
    world = _waiting()
    _beats(world, _DWELL - 3 * _BEAT)
    _beats(world, int(RECOVERY_TICK_MAX_AGE_SECONDS) + _BEAT, tick_every=None)

    _beats(world, _DWELL - 3 * _BEAT)

    assert world.state() is S.AWAITING_RECOVERY, "the dwell began again after the gap"
    _beats(world, 4 * _BEAT)
    assert world.state() is S.RUNNING


def test_a_feed_silent_since_the_halt_never_clears() -> None:
    """The review's trap: a probe built on `stale_detail` calls a dead feed clear."""
    world = _waiting()

    _beats(world, 10 * 60, tick_every=None)

    assert world.state() is S.AWAITING_RECOVERY
    assert _attempts(world) == 0


def test_a_feed_that_ticks_twice_a_minute_never_clears() -> None:
    world = _waiting()

    _beats(world, 10 * 60, tick_every=30)

    assert world.state() is S.AWAITING_RECOVERY
    assert _attempts(world) == 0


def test_a_long_wait_tells_the_owner_once_and_the_bot_still_recovers() -> None:
    world = _waiting()
    stalled_after = int(DEFAULT_RULE.stalled_after.total_seconds())

    _beats(world, stalled_after + 10 * 60, tick_every=None)
    _beats(world, 5 * 60, tick_every=None)

    [stalled] = _events(world, BotRecoveryStalledEvent)
    assert stalled.reason == "price_feed_stale"
    assert stalled.waited_s >= stalled_after
    assert world.state() is S.AWAITING_RECOVERY

    _beats(world, _DWELL + 2 * _BEAT)
    assert world.state() is S.RUNNING
    assert len(_events(world, BotRecoveryStalledEvent)) == 1


@pytest.mark.parametrize(
    ("price", "reason"),
    [(Decimal(89), GridReason.STOP_LOSS), (Decimal(151), GridReason.TAKE_PROFIT)],
)
def test_an_exit_crossed_while_the_feed_was_down_ends_the_bot_and_lays_no_ladder(
    price: Decimal, reason: GridReason
) -> None:
    """ADR 042 D1, D12: the attempt reads a fresh price; the ticks the bot heard were inside."""
    world = _waiting()
    _beats(world, _DWELL - 2 * _BEAT)
    quote_at(world, price)
    sent = len(world.book.requests)

    _beats(world, 4 * _BEAT)

    assert world.state() is S.STOPPED
    assert world.runtime().reason is reason
    assert world.runtime().sell_base_on_stop
    assert world.book.open == {}
    assert len(world.book.requests) == sent, "no ladder order was sent"


def test_a_persons_resume_ends_the_wait_and_is_not_counted() -> None:
    world = _waiting()

    world.executor.resume()
    world.executor.confirm_resume()

    assert world.state() is S.RUNNING
    assert _attempts(world) == 0
    assert _events(world, BotAutoRecoveredEvent) == []


def test_the_automatic_run_waits_while_a_persons_proposal_is_held() -> None:
    world = _waiting()
    world.executor.resume()
    assert world.executor.proposal is not None

    _beats(world, _DWELL + 4 * _BEAT)

    assert world.state() is S.AWAITING_RECOVERY
    assert _attempts(world) == 0
    world.executor.confirm_resume()
    assert world.state() is S.RUNNING


def _budget_refused(world: GridWorld) -> None:
    """The exchange cannot derive the bot's inventory: the Resume path waits, changes nothing."""
    world.session.register_owner_budget_answers(
        OwnerBudgetRegistrationResult(OwnerBudgetRefusal.INVENTORY_UNAVAILABLE)
    )


def test_a_refusal_that_changes_nothing_spends_the_attempt_and_keeps_the_bot_waiting() -> (
    None
):
    world = _waiting()
    _budget_refused(world)

    _beats(world, _DWELL + 2 * _BEAT)

    assert world.state() is S.AWAITING_RECOVERY
    assert _attempts(world) == 1
    assert _events(world, BotAutoRecoveredEvent) == []


def test_the_last_refusal_that_changes_nothing_halts_the_bot_with_the_budget_used_up() -> (
    None
):
    world = _waiting()
    _budget_refused(world)

    for _ in range(DEFAULT_RULE.max_attempts):
        _beats(world, _DWELL + 2 * _BEAT)

    assert world.state() is S.HALTED
    assert _attempts(world) == DEFAULT_RULE.max_attempts
    assert "automatic recoveries allowed are used up" in world.runtime().reason_detail


def test_a_symbol_that_does_not_trade_is_a_new_cause_and_halts_the_bot() -> None:
    world = _waiting()
    world.set_status("BREAK")

    _beats(world, _DWELL + 2 * _BEAT)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.SYMBOL_NOT_TRADING
    assert _attempts(world) == 1


def test_a_rate_limit_met_by_the_attempt_halts_the_bot_for_the_limit() -> None:
    world = _waiting()
    world.book.raise_next = [
        ExchangeRateLimitedError(
            timedelta(seconds=60), banned=False, raw_message="slow"
        )
    ]

    _beats(world, _DWELL + 2 * _BEAT)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.RATE_LIMITED


def test_the_fourth_halt_in_a_day_stays_halted_and_says_the_recoveries_are_used_up() -> (
    None
):
    world = _running()
    for _ in range(DEFAULT_RULE.max_attempts):
        _go_quiet(world)
        _beats(world, _DWELL + 2 * _BEAT)
        assert world.state() is S.RUNNING

    _go_quiet(world)

    assert world.state() is S.HALTED
    assert "used up" in world.runtime().reason_detail
    assert world.book.open == {}


def test_the_budget_survives_a_restart() -> None:
    """The ledger is in the bot's file: a new executor built from it sees the attempts."""
    world = _running()
    for _ in range(2):
        _go_quiet(world)
        _beats(world, _DWELL + 2 * _BEAT)

    stored = world.store.load(BotId(BOT)).bot
    world.factory.create(stored)

    assert len(stored.lifecycle.recovery_attempts) == 2
    # The third halt is still allowed and the fourth is not: the count is the file's.
    _go_quiet(world)
    _beats(world, _DWELL + 2 * _BEAT)
    assert world.state() is S.RUNNING
    _go_quiet(world)
    assert world.state() is S.HALTED


def test_a_fill_the_bot_missed_while_waiting_is_booked_from_the_exchange_when_it_resumes() -> (
    None
):
    """The Resume path derives the inventory from exchange evidence (ADR D6), so what the ladder
    sold while the feed was down is counted before the new ladder is sized."""
    world = _waiting()
    world.derive("4.132", cost="499.97")

    _beats(world, _DWELL + 2 * _BEAT)

    assert world.state() is S.RUNNING
    assert world.runtime().inventory == Decimal("4.132")


def test_a_stream_that_never_comes_back_never_recovers_the_bot() -> None:
    streams = FakeUserStreamStatus(connected=False)
    world = grid_world(user_streams=streams)
    world.executor.start()
    world.derive("0")
    world.executor.facts.halt_user_stream_down(timedelta(seconds=130))
    assert world.state() is S.AWAITING_RECOVERY
    assert world.runtime().reason is GridReason.USER_STREAM_DOWN

    _beats(world, 10 * 60)

    assert world.state() is S.AWAITING_RECOVERY
    assert _attempts(world) == 0


def test_a_stream_that_comes_back_recovers_the_bot_after_the_dwell() -> None:
    streams = FakeUserStreamStatus(connected=False)
    world = grid_world(user_streams=streams)
    world.executor.start()
    world.derive("0")
    world.executor.facts.halt_user_stream_down(timedelta(seconds=130))
    streams.connected = True

    _beats(world, _DWELL + 2 * _BEAT)

    assert world.state() is S.RUNNING
    [recovered] = _events(world, BotAutoRecoveredEvent)
    assert recovered.reason == "user_stream_down"


def test_the_entry_park_that_failed_does_not_let_a_ladder_be_laid_over_resting_orders() -> (
    None
):
    """The review's carried criterion: if the cancel on entering the wait was lost, the orders
    may still rest; the attempt's own cancel is what clears them, and when it fails too nothing
    new is laid."""
    world = _running()
    resting = set(world.book.open)
    world.book.cancel_raises = [
        ConnectionError("lost"),
        *[ConnectionError("lost")] * 40,
    ]
    _go_quiet(world)
    assert world.state() is S.AWAITING_RECOVERY
    assert set(world.book.open) == resting, "the entry cancel was lost; the orders rest"
    submitted = len(world.book.requests)

    _beats(world, _DWELL + 2 * _BEAT)

    assert world.state() is not S.RUNNING
    assert len(world.book.requests) == submitted, (
        "no order was sent over the resting ones"
    )
    assert set(world.book.open) == resting
