"""`BOT-176` - Copy JSON puts on the clipboard exactly the text Save… writes, through a clipboard double."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.plan_file import PlanFileWriter
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.export_bot_plan import (
    ExportBotPlanQuery,
    ExportBotPlanQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.export_bot_plan_to_file import (
    ExportBotPlanToFileCommand,
    ExportBotPlanToFileCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_dialogs import (
    BotsDialogs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.export_plan_dialog import (
    ExportPlanAction,
    ExportPlanChoice,
    ExportPlanScope,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    BotQueries,
    FencedReads,
    ReadKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_export_flow import (
    PlanExport,
    suggested_plan_name,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    CommandWorld,
    MemoryAppliedPlanStore,
    save_bot,
)

from .bots_answers import Answers
from .bots_screen_fixtures import HeldPool


class _Dispatcher(ICommandDispatcher):
    """The app's dispatcher resolves the query and the command to their handlers over the same
    store, and the bots list to the world's own."""

    def __init__(self, world: CommandWorld) -> None:
        self._world = world
        self._handler = ExportBotPlanQueryHandler(world, MemoryAppliedPlanStore())
        self._to_file = ExportBotPlanToFileCommandHandler(self, PlanFileWriter())

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        if handler_class is ListBotsQuery:
            return self._world.dispatch(handler_class, input_dto)
        if handler_class is ExportBotPlanToFileCommand:
            assert isinstance(input_dto, ExportBotPlanToFileCommand)
            return self._to_file.execute(input_dto)
        assert handler_class is ExportBotPlanQuery
        assert isinstance(input_dto, ExportBotPlanQuery)
        return self._handler.execute(input_dto)


def _flow(
    model: BotsViewModel,
    world: CommandWorld,
    dialogs: BotsDialogs,
    notifier: RecordingNotifier | None = None,
    **kwargs: Any,
) -> tuple[PlanExport, HeldPool]:
    """The flow over the screen's own fenced reads, on a pool the test runs."""
    pool = HeldPool()
    reads = FencedReads(pool, {kind: ActionOwnershipTracker() for kind in ReadKind})
    queries = BotQueries(_Dispatcher(world), reads, lambda: model.selected)
    told = notifier or RecordingNotifier()
    return PlanExport(model, queries, dialogs, told, **kwargs), pool


def test_copy_json_equals_the_saved_text(qapp, tmp_path: Path) -> None:
    world = CommandWorld()
    save_bot(world.store, "aaaaaa", BotLifecycleState.RUNNING, "one", {"lower": "1"})
    answers = Answers()
    clipboard: list[str] = []
    flow, pool = _flow(
        BotsViewModel(), world, answers.dialogs(), clipboard=clipboard.append
    )

    answers.export_plan = ExportPlanChoice(
        ExportPlanScope.ALL, False, ExportPlanAction.COPY
    )
    flow.export_plan()
    pool.run_all()
    saved = tmp_path / "plan.json"
    answers.plan_path = str(saved)
    answers.export_plan = ExportPlanChoice(
        ExportPlanScope.ALL, False, ExportPlanAction.SAVE
    )
    flow.export_plan()
    pool.run_all()

    assert len(clipboard) == 1
    assert clipboard[0] == saved.read_text(encoding="utf-8")


def test_the_suggested_name_is_the_day(qapp) -> None:
    assert suggested_plan_name(datetime(2026, 10, 14, 23, 59, tzinfo=UTC)) == (
        "bot-plan-20261014.json"
    )


@pytest.mark.parametrize("action", [ExportPlanAction.SAVE, ExportPlanAction.COPY])
def test_a_selection_that_vanishes_while_the_dialog_is_open_fails_and_never_widens_the_scope(
    qapp, tmp_path: Path, action: ExportPlanAction
) -> None:
    """The dialog is modal but the event loop runs: a list refresh can clear the selection
    before it returns. *Selected bot* then names a bot that is gone; it must not become every
    bot, one of which is a running mainnet bot the person never chose."""
    world = CommandWorld()
    save_bot(world.store, "aaaaaa", BotLifecycleState.STOPPED, "testnet one")
    save_bot(
        world.store,
        "bbbbbb",
        BotLifecycleState.RUNNING,
        "mainnet two",
        venue=TradingVenue.SPOT_MAINNET,
    )
    listing = world.dispatch(ListBotsQuery, ListBotsQuery())
    model = BotsViewModel()
    model.set_bots(listing.bots)
    model.set_selected(next(b for b in listing.bots if b.bot_id == "aaaaaa"))
    # The bot the dialog was opened on is deleted while it is open.
    world.store.delete(BotId("aaaaaa"))
    answers = Answers(
        export_plan=ExportPlanChoice(ExportPlanScope.SELECTED, False, action)
    )
    target = tmp_path / "plan.json"
    answers.plan_path = str(target)
    dialogs = replace(
        answers.dialogs(),
        ask_export_plan=lambda bots, selected: (
            model.set_selected(None) or answers.export_plan
        ),
    )
    notifier = RecordingNotifier()
    clipboard: list[str] = []
    flow, pool = _flow(model, world, dialogs, notifier, clipboard=clipboard.append)

    flow.export_plan()
    pool.run_all()

    assert not target.exists() and clipboard == []
    assert "no longer exists" in notifier.last.headline


def test_the_plan_is_read_and_written_off_the_ui_thread(qapp, tmp_path: Path) -> None:
    """`EPIC-048B`: the dialogs are asked on the UI thread, then the command runs on the pool,
    and only its answer tells. A second export waits for the first: the answer of a written
    file is never superseded and left untold."""
    world = CommandWorld()
    save_bot(world.store, "aaaaaa", BotLifecycleState.RUNNING, "one", {"lower": "1"})
    target = tmp_path / "plan.json"
    answers = Answers(
        export_plan=ExportPlanChoice(ExportPlanScope.ALL, False, ExportPlanAction.SAVE),
        plan_path=str(target),
    )
    notifier = RecordingNotifier()
    clipboard: list[str] = []
    flow, pool = _flow(
        BotsViewModel(), world, answers.dialogs(), notifier, clipboard=clipboard.append
    )

    flow.export_plan()
    answers.export_plan = ExportPlanChoice(
        ExportPlanScope.ALL, False, ExportPlanAction.COPY
    )
    flow.export_plan()

    assert len(pool.pending) == 1
    assert not target.exists() and notifier.events == []

    pool.run_all()

    assert target.exists() and len(notifier.events) == 1
    flow.export_plan()
    pool.run_all()
    assert clipboard == [target.read_text(encoding="utf-8")]
