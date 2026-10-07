"""`BOT-169` — every failure the Bots screen has reaches the user through the
notifier: a read that failed is a bar on the Bots mode with Retry, a command
that failed or was refused is a message box. The headline is a sentence, never
an exception's text; the exception is the detail."""

from __future__ import annotations

from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    BotStoreReading,
    RefusedBotFile,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_failures import (
    BotsFailures,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    ReadKind,
)

from .bots_screen_fixtures import (
    GOOD_CONFIG,
    SYMBOL,
    VENUE,
    Answers,
    ContainerDispatcher,
    stored,
)


@pytest.mark.parametrize("kind", list(ReadKind))
def test_a_failed_read_is_a_bar_on_the_bots_mode_whose_retry_reads_it_again(
    kind: ReadKind,
) -> None:
    notifier, again, shown = RecordingNotifier(), [], []
    failures = BotsFailures(notifier, again.append, shown.append)

    failures.read_failed(kind, "a00001", "timed out")

    notice = notifier.last
    assert notice.kind is FailureKind.BACKGROUND
    assert (notice.scope, notice.cause) == (BOTS_ROUTE, f"bots.read.{kind.value}")
    assert notice.detail == "timed out"
    assert "timed out" not in notice.headline
    assert notice.retry is not None
    notice.retry()
    assert again == [kind]
    assert (shown != []) is (kind is ReadKind.FILLS)

    failures.read_recovered(kind)

    assert notifier.cleared == [f"bots.read.{kind.value}"]


def test_a_list_that_cannot_be_read_is_a_bar_and_the_next_good_read_clears_it(
    open_bots_screen, monkeypatch: pytest.MonkeyPatch
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    real = screen.store.load_all

    def broken() -> BotStoreReading:
        raise OSError("the bot folder is gone")

    monkeypatch.setattr(screen.store, "load_all", broken)
    screen.settle()

    notice = screen.notifier.last
    assert (notice.kind, notice.cause) == (FailureKind.BACKGROUND, "bots.read.list")
    assert notice.scope == BOTS_ROUTE
    assert notice.detail == "the bot folder is gone"
    assert "gone" not in notice.headline
    assert not screen.view.model.statusIsError
    monkeypatch.setattr(screen.store, "load_all", real)
    assert notice.retry is not None

    notice.retry()
    screen.settle()

    assert "bots.read.list" in screen.notifier.cleared
    assert [bot.bot_id for bot in screen.view.model.bots] == ["a00001"]


def test_bot_files_the_store_refused_are_a_bar_that_clears_when_none_are_left(
    open_bots_screen, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    real = screen.store.load_all
    refused = RefusedBotFile("b00002.json", "not valid JSON")
    monkeypatch.setattr(
        screen.store, "load_all", lambda: BotStoreReading(real().bots, (refused,))
    )
    screen.settle()

    notice = screen.notifier.last
    assert (notice.kind, notice.cause) == (
        FailureKind.BACKGROUND,
        "bots.files.unreadable",
    )
    assert notice.scope == BOTS_ROUTE
    assert "b00002.json" in notice.detail
    assert "not valid JSON" not in notice.headline
    monkeypatch.setattr(screen.store, "load_all", real)

    screen.store.save(stored("c00003", S.DRAFT))
    qtbot.waitUntil(lambda: bool(screen.pool.pending))
    screen.settle()

    assert "bots.files.unreadable" in screen.notifier.cleared


def test_a_command_the_domain_refused_is_a_message_box_with_its_own_sentence(
    open_bots_screen, monkeypatch: pytest.MonkeyPatch
) -> None:
    command = CreateBotCommand("my grid", "grid", VENUE, SYMBOL, GOOD_CONFIG)
    screen = open_bots_screen(answers=Answers(new_bot=command))
    screen.settle()
    real = ContainerDispatcher.dispatch

    def refusing(self: ContainerDispatcher, handler_class: type, dto: object = None):
        if handler_class is not type(command):
            return real(self, handler_class, dto)
        return BotCommandResult.refused(BotRefusal.VENUE_NOT_READY, "Spot is off.")

    monkeypatch.setattr(ContainerDispatcher, "dispatch", refusing)

    screen.view.model.new_bot_requested.emit()
    screen.settle()

    notice = screen.notifier.last
    assert (notice.kind, notice.cause) == (FailureKind.COMMAND, "bots.command")
    assert notice.headline == "Create my grid: refused. Spot is off."
    assert notice.detail == ""
    assert notice.retry is None
    assert screen.view.model.statusIsError
    assert screen.view.status.text() == "Create my grid: not done."


def test_a_command_that_raised_is_a_message_box_whose_headline_has_no_exception(
    open_bots_screen, monkeypatch: pytest.MonkeyPatch
) -> None:
    command = CreateBotCommand("my grid", "grid", VENUE, SYMBOL, GOOD_CONFIG)
    screen = open_bots_screen(answers=Answers(new_bot=command))
    screen.settle()

    def broken(self: object, handler_class: type, input_dto: object = None) -> Any:
        raise RuntimeError("the store is read-only")

    monkeypatch.setattr(ContainerDispatcher, "dispatch", broken)
    screen.view.model.new_bot_requested.emit()
    screen.settle()

    notice = screen.notifier.failures_of(FailureKind.COMMAND)[-1]
    assert notice.cause == "bots.command"
    assert "Create my grid" in notice.headline
    assert "read-only" not in notice.headline
    assert notice.detail == "the store is read-only"
    assert screen.view.model.bots == ()


def test_fills_that_could_not_be_read_say_so_without_the_exception(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.RUNNING)])
    screen.settle()
    screen.activity.history_raises(RuntimeError("history is down"))

    screen.view.model.select_requested.emit("a00001")
    screen.settle()

    notice = screen.notifier.failures_of(FailureKind.BACKGROUND)[-1]
    assert notice.cause == "bots.read.fills"
    assert notice.detail == "history is down"
    assert "history is down" not in screen.view.fills.note.text()
