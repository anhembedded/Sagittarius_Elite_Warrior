"""`BOT-169` — what the Bots screen tells the user when something fails.

Every failure the screen has goes through `INotifier` and none is written into
a widget of its own (`ui-presentation-rule.md` §10): a read that failed is a
message bar at the top of the Bots mode with Retry, a command that failed or
was refused is a message box. The headline is a sentence written here, never an
exception's text; the technical text rides as `detail`.

**One cause is one message** (`BUG-181`): a read of a venue's account that the
venue refuses (the fills, with the key refused) is the cause the Connect step
already tells in its own bar, so it raises no bar here; it is handed to the
Connect step, and the fills panel says only that they were not read.
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
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.connect_failure_words import (
    state_words,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
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
        venue_refused: Callable[[ConnectFailure], None],
    ) -> None:
        self._notifier = notifier
        self._again = again
        self._show_fills = show_fills
        self._venue_refused = venue_refused

    def fills_answered(self, fills: BotFills) -> None:
        """Shows the fills; a read the venue refused is the Connect step's to
        tell, and the panel says only what it is."""
        refusal = fills.refused
        if refusal is None:
            self._show_fills(fills)
            return
        self._venue_refused(refusal)
        self._show_fills(BotFills(problem=f"not read: {state_words(refusal)}"))

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
