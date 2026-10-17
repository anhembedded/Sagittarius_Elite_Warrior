"""`EPIC-042C` - what an attempt that does not recover does, the budget, the stream and the entry park (ADR 042 §2.1).

The incident of 2026-10-17: the feed came back within minutes and the bot stayed HALTED. Here the
same bot waits in AWAITING_RECOVERY, resumes through the person's Resume path once the cause has
stayed clear for the dwell, and ends as a Stop if the stop loss or take profit was crossed. The
clocks are the fakes a test moves; nothing sleeps. The ladder, the cancels and the registration
are the simulated venue's, so what is asserted is what the exchange would hold.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_auto_recovered_event import (
    BotAutoRecoveredEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_user_stream_status import (
    FakeUserStreamStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
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
    GridWorld,
    grid_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.halt_recovery_world import (
    BEAT,
    DWELL,
    attempts_of,
    beats,
    events_of,
    go_quiet,
    running,
    waiting,
)

S = BotLifecycleState


def _budget_refused(world: GridWorld) -> None:
    """The exchange cannot derive the bot's inventory: the Resume path waits, changes nothing."""
    world.session.register_owner_budget_answers(
        OwnerBudgetRegistrationResult(OwnerBudgetRefusal.INVENTORY_UNAVAILABLE)
    )


def test_a_refusal_that_changes_nothing_spends_the_attempt_and_keeps_the_bot_waiting() -> (
    None
):
    world = waiting()
    _budget_refused(world)

    beats(world, DWELL + 2 * BEAT)

    assert world.state() is S.AWAITING_RECOVERY
    assert attempts_of(world) == 1
    assert events_of(world, BotAutoRecoveredEvent) == []


def test_the_last_refusal_that_changes_nothing_halts_the_bot_with_the_budget_used_up() -> (
    None
):
    world = waiting()
    _budget_refused(world)

    for _ in range(DEFAULT_RULE.max_attempts):
        beats(world, DWELL + 2 * BEAT)

    assert world.state() is S.HALTED
    assert attempts_of(world) == DEFAULT_RULE.max_attempts
    assert "automatic recoveries allowed are used up" in world.runtime().reason_detail


def test_a_symbol_that_does_not_trade_is_a_new_cause_and_halts_the_bot() -> None:
    world = waiting()
    world.set_status("BREAK")

    beats(world, DWELL + 2 * BEAT)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.SYMBOL_NOT_TRADING
    assert attempts_of(world) == 1


def test_a_rate_limit_met_by_the_attempt_halts_the_bot_for_the_limit() -> None:
    world = waiting()
    world.book.raise_next = [
        ExchangeRateLimitedError(
            timedelta(seconds=60), banned=False, raw_message="slow"
        )
    ]

    beats(world, DWELL + 2 * BEAT)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.RATE_LIMITED


def test_the_fourth_halt_in_a_day_stays_halted_and_says_the_recoveries_are_used_up() -> (
    None
):
    world = running()
    for _ in range(DEFAULT_RULE.max_attempts):
        go_quiet(world)
        beats(world, DWELL + 2 * BEAT)
        assert world.state() is S.RUNNING

    go_quiet(world)

    assert world.state() is S.HALTED
    assert "used up" in world.runtime().reason_detail
    assert world.book.open == {}


def test_the_budget_survives_a_restart() -> None:
    """The ledger is in the bot's file: a new executor built from it sees the attempts."""
    world = running()
    for _ in range(2):
        go_quiet(world)
        beats(world, DWELL + 2 * BEAT)

    stored = world.store.load(BotId(BOT)).bot
    world.factory.create(stored)

    assert len(stored.lifecycle.recovery_attempts) == 2
    # The third halt is still allowed and the fourth is not: the count is the file's.
    go_quiet(world)
    beats(world, DWELL + 2 * BEAT)
    assert world.state() is S.RUNNING
    go_quiet(world)
    assert world.state() is S.HALTED


def test_a_fill_the_bot_missed_while_waiting_is_booked_from_the_exchange_when_it_resumes() -> (
    None
):
    """The Resume path derives the inventory from exchange evidence (ADR D6), so what the ladder
    sold while the feed was down is counted before the new ladder is sized."""
    world = waiting()
    world.derive("4.132", cost="499.97")

    beats(world, DWELL + 2 * BEAT)

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

    beats(world, 10 * 60)

    assert world.state() is S.AWAITING_RECOVERY
    assert attempts_of(world) == 0


def test_a_stream_that_comes_back_recovers_the_bot_after_the_dwell() -> None:
    streams = FakeUserStreamStatus(connected=False)
    world = grid_world(user_streams=streams)
    world.executor.start()
    world.derive("0")
    world.executor.facts.halt_user_stream_down(timedelta(seconds=130))
    streams.connected = True

    beats(world, DWELL + 2 * BEAT)

    assert world.state() is S.RUNNING
    [recovered] = events_of(world, BotAutoRecoveredEvent)
    assert recovered.reason == "user_stream_down"


def test_the_entry_park_that_failed_does_not_let_a_ladder_be_laid_over_resting_orders() -> (
    None
):
    """The review's carried criterion: if the cancel on entering the wait was lost, the orders
    may still rest; the attempt's own cancel is what clears them, and when it fails too nothing
    new is laid."""
    world = running()
    resting = set(world.book.open)
    world.book.cancel_raises = [
        ConnectionError("lost"),
        *[ConnectionError("lost")] * 40,
    ]
    go_quiet(world)
    assert world.state() is S.AWAITING_RECOVERY
    assert set(world.book.open) == resting, "the entry cancel was lost; the orders rest"
    submitted = len(world.book.requests)

    beats(world, DWELL + 2 * BEAT)

    assert world.state() is not S.RUNNING
    assert len(world.book.requests) == submitted, (
        "no order was sent over the resting ones"
    )
    assert set(world.book.open) == resting
