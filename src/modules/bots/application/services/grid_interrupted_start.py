"""`EPIC-035C` (H6), `BUG-190` — the cancel a cut-short start owes.

A bot saved while STARTING may have laid part of its ladder (and bought part of
its opening) before the app closed. The restart rule makes it HALTED
(`app_restart`) and, since `EPIC-035C`, writes `START_INTERRUPTED` on it: the
debt is on the bot's own record, so a crash before it is paid does not lose it.

This pays it: cancel every order carrying the bot's tag, then say what
happened. It runs at boot (when the exchange lets it) and again whenever
trading is enabled, until paid:

  · **Paid** → `START_INTERRUPTED_CLEARED`, naming the count cancelled.
  · **The order session is closed** (the usual state at boot; cancels are
    refused then) → stays owed, saying how many tagged orders still rest and
    that they are cancelled when trading is enabled.
  · **A cancel refused or failed** → stays owed, saying so and that orders may
    still rest. Never reported as a clean halt.

A start (or a confirmed resume) refused because trading went off owes the same
cancel (`START_CUT_BY_SWITCH_OFF`): the session is closed, so its partial
ladder cannot be taken off then, and unlike a finished ladder it belongs to a
plan that never completed. Only the lead of the sentence differs.

Resuming or stopping the bot cancels its tagged orders too (`GridResumeSequence`,
`GridStopSequence`), so the user is never forced to wait for this.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_order_gateway import (
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_housekeeping import (
    CancelReport,
    GridHousekeeping,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

logger = logging.getLogger("App.Bots.GridExecutor")

#: What the restart writes on a bot whose start it cut short.
START_INTERRUPTED_DETAIL = (
    "the app closed while this bot was starting; its tagged orders may still "
    "rest and are cancelled when trading is enabled"
)
#: What cut the start short, per reason that owes the cancel; the lead of every
#: sentence this class says. Also the set of reasons that owe it.
_LEAD: dict[GridReason, str] = {
    GridReason.START_INTERRUPTED: "the app closed while this bot was starting",
    GridReason.START_CUT_BY_SWITCH_OFF: "trading went off while this bot was starting",
}
OWING_REASONS: frozenset[GridReason] = frozenset(_LEAD)


class GridInterruptedStart:
    """Pays a cut-short start's debt of cancelled orders."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context
        self._housekeeping = GridHousekeeping(context)

    def owed(self) -> bool:
        state = self._context.state
        return (
            state.state is BotLifecycleState.HALTED
            and state.runtime.reason in OWING_REASONS
        )

    def run(self) -> None:
        """Pay the debt if the bot owes it; say where it stands either way."""
        if not self.owed():
            return
        try:
            self._pay()
        except Exception as error:  # converted to a reason at this seam
            logger.warning(
                "Bot %s: the interrupted start could not be cleaned",
                self._context.state.bot_id,
                exc_info=True,
            )
            self._say(
                self._reason(),
                f"{self._lead()}; the exchange could not be read ({type(error).__name__}); "
                "its tagged orders are cancelled when trading is enabled",
            )

    def _pay(self) -> None:
        # A cancel needs no owner budget (only an order does), so none is
        # registered: the debt is not blocked by a budget refusal, and a HALTED
        # bot is not left holding one.
        report = self._housekeeping.cancel_tagged()
        failed = report.failed
        if failed is None:
            self._cleared(report.cancelled)
        elif failed.kind is OrderOutcomeKind.SWITCH_OFF:
            self._waiting_for_trading(report.remaining)
        else:
            self._still_rest(report)

    def _cleared(self, cancelled: int) -> None:
        what = (
            f"cancelled {cancelled} tagged order(s)"
            if cancelled
            else "no tagged order was resting"
        )
        self._say(
            GridReason.START_INTERRUPTED_CLEARED,
            f"{self._lead()}; {what}. Resume to lay a fresh ladder, or Stop",
        )
        logger.info("Bot %s: interrupted start — %s", self._context.state.bot_id, what)

    def _waiting_for_trading(self, resting: int) -> None:
        if resting == 0:
            self._cleared(0)
            return
        self._say(
            self._reason(),
            f"{self._lead()}; {resting} tagged order(s) still rest and are cancelled "
            "when trading is enabled",
        )

    def _still_rest(self, report: CancelReport) -> None:
        failed = report.failed
        verb = (
            "failed" if failed and failed.kind is OrderOutcomeKind.FAULT else "refused"
        )
        detail = failed.detail if failed else ""
        self._say(
            self._reason(),
            f"{self._lead()}; cancel {report.client_order_id} {verb}: {detail}; "
            f"{report.remaining} tagged order(s) may still rest",
        )

    def _reason(self) -> GridReason:
        """The reason that owes the cancel, kept while it is owed."""
        reason = self._context.state.runtime.reason
        if reason not in OWING_REASONS:
            raise ValueError(f"no cancel is owed under {reason}")
        return reason

    def _lead(self) -> str:
        return _LEAD[self._reason()]

    def _say(self, reason: GridReason, detail: str) -> None:
        state = self._context.state
        state.update(state.runtime.with_reason(reason, detail))
