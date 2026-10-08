"""`EPIC-035H` — a read-only copy of the app reads bots and changes none.

The store is the one place every writer saves through (the use cases, the
executors, the restart rule), so a read-only store covers them all; the runner
is the one door from a command to a running bot, and it answers a Start with a
named refusal before the start's preconditions touch the venue.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.errors import ReadOnlyInstanceError
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.read_only_bot_runner import (
    ReadOnlyBotRunner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.read_only_bot_store import (
    ReadOnlyBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_bot_resume.command import (
    ConfirmBotResumeCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_bot_resume.handler import (
    ConfirmBotResumeCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.pause_bot.command import (
    PauseBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.pause_bot.handler import (
    PauseBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot.command import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot.handler import (
    StopBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.contract_bot_store import (
    sample_bot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import BotLifecycle
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)

_REASON = "Another copy is running; this one is read-only."


class _Runner(IBotRunner):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def start(self, bot_id: str) -> BotCommandResult:
        self.calls.append("start")
        return BotCommandResult.done(bot_id)

    def pause(self, bot_id: str) -> None:
        self.calls.append("pause")

    def resume(self, bot_id: str) -> None:
        self.calls.append("resume")

    def stop(self, bot_id: str, base: BaseHandling) -> None:
        self.calls.append("stop")

    def confirm_resume(self, bot_id: str) -> None:
        self.calls.append("confirm")

    def has_resume_proposal(self, bot_id: str) -> bool:
        self.calls.append("proposal")
        return True


def test_a_read_only_store_reads_what_is_there() -> None:
    inner = FakeBotStore()
    inner.save(sample_bot())
    store = ReadOnlyBotStore(inner, _REASON)

    assert store.load(sample_bot().bot.bot_id) == sample_bot()
    assert store.load_all().bots == (sample_bot(),)
    assert store.exists(sample_bot().bot.bot_id)


def test_a_read_only_store_saves_nothing() -> None:
    inner = FakeBotStore()
    store = ReadOnlyBotStore(inner, _REASON)

    with pytest.raises(ReadOnlyInstanceError, match="read-only"):
        store.save(sample_bot())

    assert inner.load_all().bots == ()


def test_a_read_only_store_deletes_nothing() -> None:
    inner = FakeBotStore()
    inner.save(sample_bot())
    store = ReadOnlyBotStore(inner, _REASON)

    with pytest.raises(ReadOnlyInstanceError):
        store.delete(sample_bot().bot.bot_id)

    assert inner.load_all().bots == (sample_bot(),)


def test_a_read_only_runner_refuses_a_start_by_name() -> None:
    inner = _Runner()

    result = ReadOnlyBotRunner(inner, _REASON).start("abc123")

    assert result.accepted is False
    assert result.refusal is BotRefusal.READ_ONLY_INSTANCE
    assert result.message == _REASON
    assert inner.calls == []


@pytest.mark.parametrize(
    "command",
    [
        lambda runner: runner.pause("abc123"),
        lambda runner: runner.resume("abc123"),
        lambda runner: runner.stop("abc123", BaseHandling.KEEP),
        lambda runner: runner.confirm_resume("abc123"),
    ],
    ids=["pause", "resume", "stop", "confirm_resume"],
)
def test_a_read_only_runner_passes_no_command_to_a_bot(
    command: Callable[[IBotRunner], None],
) -> None:
    inner = _Runner()

    with pytest.raises(ReadOnlyInstanceError):
        command(ReadOnlyBotRunner(inner, _REASON))

    assert inner.calls == []


def test_the_store_says_the_instances_own_reason() -> None:
    with pytest.raises(ReadOnlyInstanceError) as caught:
        ReadOnlyBotStore(FakeBotStore(), _REASON).save(sample_bot())

    assert str(caught.value) == _REASON


def test_a_pause_on_a_read_only_copy_is_a_named_refusal_through_the_handler() -> None:
    """Review of PR 438: the four lifecycle commands reach the runner through
    `BotCommandGate`, which turns the runner's refusal into the same value every
    other refused command is, so the screen words it and nothing escapes raw."""
    store = FakeBotStore()
    stored = sample_bot()
    running = replace(stored.bot, lifecycle=BotLifecycle(BotLifecycleState.RUNNING))
    store.save(StoredBot(running, stored.runtime))
    runner = ReadOnlyBotRunner(_Runner(), _REASON)
    handlers = (
        PauseBotCommandHandler(store, runner).execute(PauseBotCommand("abc123")),
        StopBotCommandHandler(store, runner).execute(
            StopBotCommand("abc123", BaseHandling.KEEP)
        ),
    )

    for result in handlers:
        assert result.accepted is False
        assert result.refusal is BotRefusal.READ_ONLY_INSTANCE
        assert result.message == _REASON


def test_a_confirm_resume_on_a_read_only_copy_is_a_named_refusal() -> None:
    store = FakeBotStore()
    stored = sample_bot()
    halted = replace(stored.bot, lifecycle=BotLifecycle(BotLifecycleState.HALTED))
    store.save(StoredBot(halted, stored.runtime))

    result = ConfirmBotResumeCommandHandler(
        store, ReadOnlyBotRunner(_Runner(), _REASON)
    ).execute(ConfirmBotResumeCommand("abc123"))

    assert result.refusal is BotRefusal.READ_ONLY_INSTANCE
    assert result.message == _REASON
