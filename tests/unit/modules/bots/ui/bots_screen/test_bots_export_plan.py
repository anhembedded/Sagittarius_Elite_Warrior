"""`BOT-176` - Bots → Export plan…, on the presenter's real wiring.

The screen runs over the bots module's real object graph (`open_bots_screen`), so the
query the command dispatches is the one `BotsModule` binds, and the file it writes is the
one `bot export` would write.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QGuiApplication
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    BotPlanDocument,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.export_bot_plan import (
    ExportBotPlanQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    EXPORT_PLAN,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.export_plan_dialog import (
    ExportPlanAction,
    ExportPlanChoice,
    ExportPlanScope,
)

from .bots_screen_fixtures import Answers, BotsScreen, stored

_ALL = ExportPlanScope.ALL
_SELECTED = ExportPlanScope.SELECTED
_SAVE = ExportPlanAction.SAVE
_COPY = ExportPlanAction.COPY


def _out(tmp_path: Path) -> Path:
    """The bots' own files are `*.json` in `tmp_path`; a plan goes in its own folder."""
    folder = tmp_path / "out"
    folder.mkdir()
    return folder


def _screen(open_bots_screen, answers: Answers) -> BotsScreen:
    screen = open_bots_screen(
        [
            stored("a00001", S.RUNNING, name="alpha grid"),
            stored("b00002", S.DRAFT, name="beta grid"),
        ],
        answers,
    )
    screen.settle()
    return screen


def _expected(screen: BotsScreen, **query: object) -> BotPlanDocument:
    document = screen.dispatcher.dispatch(
        ExportBotPlanQuery,
        ExportBotPlanQuery(**query),  # type: ignore[arg-type]
    )
    assert isinstance(document, BotPlanDocument)
    return document


def test_export_plan_is_disabled_without_a_bot_and_says_why(
    open_bots_screen, qtbot
) -> None:
    screen = open_bots_screen([], Answers())
    screen.settle()
    export = screen.actions.action(EXPORT_PLAN)

    assert not export.isEnabled()
    assert "no bot to export" in export.toolTip()

    screen.store.save(stored("a00001", S.DRAFT))
    qtbot.waitUntil(lambda: (screen.settle(), export.isEnabled())[1], timeout=5_000)

    assert "no bot to export" not in export.toolTip()


def test_save_writes_what_bot_export_would_write(
    open_bots_screen, tmp_path: Path
) -> None:
    target = _out(tmp_path) / "plan.json"
    answers = Answers(export_plan=ExportPlanChoice(_ALL, False, _SAVE))
    answers.plan_path = str(target)
    screen = _screen(open_bots_screen, answers)

    screen.actions.action(EXPORT_PLAN).trigger()

    assert target.read_text(encoding="utf-8") == _expected(screen).to_json_text()
    assert any(a.startswith("plan path bot-plan-") for a in answers.asked)
    assert answers.asked[-1].endswith(".json")
    assert not screen.notifier.failures


def test_the_success_message_names_the_file_the_count_and_the_server_commands(
    open_bots_screen, tmp_path: Path
) -> None:
    target = _out(tmp_path) / "plan.json"
    answers = Answers(export_plan=ExportPlanChoice(_ALL, False, _SAVE))
    answers.plan_path = str(target)
    screen = _screen(open_bots_screen, answers)

    screen.actions.action(EXPORT_PLAN).trigger()

    ((headline, detail),) = screen.notifier.events
    assert str(target) in headline and "2 bot(s)" in headline
    assert "bot apply plan.json --dry-run" in detail
    assert detail.rstrip().endswith("bot apply plan.json")
    assert screen.view.model.statusMessage == headline


def test_all_stopped_writes_every_entry_stopped(
    open_bots_screen, tmp_path: Path
) -> None:
    target = _out(tmp_path) / "plan.json"
    answers = Answers(export_plan=ExportPlanChoice(_ALL, True, _SAVE))
    answers.plan_path = str(target)
    screen = _screen(open_bots_screen, answers)
    kept = _expected(screen)
    assert any(b.desired_state is DesiredState.RUNNING for b in kept.bots)

    screen.actions.action(EXPORT_PLAN).trigger()

    assert (
        target.read_text(encoding="utf-8")
        == _expected(screen, all_stopped=True).to_json_text()
    )
    assert '"desired_state": "running"' not in target.read_text(encoding="utf-8")


def test_the_selected_scope_exports_only_the_selected_bot(
    open_bots_screen, tmp_path: Path
) -> None:
    target = _out(tmp_path) / "plan.json"
    answers = Answers(export_plan=ExportPlanChoice(_SELECTED, False, _SAVE))
    answers.plan_path = str(target)
    screen = _screen(open_bots_screen, answers)
    screen.view.model.select_requested.emit("b00002")
    screen.settle()

    screen.actions.action(EXPORT_PLAN).trigger()

    assert (
        target.read_text(encoding="utf-8")
        == _expected(screen, bot_ids=("b00002",)).to_json_text()
    )
    assert "beta grid" in target.read_text(encoding="utf-8")
    assert "alpha grid" not in target.read_text(encoding="utf-8")
    assert "export plan 2 b00002" in answers.asked


def test_an_existing_file_is_refused_by_name_and_left_untouched(
    open_bots_screen, tmp_path: Path
) -> None:
    target = _out(tmp_path) / "plan.json"
    target.write_text("keep me", encoding="utf-8")
    answers = Answers(export_plan=ExportPlanChoice(_ALL, False, _SAVE))
    answers.plan_path = str(target)
    screen = _screen(open_bots_screen, answers)

    screen.actions.action(EXPORT_PLAN).trigger()

    assert target.read_text(encoding="utf-8") == "keep me"
    notice = screen.notifier.last
    assert notice.kind is FailureKind.COMMAND
    assert str(target) in notice.headline and "overwrite" in notice.headline
    assert screen.view.model.statusIsError


def test_a_write_failure_shows_its_reason_and_the_screen_keeps_running(
    open_bots_screen, tmp_path: Path
) -> None:
    target = tmp_path / "no_such_folder" / "plan.json"
    answers = Answers(export_plan=ExportPlanChoice(_ALL, False, _SAVE))
    answers.plan_path = str(target)
    screen = _screen(open_bots_screen, answers)

    screen.actions.action(EXPORT_PLAN).trigger()

    notice = screen.notifier.last
    assert str(target) in notice.headline and notice.detail
    assert screen.actions.action(EXPORT_PLAN).isEnabled()


def test_cancelling_either_question_writes_and_says_nothing(
    open_bots_screen, tmp_path: Path
) -> None:
    out = _out(tmp_path)
    answers = Answers(export_plan=None)
    screen = _screen(open_bots_screen, answers)
    screen.actions.action(EXPORT_PLAN).trigger()
    answers.export_plan = ExportPlanChoice(_ALL, False, _SAVE)
    answers.plan_path = ""

    screen.actions.action(EXPORT_PLAN).trigger()

    assert list(out.iterdir()) == []
    assert not screen.notifier.failures and not screen.notifier.events


def test_copy_json_puts_exactly_the_text_a_save_would_write(
    open_bots_screen, tmp_path: Path
) -> None:
    answers = Answers(export_plan=ExportPlanChoice(_ALL, True, _COPY))
    screen = _screen(open_bots_screen, answers)

    screen.actions.action(EXPORT_PLAN).trigger()

    clipboard = QGuiApplication.clipboard()
    assert clipboard.text() == _expected(screen, all_stopped=True).to_json_text()
    assert not any(a.startswith("plan path") for a in answers.asked)
