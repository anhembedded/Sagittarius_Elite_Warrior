"""The actor's public surface stays split by audience (architecture-rule §5.4).

`IBotExecutor` holds the commands, `IBotFacts` the facts; `GridExecutor` reaches
the second through `facts`. Retire when: the 15-member ceiling is enforced by a
repository-wide guard that covers `src/modules/bots`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_executor import (
    GridExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_facts import (
    GridFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    IBotExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_facts import IBotFacts
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    grid_world,
)

_CEILING = 15


def _public(cls: type) -> set[str]:
    return {name for name in vars(cls) if not name.startswith("_")}


def test_the_grid_executor_has_no_more_public_members_than_the_ceiling() -> None:
    assert len(_public(GridExecutor)) <= _CEILING


def test_the_facts_are_not_members_of_the_executor() -> None:
    assert _public(GridExecutor).isdisjoint(_public(IBotFacts))
    assert _public(IBotFacts) <= _public(GridFacts)


def test_the_executor_port_is_the_commands_and_the_facts_accessor() -> None:
    assert "facts" in _public(IBotExecutor)
    assert _public(IBotExecutor).isdisjoint(_public(IBotFacts))


def test_the_executor_hands_out_its_own_facts_port() -> None:
    world = grid_world()

    assert isinstance(world.executor.facts, IBotFacts)
    assert world.executor.facts is world.executor.facts
