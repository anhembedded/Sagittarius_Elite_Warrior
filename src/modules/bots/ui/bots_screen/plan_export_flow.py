"""`BOT-176` — Bots → Export plan…: ask, query, write or copy, tell the person.

The bots come from `ExportBotPlanQuery`, the query `bot export` dispatches too, and the
file from `write_new_plan_file`, the writer it calls too, so the desktop and the CLI write
the same text and neither ever overwrites a file. The work is a local read and a write of
a few kilobytes, so it runs on the UI thread and needs no coordinator
(`async-ui-action-rule.md` covers network and long work).

Every failure goes through `INotifier` as one message box with the reason behind
Details…; a success is the status line plus a toast that names the file and the two
commands to run on the server.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
    failure_detail,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.plan_file import (
    PlanFileRefused,
    write_new_plan_file,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    BotPlanDocument,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_export import (
    UnknownBotsError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.export_bot_plan import (
    ExportBotPlanQuery,
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

logger = logging.getLogger("App.Bots.Screen")

_CAUSE = "bots.export_plan"


def suggested_plan_name(now: datetime) -> str:
    """A file name, not a value a person reads, so it is not the formatter's."""
    return f"bot-plan-{now.date().isoformat().replace('-', '')}.json"


def _copy_to_clipboard(text: str) -> None:
    QGuiApplication.clipboard().setText(text)


def _server_commands(file_name: str) -> str:
    return (
        "On the server, check then apply:\n"
        f"  bot apply {file_name} --dry-run\n"
        f"  bot apply {file_name}"
    )


class PlanExport(QObject):
    """@brief Performs Export plan… for the Bots screen."""

    def __init__(
        self,
        model: BotsViewModel,
        commands: ICommandDispatcher,
        dialogs: BotsDialogs,
        notifier: INotifier,
        *,
        clipboard: Callable[[str], None] = _copy_to_clipboard,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        super().__init__(model)
        self._model = model
        self._commands = commands
        self._dialogs = dialogs
        self._notifier = notifier
        self._clipboard = clipboard
        self._now = now
        model.export_plan_requested.connect(self.export_plan)

    def export_plan(self) -> None:
        selected = self._model.selected
        choice = self._dialogs.ask_export_plan(self._model.bots, selected)
        if choice is None:
            return
        document = self._document(choice)
        if document is None:
            return
        if choice.action is ExportPlanAction.COPY:
            self._clipboard(document.to_json_text())
            self._model.set_status(
                f"Copied the plan of {len(document.bots)} bot(s) as JSON.", False
            )
            logger.info("Bots screen: plan of %d bot(s) copied", len(document.bots))
            return
        self._save(document)

    def _document(self, choice: ExportPlanChoice) -> BotPlanDocument | None:
        selected = self._model.selected
        ids = (
            (selected.bot_id,)
            if choice.scope is ExportPlanScope.SELECTED and selected is not None
            else ()
        )
        try:
            return cast(
                BotPlanDocument,
                self._commands.dispatch(
                    ExportBotPlanQuery,
                    ExportBotPlanQuery(ids, all_stopped=choice.all_stopped),
                ),
            )
        except UnknownBotsError as unknown:
            self._fail(
                "The plan was not exported: that bot no longer exists. "
                "Select another bot and try again.",
                failure_detail(unknown),
            )
        return None

    def _save(self, document: BotPlanDocument) -> None:
        chosen = self._dialogs.ask_plan_save_path(suggested_plan_name(self._now()))
        if not chosen:
            return
        target = Path(chosen)
        written = write_new_plan_file(target, document.to_json_text())
        if isinstance(written, PlanFileRefused):
            self._report_refusal(written)
            return
        count = len(document.bots)
        headline = f"Wrote the plan of {count} bot(s) to {target}."
        self._model.set_status(headline, False)
        self._notifier.notify(headline, _server_commands(target.name))
        logger.info("Bots screen: plan of %d bot(s) written to %s", count, target)

    def _report_refusal(self, refused: PlanFileRefused) -> None:
        if refused.reason == "exists":
            self._fail(
                f"{refused.path} already exists, so nothing was written. "
                "Export never overwrites a file; choose a new name.",
                str(refused.path),
            )
        else:
            self._fail(
                f"The plan could not be written to {refused.path}: {refused.detail}.",
                refused.detail,
            )

    def _fail(self, headline: str, detail: str) -> None:
        self._model.set_status(headline, True)
        self._notifier.report_failure(
            FailureNotice(FailureKind.COMMAND, _CAUSE, headline, detail=detail)
        )
        logger.warning("Bots screen: export plan failed: %s", headline)
