"""`EPIC-029E` — resuming a HALTED Grid is always safe (ADR D13, O2, §1.4).

Resume cancels every order carrying the bot's tag, derives the inventory and
proposes a new plan from the current price and that inventory — and places
nothing until the user confirms. Proven after a disable that left the old
ladder resting, and after an Emergency Stop that left the inventory sold
(while the user also holds the asset), partly sold or untouched.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import LevelSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
)

S = BotLifecycleState


def _halted_by(cause: TradingSwitchCause) -> GridWorld:
    world = grid_world()
    world.executor.start()
    world.executor.on_switch(False, cause)
    assert world.state() is S.HALTED
    world.book.requests.clear()
    return world


def _sells(world: GridWorld) -> dict[Decimal, Decimal]:
    proposal = world.executor.proposal
    assert proposal is not None
    return {
        lv.price: lv.quantity
        for lv in proposal.plan.levels
        if lv.side is LevelSide.SELL
    }


def test_resume_after_a_disable_cancels_the_old_ladder_and_places_nothing() -> None:
    world = _halted_by(TradingSwitchCause.DISABLED)
    old = set(world.book.open)
    world.derive("4.132")

    world.executor.resume()

    assert set(world.book.cancels) == old
    assert world.book.open == {}
    assert world.book.requests == []
    assert world.state() is S.HALTED
    assert world.executor.proposal is not None


def test_confirming_lays_the_proposed_ladder_with_no_opening_buy() -> None:
    world = _halted_by(TradingSwitchCause.DISABLED)
    world.derive("4.132", cost="499.97")
    world.executor.resume()

    world.executor.confirm_resume()

    assert world.state() is S.RUNNING
    assert [r for r in world.book.requests if r.order_type is OrderType.MARKET] == []
    assert len(world.book.open) == 4
    assert world.runtime().inventory == Decimal("4.132")


def test_after_an_emergency_stop_that_sold_everything_only_buys_are_proposed() -> None:
    """The user holds BTC of their own; the bot's share was sold under its tag,
    so the derived inventory is zero and nothing of the user's is laid out."""
    world = _halted_by(TradingSwitchCause.EMERGENCY_STOP)
    world.book.open.clear()
    world.hold("5")
    world.derive("0")

    world.executor.resume()
    world.executor.confirm_resume()

    assert {r.side for r in world.book.requests} == {OrderSide.BUY}
    assert world.state() is S.RUNNING


def test_after_a_partial_sale_the_sell_side_is_sized_to_what_is_left() -> None:
    world = _halted_by(TradingSwitchCause.EMERGENCY_STOP)
    world.book.open.clear()
    world.derive("2")

    world.executor.resume()

    assert _sells(world) == {Decimal(130): Decimal(2)}


def test_after_an_emergency_stop_that_sold_nothing_the_whole_sell_side_returns() -> (
    None
):
    """Inventory bought before the latest enable sits inside Emergency Stop's
    baseline and is not sold (§1.4)."""
    world = _halted_by(TradingSwitchCause.EMERGENCY_STOP)
    world.book.open.clear()
    world.derive("4.132")

    world.executor.resume()

    assert _sells(world) == {
        Decimal(130): Decimal("2.066"),
        Decimal(140): Decimal("2.066"),
    }


def test_confirming_with_nothing_proposed_does_nothing() -> None:
    world = _halted_by(TradingSwitchCause.DISABLED)

    world.executor.confirm_resume()

    assert world.state() is S.HALTED
    assert world.book.requests == []


def test_a_switch_off_between_proposal_and_confirmation_discards_the_proposal() -> None:
    world = _halted_by(TradingSwitchCause.DISABLED)
    world.derive("0")
    world.executor.resume()

    world.executor.on_switch(False, TradingSwitchCause.EMERGENCY_STOP)
    world.executor.confirm_resume()

    assert world.executor.proposal is None
    assert world.state() is S.HALTED
    assert world.book.requests == []


def test_a_resume_refused_its_budget_proposes_nothing() -> None:
    world = _halted_by(TradingSwitchCause.DISABLED)
    world.session.set_enabled(enabled=False)

    world.executor.resume()

    assert world.executor.proposal is None
    assert world.book.cancels == []
    assert "resume waits" in world.runtime().reason_detail
