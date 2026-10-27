"""`BOT-176` - Bots → Export plan… on the composed app: the file it writes applies as "no changes".

The Bots screen is built on the booted app's container (its real dispatcher, stores and
`ExportBotPlanQuery` binding), the command is triggered as a person would, and the file
the dialogs' answers choose is parsed and previewed by the `PlanApplier` that `bot apply
--dry-run` uses. Nothing reaches a real exchange.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_parser import (
    parse_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_applier import (
    PlanApplier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_differ import (
    PrunePolicy,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_applied_plan_store import (
    IAppliedPlanStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    EXPORT_PLAN,
    bots_commands,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_dialogs import (
    BotsDialogs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_presenter import (
    BotsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BotsView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.export_plan_dialog import (
    ExportPlanAction,
    ExportPlanChoice,
    ExportPlanScope,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions

from .grid_fake_exchange import GRID, SPOT, SYMBOL, FakeExchange, booted

_WAIT_MS = 10_000


def test_a_plan_exported_from_the_screen_applies_as_no_changes(
    exchange: FakeExchange, qtbot: Any, tmp_path: Path
) -> None:
    target = tmp_path / "exported-plan.json"
    with booted(exchange) as app:
        container = app.engine.context.container
        dispatcher = container.resolve(ICommandDispatcher)
        for name in ("alpha", "beta"):
            dispatcher.dispatch(
                CreateBotCommand, CreateBotCommand(name, "grid", SPOT, SYMBOL, GRID)
            )
        view = BotsView()
        qtbot.addWidget(view)
        presenter = BotsPresenter(
            view,
            container,
            dialogs=BotsDialogs(
                ask_new_bot=lambda _kinds, _venues: None,
                ask_stop=lambda _bot: None,
                confirm_delete=lambda _bot: False,
                ask_arm_strategy=lambda _question: None,
                choose_venue=lambda _choice: None,
                allow_real_money=lambda _venue, _what: True,
                ask_export_plan=lambda _bots, _selected: ExportPlanChoice(
                    ExportPlanScope.ALL, False, ExportPlanAction.SAVE
                ),
                ask_plan_save_path=lambda _suggested: str(target),
            ),
        )
        try:
            actions = bound_actions(
                view, bots_commands(BOTS_ROUTE), presenter.bind_commands
            )
            export = actions.action(EXPORT_PLAN)
            qtbot.waitUntil(export.isEnabled, timeout=_WAIT_MS)

            export.trigger()
            # The file is written off the UI thread (`EPIC-048B`); the status line says when.
            qtbot.waitUntil(
                lambda: "Wrote the plan" in view.model.statusMessage, timeout=_WAIT_MS
            )

            document = parse_plan(
                target.read_text(encoding="utf-8"), container.resolve(IBotKindCatalog)
            )
            assert {bot.name for bot in document.bots} == {"alpha", "beta"}
            preview = PlanApplier(
                dispatcher, container.resolve(IAppliedPlanStore)
            ).preview(document, PrunePolicy.PRUNE)
            assert not preview.diff.has_changes, preview.diff
        finally:
            presenter.dispose()
