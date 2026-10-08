"""`EPIC-035A` — a stop loss is watched in every state that holds orders.

Before this task `_WATCHES_EXITS` left out STARTING and RECOVERING, so a price
that crossed the stop loss while a restored bot waited for trading to open (or
while its ladder was being laid) was remembered and never acted on. The exit is
the existing `_run_stop` path: it takes the ladder off and sells the base.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    grid_world,
    recovering_world,
)

S = BotLifecycleState

#: The world's stop loss is `price:90` and its take profit `price:150`.
_BELOW_STOP_LOSS = Decimal(89)
_ABOVE_TAKE_PROFIT = Decimal(151)


@pytest.mark.parametrize("state", [S.STARTING, S.RECOVERING])
def test_a_stop_loss_is_watched_in_recovering_and_starting(state: S) -> None:
    world = recovering_world() if state is S.RECOVERING else grid_world(state=state)

    world.executor.on_tick(_BELOW_STOP_LOSS)

    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.STOP_LOSS
    assert world.book.open == {}


@pytest.mark.parametrize("state", [S.STARTING, S.RECOVERING])
def test_a_take_profit_is_watched_in_recovering_and_starting(state: S) -> None:
    world = recovering_world() if state is S.RECOVERING else grid_world(state=state)

    world.executor.on_tick(_ABOVE_TAKE_PROFIT)

    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.TAKE_PROFIT


def test_a_price_inside_the_band_leaves_a_recovering_bot_alone() -> None:
    world = recovering_world()

    world.executor.on_tick(Decimal(121))

    assert world.state() is S.RECOVERING
    assert len(world.book.open) == 4
