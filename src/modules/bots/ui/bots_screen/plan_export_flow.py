"""`BOT-176` — Bots → Export plan…: ask, query, write or copy, tell the person.

The bots come from `ExportBotPlanQuery`, the query `bot export` dispatches too, and the file is
written by `ExportBotPlanToFileCommand`, the command it dispatches too, so the desktop and the CLI
write the same text and neither ever overwrites a file. Both run off the UI thread, as a fenced
read of their own (`ReadKind.EXPORT`, `EPIC-048B`): the screen holds no adapter and touches no
file, so a backend that is not this machine can stand behind it. The dialogs are asked first, on
the UI thread; the answer is what continues the flow.

Every failure goes through `INotifier` as one message box with the reason behind
Details…; a success is the status line plus a toast that names the file and the two
commands to run on the server.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
    failure_detail,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.export_bot_plan import (
    BotPlanDocument,
    UnknownBotsError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.export_bot_plan_to_file import (
    ExportBotPlanToFileCommand,
    PlanFileExported,
    PlanFileNotExported,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_dialogs import (
    BotsDialogs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.export_plan_dialog import (
    ExportPlanAction,
    ExportPlanScope,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    BotQueries,
    ReadKind,
)

logger = logging.getLogger("App.Bots.Screen")

_CAUSE = "bots.export_plan"
_GONE = (
    "The plan was not exported: that bot no longer exists. "
    "Select another bot and try again."
)


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
        queries: BotQueries,
        dialogs: BotsDialogs,
        notifier: INotifier,
        *,
        clipboard: Callable[[str], None] = _copy_to_clipboard,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        super().__init__(model)
        self._model = model
        self._queries = queries
        self._dialogs = dialogs
        self._notifier = notifier
        self._clipboard = clipboard
        self._now = now
        #: An export sent and not yet answered: a second one waits for it, so no answer of a
        #: written file is ever superseded and left untold.
        self._in_flight = False
        model.export_plan_requested.connect(self.export_plan)
        queries.reads.answered.connect(self._on_export_answered)
        queries.reads.failed.connect(self._on_export_failed)

    def export_plan(self) -> None:
        """Asks what to export and where, then sends the work off the UI thread.

        `selected` is the bot the dialog was opened on: the screen's selection can change while
        it is open, and a vanished bot must fail, never widen the scope."""
        if self._in_flight:
            logger.debug("Bots screen: export plan asked while one is running; ignored")
            return
        selected = self._model.selected
        choice = self._dialogs.ask_export_plan(self._model.bots, selected)
        if choice is None:
            return
        if choice.scope is ExportPlanScope.SELECTED and selected is None:
            self._fail(_GONE, "no bot was selected")
            return
        ids = (
            (selected.bot_id,)
            if choice.scope is ExportPlanScope.SELECTED and selected is not None
            else ()
        )
        if choice.action is ExportPlanAction.COPY:
            self._in_flight = True
            self._queries.plan_document(ids, all_stopped=choice.all_stopped)
            return
        chosen = self._dialogs.ask_plan_save_path(suggested_plan_name(self._now()))
        if chosen:
            self._in_flight = True
            self._queries.plan_file(
                ExportBotPlanToFileCommand(
                    Path(chosen), ids, all_stopped=choice.all_stopped
                )
            )

    def _on_export_answered(self, kind: ReadKind, _label: str, answer: object) -> None:
        if kind is not ReadKind.EXPORT:
            return
        self._in_flight = False
        if isinstance(answer, UnknownBotsError):
            self._fail(_GONE, failure_detail(answer))
        elif isinstance(answer, BotPlanDocument):
            self._copied(answer)
        elif isinstance(answer, PlanFileExported):
            self._written(answer)
        elif isinstance(answer, PlanFileNotExported):
            self._not_written(answer)
        else:
            raise TypeError(
                f"an Export plan read answers a plan or its file, not {type(answer).__name__}"
            )

    def _on_export_failed(self, kind: ReadKind, _label: str, detail: str) -> None:
        if kind is ReadKind.EXPORT:
            self._in_flight = False
            self._fail("The plan was not exported. Try again.", detail)

    def _copied(self, document: BotPlanDocument) -> None:
        self._clipboard(document.to_json_text())
        self._model.set_status(
            f"Copied the plan of {len(document.bots)} bot(s) as JSON.", False
        )
        logger.info("Bots screen: plan of %d bot(s) copied", len(document.bots))

    def _written(self, exported: PlanFileExported) -> None:
        headline = f"Wrote the plan of {exported.bot_count} bot(s) to {exported.path}."
        self._model.set_status(headline, False)
        self._notifier.notify(headline, _server_commands(exported.path.name))
        logger.info(
            "Bots screen: plan of %d bot(s) written to %s",
            exported.bot_count,
            exported.path,
        )

    def _not_written(self, refused: PlanFileNotExported) -> None:
        if refused.reason == "unknown_bots":
            self._fail(_GONE, refused.detail)
        elif refused.reason == "exists":
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
