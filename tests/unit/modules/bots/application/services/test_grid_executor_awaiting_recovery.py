"""`EPIC-042B` — the Grid answers for a bot waiting in AWAITING_RECOVERY (ADR 042 §2.4).

These tests put a bot in the state directly and prove what the state must mean wherever the
Grid names a state: the ladder comes off on entering it, a person's Resume re-plans it like a
HALTED bot's, an Emergency Stop ends the wait, a stop loss ends the bot, and a rate limit met in
it (`EPIC-042F`) keeps the bot waiting, now for the pause too.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.halt_recovery_world import (
    waiting,
)

S = BotLifecycleState
E = BotLifecycleEvent
_DETAIL = "last tick 62 s ago; the limit is 60 s"


def _waiting_with_nothing_on_the_exchange() -> GridWorld:
    world = grid_world(state=S.AWAITING_RECOVERY)
    world.derive("0")
    return world


def _halt_transiently(world: GridWorld) -> None:
    """Applies the event as a task on the bot's worker, as `EPIC-042C`'s halt will."""
    state = world.executor._context.state
    world.executor._post(
        "transient halt",
        lambda: state.transition(
            E.HALT_TRANSIENT, GridReason.PRICE_FEED_STALE, _DETAIL
        ),
    )


def test_a_ladder_is_taken_off_the_exchange_on_entering_the_wait() -> None:
    """The review's blocking finding: the table alone does not park."""
    world = grid_world()
    world.executor.start()
    assert world.book.open, "the ladder rests while the bot runs"

    _halt_transiently(world)

    assert world.state() is S.AWAITING_RECOVERY
    assert world.book.open == {}
    assert world.runtime().open_orders == ()


def test_a_persons_resume_in_the_wait_proposes_a_ladder_and_confirm_lays_it() -> None:
    world = _waiting_with_nothing_on_the_exchange()

    world.executor.resume()
    assert world.state() is S.AWAITING_RECOVERY
    assert world.executor.proposal is not None

    world.executor.confirm_resume()
    assert world.state() is S.RUNNING
    assert world.book.open


def test_an_emergency_stop_ends_the_wait_in_halted() -> None:
    world = _waiting_with_nothing_on_the_exchange()

    world.executor.facts.on_switch(False, TradingSwitchCause.EMERGENCY_STOP)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.SWITCH_OFF


def test_a_tick_through_the_stop_loss_ends_a_waiting_bot() -> None:
    """The exits stay watched while waiting (ADR 042 D12)."""
    world = _waiting_with_nothing_on_the_exchange()

    world.executor.facts.on_tick(PriceTick.at(Decimal(89)))

    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.STOP_LOSS


def test_a_rate_limit_met_laying_a_persons_confirmed_resume_puts_the_bot_back_to_waiting() -> (
    None
):
    """The confirmed Resume entered STARTING and its first order met a limit: a new halt, and the
    pause is a transient one, so the bot waits again, now for the pause (`EPIC-042F`)."""
    world = _waiting_with_nothing_on_the_exchange()
    world.book.raise_next = [
        ExchangeRateLimitedError(
            timedelta(seconds=60), banned=False, raw_message="slow down"
        )
    ]

    world.executor.resume()
    world.executor.confirm_resume()

    assert world.state() is S.AWAITING_RECOVERY
    assert world.runtime().reason is GridReason.RATE_LIMITED


def test_a_task_that_meets_a_rate_limit_in_the_wait_keeps_the_bot_waiting_for_the_pause() -> (
    None
):
    """`GridRateLimitPause` finds a limit in a bot that waits (`_HALTED_BY_A_LIMIT`): the wait goes
    on, it says the pause holds it too, and its reason and dwell are not replaced."""
    world = waiting()

    def meets_the_limit() -> None:
        raise ExchangeRateLimitedError(
            timedelta(seconds=60), banned=False, raw_message="slow down"
        )

    world.executor._post("a read", meets_the_limit)

    assert world.state() is S.AWAITING_RECOVERY
    runtime = world.runtime()
    assert runtime.reason is GridReason.PRICE_FEED_STALE
    assert "the exchange also asked for a pause of 60 s" in runtime.reason_detail
