"""`BOT-169` — what the Bots screen tells the user when something fails.

Every failure the screen has goes through `INotifier` and none is written into
a widget of its own (`ui-presentation-rule.md` §10): a read that failed is a
message bar at the top of the Bots mode with Retry, a command that failed or
was refused is a message box. The headline is a sentence written here, never an
exception's text; the technical text rides as `detail`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import partial

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills import (
    BotFills,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    ReadKind,
)

#: What the fills panel says in place of the failure, which the message bar carries.
FILLS_PROBLEM = "see the message at the top of the screen"

_READ_HEADLINES = {
    ReadKind.LIST: "The bots could not be read. Retry, or check the venue connection.",
    ReadKind.PLANNER: "The market numbers for this bot could not be read. Retry.",
    ReadKind.FILLS: "The fills of this bot could not be read. Retry.",
}
_FILES_CAUSE = "bots.files.unreadable"
_COMMAND_CAUSE = "bots.command"


def read_cause(kind: ReadKind) -> str:
    return f"bots.read.{kind.value}"


class BotsFailures:
    """@brief Tells the user of the Bots screen's failures, one cause one message."""

    def __init__(
        self,
        notifier: INotifier,
        again: Callable[[ReadKind], None],
        show_fills: Callable[[BotFills], None],
    ) -> None:
        self._notifier = notifier
        self._again = again
        self._show_fills = show_fills

    def read_failed(self, kind: ReadKind, _label: str, detail: str) -> None:
        if kind is ReadKind.FILLS:
            self._show_fills(BotFills(problem=FILLS_PROBLEM))
        self._notifier.report_failure(
            FailureNotice(
                FailureKind.BACKGROUND,
                read_cause(kind),
                _READ_HEADLINES[kind],
                scope=BOTS_ROUTE,
                detail=detail,
                retry=partial(self._again, kind),
            )
        )

    def read_recovered(self, kind: ReadKind) -> None:
        self._notifier.clear_failure(read_cause(kind))

    def files_refused(self, names: Sequence[str]) -> None:
        """Bot files the store could not read; the list is a read's answer, so
        it clears when the next read has none."""
        if not names:
            self._notifier.clear_failure(_FILES_CAUSE)
            return
        self._notifier.report_failure(
            FailureNotice(
                FailureKind.BACKGROUND,
                _FILES_CAUSE,
                "Some bot files could not be read and are not listed. "
                "Check their files in the bots folder.",
                scope=BOTS_ROUTE,
                detail=", ".join(names),
            )
        )

    def command_refused(self, label: str, result: object, detail: str) -> None:
        """A command the user ran did not happen: the domain's refusal carries
        its own authored message; anything else is a failure with `detail`."""
        if isinstance(result, BotCommandResult):
            headline, detail = f"{label}: refused. {result.message}", ""
        else:
            headline = f"{label}: failed. Check the bot and try again."
        self._notifier.report_failure(
            FailureNotice(FailureKind.COMMAND, _COMMAND_CAUSE, headline, detail=detail)
        )
