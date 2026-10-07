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
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_readiness_fsm_matrix import (
    ReadinessState,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)

from .bots_screen_fixtures import (
    GOOD_CONFIG,
    SYMBOL,
    VENUE,
    Answers,
    ContainerDispatcher,
    stored,
)
from .connect_screen_helpers import failure, select


@pytest.mark.parametrize("kind", [ReadKind.LIST, ReadKind.PLANNER, ReadKind.FILLS])
def test_a_failed_read_is_a_bar_on_the_bots_mode_whose_retry_reads_it_again(
    kind: ReadKind,
) -> None:
    notifier, again, shown, refused = RecordingNotifier(), [], [], []
    failures = BotsFailures(notifier, again.append, shown.append, refused.append)

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


def _refused_history() -> AccountHistoryUnavailableError:
    return AccountHistoryUnavailableError(
        "order history: -2015 Invalid API-key, IP, or permissions for action.",
        ConnectionFailureKind.KEY_REJECTED,
    )


def test_fills_the_venue_refuses_raise_no_bar_of_their_own(open_bots_screen) -> None:
    """`BUG-181` — the owner's screenshot: a key the exchange refuses made the
    fills read fail too, and "The fills of this bot could not be read" was a
    second bar for the one cause the Connect step had already told."""
    screen = open_bots_screen([stored("a00001", S.RUNNING)])
    screen.account.answer_with(failure(ConnectionFailureKind.KEY_REJECTED))
    screen.activity.history_raises(_refused_history())
    screen.settle()

    select(screen, "a00001")
    screen.settle()

    bars = screen.notifier.failures_of(FailureKind.BACKGROUND)
    assert {bar.cause for bar in bars} == {"bots.connect.spot_testnet"}
    assert screen.view.fills.note.text().endswith("not read: key refused")


def test_fills_the_venue_refuses_fail_a_step_that_believed_it_was_connected(
    open_bots_screen,
) -> None:
    """The account read passed and the fills were refused: the connection is not
    what the step thought, so it fails and tells it once, in its own bar."""
    screen = open_bots_screen([stored("a00001", S.RUNNING)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    assert screen.presenter._account.view.state is ReadinessState.DESIGNING

    screen.activity.history_raises(_refused_history())
    screen.view.model.refresh_fills_requested.emit()
    screen.settle()

    assert screen.presenter._account.view.state is ReadinessState.FAILED
    bars = screen.notifier.failures_of(FailureKind.BACKGROUND)
    assert [bar.cause for bar in bars] == ["bots.connect.spot_testnet"]
    assert screen.notifier.last.retry is not None


def test_a_fills_failure_the_exchange_does_not_name_stays_its_own_bar(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.RUNNING)])
    screen.settle()
    screen.activity.history_raises(AccountHistoryUnavailableError("order history: odd"))

    select(screen, "a00001")
    screen.settle()

    bars = screen.notifier.failures_of(FailureKind.BACKGROUND)
    assert [bar.cause for bar in bars] == ["bots.read.fills"]
    assert screen.presenter._account.view.state is ReadinessState.DESIGNING


def test_a_refusal_of_another_venue_does_not_fail_the_bot_that_is_connected(
    open_bots_screen,
) -> None:
    """A fills answer for the venue a bot has since left must not fail the bot
    that is connected on the other one (the source guard in `venue_refused`)."""
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    assert screen.presenter._account.view.state is ReadinessState.DESIGNING

    screen.presenter._account.venue_refused(
        ConnectFailure(
            AccountSource.SPOT_MAINNET, ConnectionFailureKind.KEY_REJECTED, "x"
        )
    )

    assert screen.presenter._account.view.state is ReadinessState.DESIGNING
    assert not [n for n in screen.notifier.failures if n.cause.startswith("bots.")]
