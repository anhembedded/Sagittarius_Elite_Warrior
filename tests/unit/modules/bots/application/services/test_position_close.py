"""`EPIC-039H` - the position venue's close, against a simulated venue.

@details The close is reduce-only, cut under the per-order cap, and confirmed from a fresh read of
the position and from nothing else: a position that is still open, or that could not be read, is
waited on and never called flat.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.stop_progress import (
    StopProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    LAST_PRICE,
)

D = Decimal
S = BotLifecycleState
_AT = datetime(2026, 10, 13, 9, tzinfo=UTC)


from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.position_world import (
    a_long_position,
    a_position_world,
    a_registration,
    closer_of,
    flat_once_sold,
)

# --- the close ----------------------------------------------------------------


def test_a_flat_account_closes_nothing_and_sends_nothing() -> None:
    world, _ = a_position_world()

    progress = closer_of(world).close(a_registration("0"), LAST_PRICE)

    assert progress is None
    assert world.book.requests == []


def test_a_long_position_is_closed_by_a_reduce_only_market_sell_and_confirmed_flat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, _ = a_position_world()
    flat_once_sold(world, monkeypatch, "0.05")

    progress = closer_of(world).close(a_registration("0.05"), LAST_PRICE)

    (sent,) = world.book.requests
    assert progress is None
    assert (sent.side, sent.order_type, sent.reduce_only) == (
        OrderSide.SELL,
        OrderType.MARKET,
        True,
    )
    assert sent.quantity == D("0.05")


def test_a_short_position_is_closed_by_a_reduce_only_market_buy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, _ = a_position_world()
    monkeypatch.setattr(
        world.snapshot,
        "open_positions",
        lambda: () if world.book.requests else (a_long_position("-0.05"),),
    )

    closer_of(world).close(a_registration("-0.05"), LAST_PRICE)

    (sent,) = world.book.requests
    assert (sent.side, sent.reduce_only) == (OrderSide.BUY, True)


def test_a_position_over_the_per_order_cap_is_closed_in_slices_under_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, _ = a_position_world()
    flat_once_sold(world, monkeypatch, "5")
    cap = world.executor._context.cap

    progress = closer_of(world).close(a_registration("5"), LAST_PRICE)

    assert progress is None
    assert len(world.book.requests) > 1
    assert sum(r.quantity for r in world.book.requests) == D(5)
    assert all(r.quantity * LAST_PRICE <= cap for r in world.book.requests)


def test_a_position_that_is_still_open_after_the_close_is_waited_on_not_called_flat() -> (
    None
):
    world, _ = a_position_world()
    world.snapshot.holding([a_long_position("0.05")])  # the exchange keeps reporting it

    progress = closer_of(world).close(a_registration("0.05"), LAST_PRICE)

    assert progress is StopProgress.WAITING_ON_EXCHANGE
    assert "still open after the close" in world.runtime().reason_detail


def test_a_position_that_could_not_be_read_is_waited_on_not_called_flat() -> None:
    world, _ = a_position_world()
    world.snapshot.positions_raise(RuntimeError("positionRisk timed out"))

    progress = closer_of(world).close(a_registration("0.05"), LAST_PRICE)

    assert progress is StopProgress.WAITING_ON_EXCHANGE
    assert world.book.requests == [], "nothing is sent on an unread position"


def test_a_remainder_below_one_market_step_is_left_where_it_cannot_be_sent() -> None:
    world, _ = a_position_world()
    world.snapshot.holding([a_long_position("0.0004")])

    progress = closer_of(world).close(a_registration("0.0004"), LAST_PRICE)

    assert progress is None
    assert world.book.requests == []
