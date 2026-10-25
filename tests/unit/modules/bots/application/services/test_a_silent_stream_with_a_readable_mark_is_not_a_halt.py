"""`BUG-270` - a position venue's price read over REST counts as a price heard.

The incident: a Futures bot's price WebSocket died while REST worked, its stop loss and take profit
were being judged on the mark price every beat, and the age check, which looked at the stream alone,
halted it for "no price". The mark read is the bot's own price on that venue (`IMarkSource`), so a
successful read restarts the age as a tick does; when neither the stream nor the mark answers for
the limit, the bot still halts, and a crossed exit still ends it.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.price_freshness import (
    PRICE_STALE_AFTER_SECONDS,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.position_world import (
    Marks,
    a_position_world,
)

S = BotLifecycleState
D = Decimal

_BEAT = 5
#: The world's stop loss is `price:90`.
_BELOW_STOP_LOSS = D(89)


def _beats(world: GridWorld, seconds: int) -> None:
    """The price watch's beat for `seconds`, with no tick from the stream."""
    for _ in range(0, seconds, _BEAT):
        world.monotonic.advance(_BEAT)
        world.executor.facts.on_price_age_check()


def _running(marks: Marks) -> GridWorld:
    world, _ = a_position_world(marks=marks, state=S.RUNNING)
    world.executor.facts.on_tick(PriceTick.at(D(121)))
    return world


def test_a_dead_stream_with_a_readable_mark_does_not_halt_the_bot() -> None:
    world = _running(Marks("121"))

    _beats(world, int(PRICE_STALE_AFTER_SECONDS) * 3)

    assert world.state() is S.RUNNING


def test_a_dead_stream_and_a_dead_mark_still_halt_the_bot() -> None:
    marks = Marks("121")
    world = _running(marks)
    marks.unreadable = "no answer"

    _beats(world, int(PRICE_STALE_AFTER_SECONDS) + _BEAT)

    assert world.runtime().reason is GridReason.PRICE_FEED_STALE


def test_a_mark_that_comes_back_inside_the_limit_keeps_the_bot_running() -> None:
    marks = Marks("121")
    world = _running(marks)
    marks.unreadable = "no answer"
    _beats(world, int(PRICE_STALE_AFTER_SECONDS) - 2 * _BEAT)
    marks.unreadable = None

    _beats(world, int(PRICE_STALE_AFTER_SECONDS))

    assert world.state() is S.RUNNING


def test_a_mark_below_the_stop_loss_still_stops_a_bot_whose_stream_is_dead() -> None:
    marks = Marks("121")
    world = _running(marks)
    _beats(world, 30)
    marks.mark = _BELOW_STOP_LOSS

    _beats(world, _BEAT)

    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.STOP_LOSS


def test_a_quiet_stream_is_said_once_while_the_mark_carries_the_bot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = _running(Marks("121"))

    with caplog.at_level(logging.WARNING, logger="App.Bots.GridExecutor"):
        _beats(world, 60)

    told = [r for r in caplog.records if "[price-poll]" in r.getMessage()]
    assert len(told) == 1
    assert "quiet for 15 s" in told[0].getMessage()
