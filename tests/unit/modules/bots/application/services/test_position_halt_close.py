"""`EPIC-039H` - a halt's close does not depend on the ladder's cancel (review of #490, blocking 1).

@details A leveraged position is never left bare (O8): when the halt's cancel is refused, or the
parking itself raises, the bot still stops with the close; the Stop's own cancel and retries then
settle what rests. The probe that found it: the bot ended HALTED with the long still open, no close
order sent and no retry.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_housekeeping import (
    GridHousekeeping,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    grid_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.position_world import (
    a_position_world,
    a_registration,
    exchange_holds_less_after_each_sale,
)

S = BotLifecycleState
D = Decimal


def _one_order_rests(world) -> None:
    """A ladder order of the bot's on the book, so the halt has something to cancel."""
    order = Order(
        client_order_id=ClientOrderId("SEW-a3f9c1-0000000001"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=D("0.01"),
        price=D(100),
    )
    world.book.open[str(order.client_order_id)] = order


def _market_orders(world) -> list[object]:
    return [r for r in world.book.requests if r.order_type is OrderType.MARKET]


def test_a_halt_whose_cancel_is_refused_still_closes_the_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, _ = a_position_world(state=S.RUNNING)
    exchange_holds_less_after_each_sale(world, monkeypatch, "0.03")
    world.session.register_owner_budget_answers(a_registration("0.03"))
    _one_order_rests(world)
    world.book.cancel_raises = [ConnectionError("read timed out")]

    world.executor.facts.halt_user_stream_down(timedelta(seconds=130))

    assert _market_orders(world), (
        "the close was sent although the ladder's cancel failed"
    )
    assert world.state() is S.STOPPED
    assert "may still rest" in world.runtime().reason_detail


def test_a_halt_whose_parking_raises_still_closes_the_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, _ = a_position_world(state=S.RUNNING)
    exchange_holds_less_after_each_sale(world, monkeypatch, "0.03")
    world.session.register_owner_budget_answers(a_registration("0.03"))
    _one_order_rests(world)

    real = GridHousekeeping.cancel_tagged
    calls: list[int] = []

    def cancel_blows_up_once(self):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("the cancel path broke")
        return real(self)

    monkeypatch.setattr(GridHousekeeping, "cancel_tagged", cancel_blows_up_once)

    world.executor.facts.halt_user_stream_down(timedelta(seconds=130))

    assert _market_orders(world)
    assert world.state() is S.STOPPED
    assert "may still rest" in world.runtime().reason_detail


def test_a_halt_that_cannot_close_says_the_position_stays_open_on_the_exchange() -> (
    None
):
    """Review of #490, item 4: a switch-off, a rejected key or a rate limit halts without a cancel
    or a close, because the order session is closed or the key is refused. On a position venue the
    halt's words say so, instead of the silence of a Spot halt (whose base is the user's to keep).
    `EPIC-039L`'s stop on the exchange is what protects the position meanwhile."""
    world, _ = a_position_world(state=S.RUNNING)

    world.executor.facts.on_switch(False, TradingSwitchCause.EMERGENCY_STOP)

    assert world.state() is S.HALTED
    assert "position stays open on the exchange" in world.runtime().reason_detail
    assert _market_orders(world) == []


def test_a_spot_halt_that_cannot_cancel_keeps_the_words_it_always_had() -> None:
    world = grid_world(state=S.RUNNING)

    world.executor.facts.on_switch(False, TradingSwitchCause.EMERGENCY_STOP)

    assert world.state() is S.HALTED
    assert "stays open" not in world.runtime().reason_detail
