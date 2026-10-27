"""`EPIC-048B` - `ExportBotPlanToFileCommand`: the plan document, written to a new file, for the
desktop's Export plan… and `bot export` alike (`BOT-176`).

The text is `ExportBotPlanQuery`'s, the file is never written over, and an id that names no bot
is a refusal checked before the query runs, so the engine's dispatcher never logs it at ERROR.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.plan_file import (
    PlanFileWriter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.export_bot_plan import (
    BotPlanDocument,
    ExportBotPlanQuery,
    ExportBotPlanQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.export_bot_plan_to_file import (
    ExportBotPlanToFileCommand,
    ExportBotPlanToFileCommandHandler,
    PlanFileExported,
    PlanFileNotExported,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    CommandWorld,
    MemoryAppliedPlanStore,
    save_bot,
)


class _App(ICommandDispatcher):
    """Resolves the export query to its handler, every other read to the world's."""

    def __init__(self, world: CommandWorld) -> None:
        self._world = world
        self._export = ExportBotPlanQueryHandler(world, MemoryAppliedPlanStore())
        self.exports: list[ExportBotPlanQuery] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        if handler_class is ExportBotPlanQuery:
            assert isinstance(input_dto, ExportBotPlanQuery)
            self.exports.append(input_dto)
            return self._export.execute(input_dto)
        return self._world.dispatch(handler_class, input_dto)


def _app() -> _App:
    world = CommandWorld()
    save_bot(world.store, "aaaaaa", BotLifecycleState.RUNNING, "one", {"lower": "1"})
    save_bot(world.store, "bbbbbb", BotLifecycleState.STOPPED, "two", {"lower": "3"})
    return _App(world)


def _export(app: _App, command: ExportBotPlanToFileCommand) -> object:
    return ExportBotPlanToFileCommandHandler(app, PlanFileWriter()).execute(command)


def _document(app: _App, query: ExportBotPlanQuery) -> BotPlanDocument:
    document = app.dispatch(ExportBotPlanQuery, query)
    assert isinstance(document, BotPlanDocument)
    return document


def test_the_file_holds_the_export_querys_text_and_the_answer_counts_its_bots(
    tmp_path: Path,
) -> None:
    app = _app()
    target = tmp_path / "plan.json"

    answer = _export(app, ExportBotPlanToFileCommand(target, all_stopped=True))

    assert answer == PlanFileExported(target, 2)
    expected = _document(app, ExportBotPlanQuery((), all_stopped=True))
    assert target.read_text(encoding="utf-8") == expected.to_json_text()


def test_only_the_named_bot_is_written(tmp_path: Path) -> None:
    app = _app()
    target = tmp_path / "plan.json"

    answer = _export(app, ExportBotPlanToFileCommand(target, ("bbbbbb",)))

    assert answer == PlanFileExported(target, 1)
    assert '"two"' in target.read_text(encoding="utf-8")
    assert '"one"' not in target.read_text(encoding="utf-8")


def test_an_existing_file_is_refused_and_left_untouched(tmp_path: Path) -> None:
    target = tmp_path / "plan.json"
    target.write_text("keep me", encoding="utf-8")

    answer = _export(_app(), ExportBotPlanToFileCommand(target))

    assert answer == PlanFileNotExported(target, "exists")
    assert target.read_text(encoding="utf-8") == "keep me"


def test_an_unknown_id_is_refused_before_the_export_query_runs(tmp_path: Path) -> None:
    app = _app()
    target = tmp_path / "plan.json"

    answer = _export(app, ExportBotPlanToFileCommand(target, ("zzzzzz",)))

    assert isinstance(answer, PlanFileNotExported)
    assert answer.reason == "unknown_bots" and "zzzzzz" in answer.detail
    assert app.exports == []
    assert not target.exists()
