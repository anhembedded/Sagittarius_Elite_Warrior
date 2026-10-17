"""`EPIC-042C` - the shared world of the halt-recovery tests: a running Spot Grid, the price watch's beat, the dwell.

The clocks are the fakes a test moves; nothing sleeps. `beats` is the price watch's 5 s beat with a
tick at each one, or with none; `go_quiet` is the silence of the incident; `waiting` is the bot in
AWAITING_RECOVERY with its ladder off.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.price_freshness import (
    PRICE_START_GRACE_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    DEFAULT_RULE,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    GridWorld,
    grid_world,
)

S = BotLifecycleState
INSIDE = Decimal(121)
BEAT = 5
DWELL = int(DEFAULT_RULE.dwell.total_seconds())


def running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    assert world.state() is S.RUNNING
    world.derive("0")
    return world


def beats(world: GridWorld, seconds: int, *, tick_every: int | None = BEAT) -> None:
    """The price watch's beat for `seconds`; a tick every `tick_every` seconds, or none."""
    for elapsed in range(BEAT, seconds + 1, BEAT):
        world.monotonic.advance(BEAT)
        if tick_every is not None and elapsed % tick_every == 0:
            world.executor.facts.on_tick(PriceTick.at(INSIDE))
        world.executor.facts.on_price_age_check()


def go_quiet(world: GridWorld) -> None:
    """The feed says nothing for the start grace: the halt of the incident."""
    world.monotonic.advance(PRICE_START_GRACE_SECONDS)
    world.executor.facts.on_price_age_check()


def waiting() -> GridWorld:
    world = running()
    go_quiet(world)
    assert world.state() is S.AWAITING_RECOVERY
    return world


def events_of(world: GridWorld, kind: type) -> list:
    return [e for e in world.events.events if isinstance(e, kind)]


def attempts_of(world: GridWorld) -> int:
    return len(world.store.load(BotId(BOT)).bot.lifecycle.recovery_attempts)
