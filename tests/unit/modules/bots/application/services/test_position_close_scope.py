"""`EPIC-039H` - the close covers the bot's own position and nothing else (owner's answer, 2026-10-13).

@details A halt or a Stop on a position venue closes the position the bot built from its own fills,
reduce-only, by that quantity. A position the owner opened by hand on the same symbol is left
untouched and reported in words; it is a divergence or a foreign position, never something the bot
closes. The owner decided this in the coordinator session on 2026-10-13 (~13:01 UTC).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.stop_progress import (
    StopProgress,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    ForeignPosition,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    LAST_PRICE,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.position_world import (
    a_long_position,
    a_position_world,
    a_registration,
    closer_of,
    exchange_holds_less_after_each_sale,
)

D = Decimal


def _market_sells(world) -> list[Decimal]:
    return [
        r.quantity
        for r in world.book.requests
        if r.order_type is OrderType.MARKET and r.side is OrderSide.SELL
    ]


def test_a_hand_added_position_beside_the_bots_is_left_open_and_only_the_bots_is_sold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, _ = a_position_world()
    exchange_holds_less_after_each_sale(world, monkeypatch, "0.05")

    progress = closer_of(world).close(a_registration("0.03"), LAST_PRICE)

    assert progress is None
    assert _market_sells(world) == [D("0.03")]
    assert all(
        r.reduce_only for r in world.book.requests if r.order_type is OrderType.MARKET
    )


def test_a_flat_bot_beside_a_position_by_hand_closes_nothing_and_is_flat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`EPIC-039I`: trading refuses a registration as a foreign position only when the bot's own
    fills add up to flat, which is a NEUTRAL bot's ordinary state between cycles. The close has
    nothing of its own to send and ends; it never waits for a position it cannot derive."""
    world, _ = a_position_world()
    monkeypatch.setattr(
        world.snapshot, "open_positions", lambda: (a_long_position("0.05"),)
    )
    foreign = OwnerBudgetRegistrationResult(
        OwnerBudgetRefusal.FOREIGN_POSITION,
        foreign_position=ForeignPosition("BTCUSDT", D("0.05")),
    )

    progress = closer_of(world).close(foreign, LAST_PRICE)

    assert progress is None
    assert world.book.requests == []


def test_the_fill_of_an_exit_slice_does_not_open_a_position_in_a_flat_runtime() -> None:
    """Review of #523, wiring: the fact that an exit slice filled reaches the runtime through
    `GridFacts`, which books it as an exit (`book_exit_fill`), not as a trade that could open."""
    world, _ = a_position_world()
    context = world.executor._context
    context.state.update(replace(context.state.runtime, entry_side=None))
    context.off_ladder.add_exit("exit-1")

    world.executor.facts.on_fill(
        BotOrderFill("exit-1", OrderSide.SELL, D(100), D("0.012"), D(0), "USDT")
    )

    assert world.runtime().inventory == 0


def test_what_is_left_to_the_owner_is_said_in_words(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    world, _ = a_position_world()
    exchange_holds_less_after_each_sale(world, monkeypatch, "0.05")

    with caplog.at_level(logging.WARNING, logger="App.Bots.GridExecutor"):
        closer_of(world).close(a_registration("0.03"), LAST_PRICE)

    said = [
        r.getMessage() for r in caplog.records if "[foreign-position]" in r.getMessage()
    ]
    assert len(said) == 1
    assert "0.02" in said[0] and "left open" in said[0]


def test_a_position_that_did_not_shrink_by_what_was_sold_still_waits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exchange keeps reporting 0.05 after the bot sold its 0.03: the close did not happen."""
    world, _ = a_position_world()
    monkeypatch.setattr(
        world.snapshot, "open_positions", lambda: (a_long_position("0.05"),)
    )

    progress = closer_of(world).close(a_registration("0.03"), LAST_PRICE)

    assert progress is StopProgress.WAITING_ON_EXCHANGE


def test_a_bot_that_derives_less_than_it_may_hold_never_sells_the_owners_difference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, _ = a_position_world()
    exchange_holds_less_after_each_sale(world, monkeypatch, "0.05")

    closer_of(world).close(a_registration("0.01"), LAST_PRICE)

    assert _market_sells(world) == [D("0.01")]


def test_a_bot_with_nothing_of_its_own_sells_nothing_of_the_owners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, _ = a_position_world()
    exchange_holds_less_after_each_sale(world, monkeypatch, "0.05")

    progress = closer_of(world).close(a_registration("0"), LAST_PRICE)

    assert progress is None
    assert world.book.requests == []


def test_when_the_exchange_holds_less_than_the_bot_derives_only_what_is_there_is_sold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A partial forced close left 0.01 of the bot's 0.03."""
    world, _ = a_position_world()
    exchange_holds_less_after_each_sale(world, monkeypatch, "0.01")

    progress = closer_of(world).close(a_registration("0.03"), LAST_PRICE)

    assert progress is None
    assert _market_sells(world) == [D("0.01")]


def test_a_position_on_the_other_side_of_the_bots_is_not_the_bots_to_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bot derives a long; the exchange holds a short the owner opened: nothing is sent."""
    world, _ = a_position_world()
    monkeypatch.setattr(
        world.snapshot, "open_positions", lambda: (a_long_position("-0.02"),)
    )

    progress = closer_of(world).close(a_registration("0.03"), LAST_PRICE)

    assert progress is None
    assert world.book.requests == []
