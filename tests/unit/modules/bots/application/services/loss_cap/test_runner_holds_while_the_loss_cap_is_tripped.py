"""`EPIC-026L` — the runner, the one door every start and resume passes, refuses while the cap is tripped.

The collaborators the runner must not reach are doubles that fail the test when touched, so a
refusal that still queued the start would be a red test, not a quiet pass."""

from __future__ import annotations

from typing import cast

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.start.grid_start_preconditions import (
    GridStartPreconditions,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_runner import (
    BotRunner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_hold import (
    ILossCapHold,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import seed
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CONFIG,
)

SENTENCE = "The account-level loss cap is tripped; acknowledge it first."


class _Hold(ILossCapHold):
    def __init__(self, sentence: str | None) -> None:
        self.sentence = sentence

    def restart_refusal(self) -> str | None:
        return self.sentence


class _Untouchable:
    """Fails the test the moment the runner reaches for it."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"the runner reached for {name} past a held loss cap")


def _runner(sentence: str | None, state: BotLifecycleState) -> tuple[BotRunner, str]:
    store = FakeBotStore()
    seed(store, BOT, state, config=CONFIG, runtime={})
    runner = BotRunner(
        store,
        cast(IBotClock, _Untouchable()),
        cast(GridStartPreconditions, _Untouchable()),
        cast(BotExecutors, _Untouchable()),
        _Hold(sentence),
    )
    return runner, BOT


def test_a_start_is_refused_with_the_caps_sentence_and_touches_nothing() -> None:
    runner, bot_id = _runner(SENTENCE, BotLifecycleState.DRAFT)

    result = runner.start(bot_id)

    assert not result.accepted
    assert result.refusal is BotRefusal.LOSS_CAP_TRIPPED and result.message == SENTENCE
    assert result.bot_id == bot_id


@pytest.mark.parametrize(
    "state",
    [BotLifecycleState.PAUSED, BotLifecycleState.RECOVERING, BotLifecycleState.HALTED],
)
def test_a_resume_is_refused_whatever_state_the_bot_waits_in(
    state: BotLifecycleState,
) -> None:
    runner, bot_id = _runner(SENTENCE, state)

    assert runner.resume(bot_id).refusal is BotRefusal.LOSS_CAP_TRIPPED


def test_with_no_hold_the_runner_goes_on_to_its_own_work() -> None:
    """The mutation check: without the hold the runner reaches the clock, and the double says so."""
    runner, bot_id = _runner(None, BotLifecycleState.DRAFT)

    with pytest.raises(AssertionError, match="past a held loss cap"):
        runner.start(bot_id)
