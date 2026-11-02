"""`EPIC-047E` — Bots → Add to VPS…: ask, send the bot to the host off the UI thread, tell the host's answer.

The question is asked on the UI thread; the send is a fenced read of its own (`ReadKind.ADD_TO_VPS`), because the host
may take seconds to answer and the screen never waits on the link. The bot is named by its id when the dialog opened: a
selection that changes while the question is open cannot send another bot.

The answer is the host's, in its words. A reply that never came is told as "may or may not have been created" and never as
a failure, because the host may have created it; nothing is sent again by this flow. The result is one status line, plus a
toast on success so it is seen while the person looks at another tab.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.add_bot_to_vps import (
    AddedToVps,
    NotAddedToVps,
)

from .bots_dialogs import BotsDialogs
from .bots_view_model import BotsViewModel
from .fenced_reads import BotQueries, ReadKind

logger = logging.getLogger("App.Bots.Screen")

_CAUSE = "bots.add_to_vps"
UNKNOWN_WORDS = (
    "The VPS host did not answer in time, so {name} may or may not have been created there. "
    "Read the VPS Bots tab before sending it again."
)


class AddToVps(QObject):
    """@brief Performs Add to VPS… for the Bots screen."""

    def __init__(
        self,
        model: BotsViewModel,
        queries: BotQueries,
        dialogs: BotsDialogs,
        notifier: INotifier,
    ) -> None:
        super().__init__(model)
        self._model = model
        self._queries = queries
        self._dialogs = dialogs
        self._notifier = notifier
        #: A send not yet answered: a second asks for nothing, so no bot is sent twice by two presses.
        self._in_flight = False
        model.add_to_vps_requested.connect(self.add_to_vps)
        queries.reads.answered.connect(self._on_add_answered)
        queries.reads.failed.connect(self._on_add_failed)

    def add_to_vps(self) -> None:
        bot = self._model.selected
        if bot is None or self._in_flight:
            logger.debug("Bots screen: add to VPS asked with no bot or one running")
            return
        if self._model.add_to_vps_unavailable:
            return
        if not self._dialogs.confirm_add_to_vps(bot):
            return
        self._in_flight = True
        self._model.set_status(f"Sending {bot.name} to the VPS host…", False)
        logger.info("[add-to-vps] sending bot %s", bot.bot_id)
        self._queries.add_to_vps(bot)

    def _on_add_answered(self, kind: ReadKind, _label: str, answer: object) -> None:
        if kind is not ReadKind.ADD_TO_VPS:
            return
        self._in_flight = False
        if isinstance(answer, AddedToVps):
            headline = f"Added {answer.bot_name} to the VPS host as a DRAFT."
            self._model.set_status(headline, False)
            self._notifier.notify(headline, answer.message)
            logger.info("[add-to-vps] host created bot %s", answer.host_bot_id)
        elif isinstance(answer, NotAddedToVps):
            words = (
                UNKNOWN_WORDS.format(name=answer.bot_name)
                if answer.unknown
                else f"{answer.bot_name} was not added to the VPS host. {answer.message}"
            )
            self._fail(words, answer.message)
        else:
            raise TypeError(
                f"an Add to VPS read answers its result, not {type(answer).__name__}"
            )

    def _on_add_failed(self, kind: ReadKind, _label: str, detail: str) -> None:
        if kind is ReadKind.ADD_TO_VPS:
            self._in_flight = False
            self._fail(
                "The bot was not added to the VPS host, and it may not have reached it. Try again.",
                detail,
            )

    def _fail(self, headline: str, detail: str) -> None:
        self._model.set_status(headline, True)
        self._notifier.report_failure(
            FailureNotice(FailureKind.COMMAND, _CAUSE, headline, detail=detail)
        )
        logger.warning("[add-to-vps] %s", headline)
