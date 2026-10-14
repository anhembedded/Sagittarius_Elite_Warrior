"""`BOT-176` - Copy JSON puts on the clipboard exactly the text Save… writes, through a clipboard double."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.export_bot_plan import (
    ExportBotPlanQuery,
    ExportBotPlanQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.export_plan_dialog import (
    ExportPlanAction,
    ExportPlanChoice,
    ExportPlanScope,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_export_flow import (
    PlanExport,
    suggested_plan_name,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    CommandWorld,
    MemoryAppliedPlanStore,
    save_bot,
)

from .bots_answers import Answers


class _Dispatcher(ICommandDispatcher):
    """The app's dispatcher resolves the query to its handler over the same store."""

    def __init__(self, world: CommandWorld) -> None:
        self._handler = ExportBotPlanQueryHandler(world, MemoryAppliedPlanStore())

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        assert handler_class is ExportBotPlanQuery
        assert isinstance(input_dto, ExportBotPlanQuery)
        return self._handler.execute(input_dto)


def test_copy_json_equals_the_saved_text(qapp, tmp_path: Path) -> None:
    world = CommandWorld()
    save_bot(world.store, "aaaaaa", BotLifecycleState.RUNNING, "one", {"lower": "1"})
    answers = Answers()
    clipboard: list[str] = []
    flow = PlanExport(
        BotsViewModel(),
        _Dispatcher(world),
        answers.dialogs(),
        RecordingNotifier(),
        clipboard=clipboard.append,
    )

    answers.export_plan = ExportPlanChoice(
        ExportPlanScope.ALL, False, ExportPlanAction.COPY
    )
    flow.export_plan()
    saved = tmp_path / "plan.json"
    answers.plan_path = str(saved)
    answers.export_plan = ExportPlanChoice(
        ExportPlanScope.ALL, False, ExportPlanAction.SAVE
    )
    flow.export_plan()

    assert len(clipboard) == 1
    assert clipboard[0] == saved.read_text(encoding="utf-8")


def test_the_suggested_name_is_the_day(qapp) -> None:
    assert suggested_plan_name(datetime(2026, 10, 14, 23, 59, tzinfo=UTC)) == (
        "bot-plan-20261014.json"
    )


def test_a_selection_that_vanishes_while_the_dialog_is_open_fails_and_never_widens_the_scope(
    qapp, tmp_path: Path
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
        export_plan=ExportPlanChoice(
            ExportPlanScope.SELECTED, False, ExportPlanAction.SAVE
        )
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
    flow = PlanExport(model, _Dispatcher(world), dialogs, notifier)

    flow.export_plan()

    assert not target.exists()
    assert "no longer exists" in notifier.last.headline
