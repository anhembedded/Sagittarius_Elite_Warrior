"""`EPIC-035R` — a resume sizes the ladder from what is left, not from what was.

The ladder a resume proposes is laid over the inventory the exchange says the bot
holds (`OwnerInventory`, with its cost). Trading refuses an order that would take
the bot's open BUYs plus that inventory at cost above `capital_quote`, so a BUY
side sized from the whole capital again, after the bot bought down the ladder,
asks for what the budget will refuse. The BUY side shares only what the inventory
leaves of the capital, and an inventory the SELL levels do not reach is reported
to the user instead of being kept in silence.
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
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
)

S = BotLifecycleState
CAPITAL = Decimal(1000)


def _halted_holding(quantity: str, cost: str) -> GridWorld:
    world = grid_world()
    world.executor.start()
    world.executor.facts.on_switch(False, TradingSwitchCause.EMERGENCY_STOP)
    assert world.state() is S.HALTED
    world.book.open.clear()
    world.book.requests.clear()
    world.derive(quantity, cost=cost)
    return world


def _buy_notional(world: GridWorld) -> Decimal:
    proposal = world.executor.proposal
    assert proposal is not None
    return sum(
        (
            lv.price * lv.quantity
            for lv in proposal.plan.levels
            if lv.side is LevelSide.BUY
        ),
        Decimal(0),
    )


def test_resume_after_a_loss_does_not_oversize_the_buy_side() -> None:
    world = _halted_holding("6", cost="800")

    world.executor.resume()

    assert _buy_notional(world) + Decimal(800) <= CAPITAL
    proposal = world.executor.proposal
    assert proposal is not None
    assert len(proposal.plan.buy_levels) == 2, "what is left is shared, not dropped"


def test_resume_with_the_whole_capital_in_inventory_proposes_no_buy() -> None:
    world = _halted_holding("6", cost="1000")

    world.executor.resume()

    proposal = world.executor.proposal
    assert proposal is not None
    assert proposal.plan.buy_levels == ()


def test_a_buy_share_under_the_minimum_notional_leaves_that_level_empty() -> None:
    world = _halted_holding("6", cost="992")

    world.executor.resume()

    proposal = world.executor.proposal
    assert proposal is not None
    assert proposal.plan.buy_levels == (), "4 USDT each is under the 5 USDT minimum"
    assert _buy_notional(world) == 0


def test_a_resume_that_lost_nothing_keeps_the_buy_side_it_always_had() -> None:
    world = _halted_holding("4.132", cost="499.97")

    world.executor.resume()

    proposal = world.executor.proposal
    assert proposal is not None
    assert [lv.quantity for lv in proposal.plan.buy_levels] == [
        Decimal("2.5"),
        Decimal("2.272"),
    ]


def test_the_confirmed_ladder_asks_only_for_what_is_left() -> None:
    world = _halted_holding("6", cost="800")
    world.executor.resume()

    world.executor.confirm_resume()

    assert world.state() is S.RUNNING
    bought = sum(
        (
            r.reference_price * r.quantity
            for r in world.book.requests
            if r.side is OrderSide.BUY
        ),
        Decimal(0),
    )
    assert bought + Decimal(800) <= CAPITAL


def test_inventory_beyond_the_sell_levels_is_named_not_kept_in_silence() -> None:
    world = _halted_holding("6", cost="500")

    world.executor.resume()

    proposal = world.executor.proposal
    assert proposal is not None
    assert proposal.unplaced_inventory == Decimal("1.868")
    detail = world.runtime().reason_detail
    assert "1.868" in detail
    assert "no SELL level" in detail


def test_a_second_resume_names_the_excess_once() -> None:
    world = _halted_holding("6", cost="500")
    world.executor.resume()

    world.executor.resume()

    assert world.runtime().reason_detail.count("1.868") == 1


def test_an_inventory_the_sell_levels_cover_is_not_reported() -> None:
    world = _halted_holding("4.132", cost="499.97")

    world.executor.resume()

    proposal = world.executor.proposal
    assert proposal is not None
    assert proposal.unplaced_inventory == 0
    assert "no SELL level" not in world.runtime().reason_detail


def test_a_resume_that_no_longer_leaves_base_over_removes_the_sentence() -> None:
    world = _halted_holding("6", cost="500")
    world.executor.resume()
    assert "no SELL level" in world.runtime().reason_detail

    world.derive("4.132", cost="499.97")
    world.executor.resume()

    assert "no SELL level" not in world.runtime().reason_detail
    assert world.runtime().reason_detail.startswith("Emergency Stop")
