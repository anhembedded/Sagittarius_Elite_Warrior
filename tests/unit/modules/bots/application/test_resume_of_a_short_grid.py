"""`EPIC-039I` - a resume of a short grid is refused in words, whatever the position held.

@details A resume sizes SELL levels to a long inventory (`resized_for_inventory`). Over a held
short it has no reading; over a flat short it would lay only reduce-only BUYs the exchange refuses
(review of #521). The direction decides. The mirror of the resume for a signed position is a later
task; until then the user stops the bot (which closes the position) and starts a new run.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_runtime_codec import (
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.readiness_world import (
    ReadinessWorld,
    readiness_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.test_resume_bot_readiness import (
    HELD,
    _halt,
    _resume,
    _Runner,
)


@pytest.fixture
def world() -> ReadinessWorld:
    made = readiness_world()
    _halt(made, BotLifecycleState.HALTED)
    return made


def test_a_resume_over_a_short_position_is_refused_in_words_and_nothing_is_queued(
    world: ReadinessWorld,
) -> None:
    """`EPIC-039I`: a resume sizes a ladder to a long inventory; a short has no such reading yet,
    so the bot is not resumed over it. The user stops it (which closes the position)."""
    stored = world.store.load(BotId(BOT))
    short = GridRuntime((), inventory=-HELD, cost=Decimal(500))
    world.store.save(StoredBot(stored.bot, encode_runtime(short)))
    runner = _Runner()

    result = _resume(world, runner)

    assert not result.accepted
    assert "short or neutral grid" in result.message
    assert runner.resumed == []


@pytest.mark.parametrize("direction", ["SHORT", "NEUTRAL"])
def test_a_resume_of_a_short_or_neutral_grid_is_refused_even_over_a_flat_position(
    world: ReadinessWorld, direction: str
) -> None:
    """`EPIC-039I` review: a resume sizes a long inventory, so over a flat short grid it would lay
    only reduce-only BUYs the exchange refuses, and a neutral grid holds either sign. The direction
    decides, not what is held."""
    stored = world.store.load(BotId(BOT))
    definition = replace(
        stored.bot.definition,
        config={
            **stored.bot.definition.config,
            "direction": direction,
            "leverage": "2",
        },
    )
    bot = Bot(
        stored.bot.bot_id, definition, stored.bot.lifecycle, stored.bot.created_at
    )
    flat = GridRuntime((), inventory=Decimal(0), cost=Decimal(0))
    world.store.save(StoredBot(bot, encode_runtime(flat)))
    runner = _Runner()

    result = _resume(world, runner)

    assert not result.accepted
    assert "short or neutral grid" in result.message
    assert runner.resumed == []
