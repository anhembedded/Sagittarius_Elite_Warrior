"""`BUG-190` — a start refused because trading went off owes the cancel of its partial ladder.

Cancels are refused while the order session is closed, so a start (or a
confirmed resume) cut short by a switch-off cannot take its partial ladder off
at that moment (D13). Unlike a RUNNING bot's whole ladder, that ladder belongs
to a plan that never completed: only Resume (which cancels first and re-plans)
or Stop can follow. The debt is written on the bot, as `EPIC-035C` does for a
start the app's restart cut short, and paid when trading is enabled.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
)

S = BotLifecycleState
_OFF = ExecuteOrderSafetyGate.TRADING_SWITCH_OFF


def _start_cut_by_the_switch() -> GridWorld:
    """Two opening slices and one ladder order are accepted, then trading goes
    off; the session being closed, the cancel the park would make is refused."""
    world = grid_world()
    world.book.refuse_next = [None, None, None, _OFF]
    world.executor.start()
    return world


def _resume_cut_by_the_switch() -> GridWorld:
    world = grid_world()
    world.executor.start()
    world.executor.facts.on_switch(False, TradingSwitchCause.EMERGENCY_STOP)
    world.derive("4.132", cost="499.97")
    world.executor.resume()
    world.book.cancels.clear()
    world.book.refuse_next = [None, _OFF]
    world.executor.confirm_resume()
    return world


def test_a_start_cut_by_the_switch_writes_the_debt_on_the_bot() -> None:
    """Red before: the reason was `SWITCH_OFF`, which no later step pays."""
    world = _start_cut_by_the_switch()

    runtime = world.runtime()
    assert world.state() is S.HALTED
    assert runtime.reason is GridReason.START_CUT_BY_SWITCH_OFF
    assert "cancelled when trading is enabled" in runtime.reason_detail
    assert world.book.open, "the partial ladder rests: the session was closed"


def test_enabling_trading_cancels_the_partial_ladder_of_a_cut_start() -> None:
    """Red before: the HALTED bot stayed as it was and its partial ladder kept
    resting until the user pressed Resume or Stop."""
    world = _start_cut_by_the_switch()
    assert world.book.open

    world.executor.facts.on_switch(True, TradingSwitchCause.ENABLED)

    assert world.book.open == {}
    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.START_INTERRUPTED_CLEARED
    assert "trading went off while this bot was starting" in (
        world.runtime().reason_detail
    )


def test_a_cancel_refused_by_the_closed_session_waits_for_the_enable() -> None:
    world = _start_cut_by_the_switch()
    world.book.cancel_refusals = [_OFF]

    world.executor.facts.on_switch(True, TradingSwitchCause.ENABLED)

    assert world.runtime().reason is GridReason.START_CUT_BY_SWITCH_OFF
    assert world.book.open, "still owed"
    world.executor.facts.on_switch(True, TradingSwitchCause.ENABLED)
    assert world.book.open == {}
    assert world.runtime().reason is GridReason.START_INTERRUPTED_CLEARED


def test_a_confirmed_resume_cut_by_the_switch_owes_the_cancel_too() -> None:
    world = _resume_cut_by_the_switch()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.START_CUT_BY_SWITCH_OFF
    assert world.book.open, "the part of the ladder laid before the switch"

    world.executor.facts.on_switch(True, TradingSwitchCause.ENABLED)

    assert world.book.open == {}
    assert world.runtime().reason is GridReason.START_INTERRUPTED_CLEARED


def test_the_debt_is_not_a_park_the_closed_session_would_refuse() -> None:
    """The guard must not try (and report a refusal) while trading is off."""
    world = _start_cut_by_the_switch()

    assert world.book.cancels == []
    assert "may still rest:" not in world.runtime().reason_detail


def test_a_running_bots_whole_ladder_still_rests_after_the_enable() -> None:
    """D13 stands for a ladder that completed: its bot is a valid grid whose
    owner chose to switch trading off; Resume re-plans it."""
    world = grid_world()
    world.executor.start()
    resting = set(world.book.open)
    assert world.state() is S.RUNNING

    world.executor.facts.on_switch(False, TradingSwitchCause.EMERGENCY_STOP)
    world.executor.facts.on_switch(True, TradingSwitchCause.ENABLED)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.SWITCH_OFF
    assert set(world.book.open) == resting
    assert world.book.cancels == []


def test_a_counter_order_refused_by_the_switch_leaves_a_running_ladder_alone() -> None:
    world = grid_world()
    world.executor.start()
    world.book.refuse_next = [_OFF]

    world.fill(Decimal(110), "2.272")

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.SWITCH_OFF
    assert world.book.cancels == []
