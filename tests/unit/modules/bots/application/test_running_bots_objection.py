"""`EPIC-029F` (ADR O4) — closing the app names every bot that is not at rest."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.running_bots_objection import (
    RunningBotsObjection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)

from .helpers import seed

_AT_REST = (BotLifecycleState.DRAFT, BotLifecycleState.STOPPED)


def test_bots_at_rest_raise_no_objection() -> None:
    store = FakeBotStore()
    for index, state in enumerate(_AT_REST):
        seed(store, f"a{index}0000", state)

    assert RunningBotsObjection(store).objection() is None


@pytest.mark.parametrize(
    "state",
    [state for state in BotLifecycleState if state not in _AT_REST],
    ids=lambda state: state.value,
)
def test_every_other_state_objects_and_says_what_closing_leaves(
    state: BotLifecycleState,
) -> None:
    store = FakeBotStore()
    seed(store, "a3f9c1", state)
    seed(store, "b00000", BotLifecycleState.STOPPED)

    objection = RunningBotsObjection(store).objection()

    assert objection is not None
    assert f"grid one ({state.value})" in objection
    assert objection.count("grid one") == 1
    assert "resting orders on the exchange" in objection
    assert "stop loss or take profit" in objection
