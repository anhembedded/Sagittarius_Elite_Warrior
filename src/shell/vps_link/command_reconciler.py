"""`EPIC-047E` (AC6) — settles the commands the link lost, from what the host recorded, and never sends one again.

@details A command whose answer was lost with the link sits in the `UnansweredLedger`, and its bot is blocked for the next
command (the one-press-twice guarantee). After a reconnect this asks the host, read-only (`LinkHostControl.outcome_of`, the
bridge's `outcome` call), what it recorded for each request id:

  · a settled outcome (done, refused, rejected) → the entry leaves the ledger and the person is told, in the host's words,
    that it ran or was refused;
  · nothing recorded yet (the file still waits, or the host took it and has not written the outcome) → the entry stays and
    the bot stays blocked; it is asked again;
  · the host never saw the id → the command never reached it: the entry leaves the ledger and the person is told nothing
    happened and that they may send it again if they still want it. **It is not sent again by this class**: a lost
    Start, Edit, Add or Resume must not run minutes later without a fresh answer to the real-money question (decision of
    2026-10-28, `EPIC-047E` PR 3). Any re-send is a new action of the person, with a new request id.

A link that is lost again, or a build whose bridge has no `outcome` call, leaves the ledger as it was and says so once.

@par Extension cases
  · telling the person somewhere else than the toast (a line in the Output pane) - another `notify` callable.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlReply,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.link_host_control import (
    LinkHostControl,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.unanswered_ledger import (
    UnansweredCommand,
    UnansweredLedger,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_errors import (
    CallFailedError,
    CallTimedOutError,
    LinkLostError,
)

logger = logging.getLogger("App.VpsTab")

_SETTLED = frozenset(
    {HostControlStatus.DONE, HostControlStatus.REFUSED, HostControlStatus.REJECTED}
)
_UNCHECKABLE = (
    "A command lost with the link could not be checked against the host's record: {why}. "
    "Its bot stays blocked; check `bot show` on the host."
)


def what_it_was(entry: UnansweredCommand) -> str:
    return f"{entry.request.action.value} on {entry.request.bot_id}"


def ran_words(entry: UnansweredCommand, reply: HostControlReply) -> str:
    verdict = "ran" if reply.status is HostControlStatus.DONE else "did not run"
    return f"The command lost with the link, {what_it_was(entry)}, {verdict} on the host: {reply.message}"


def never_reached_words(entry: UnansweredCommand) -> str:
    return (
        f"The command lost with the link, {what_it_was(entry)}, never reached the host: nothing happened. "
        "Send it again if you still want it."
    )


class CommandReconciler:
    def __init__(
        self,
        ledger: UnansweredLedger,
        control: LinkHostControl,
        notify: Callable[[str], None],
    ) -> None:
        self._ledger = ledger
        self._control = control
        self._notify = notify

    def reconcile(self) -> int:
        """One pass over the ledger; the number of commands still unsettled (asked again later)."""
        for entry in self._ledger.entries():
            try:
                reply = self._control.outcome_of(entry.request_id)
            except (LinkLostError, CallTimedOutError, CallFailedError) as failure:
                logger.warning(
                    "[vps-command] reconcile of request %s stopped: %s",
                    entry.request_id,
                    failure,
                )
                self._notify(_UNCHECKABLE.format(why=failure))
                return len(self._ledger.entries())
            self._settle(entry, reply)
        return len(self._ledger.entries())

    def _settle(self, entry: UnansweredCommand, reply: HostControlReply | None) -> None:
        if reply is None:
            self._ledger.settle(entry.request_id)
            logger.info(
                "[vps-command] request %s (%s) never reached the host; not sent again",
                entry.request_id,
                what_it_was(entry),
            )
            self._notify(never_reached_words(entry))
        elif reply.status in _SETTLED:
            self._ledger.settle(entry.request_id)
            logger.info(
                "[vps-command] request %s (%s) settled on the host: %s",
                entry.request_id,
                what_it_was(entry),
                reply.status.value,
            )
            self._notify(ran_words(entry, reply))
        else:
            logger.info(
                "[vps-command] request %s (%s) has no recorded outcome yet: %s",
                entry.request_id,
                what_it_was(entry),
                reply.message,
            )
