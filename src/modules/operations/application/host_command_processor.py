"""What the host does with the commands waiting for it (`EPIC-038J`, decision O4, channel A).

`poll()` takes what the inbox offers, oldest first, and for each file decides, in this order:

  1. **unauthorised** - the door refused it (the file is not owner-only, not the service
     account's...): audited, never read;
  2. **malformed** - not exactly a `sew.host-command/1` document;
  3. **replayed** - its id is already in the audit, so it is not run again;
  4. **expired** - written more than `COMMAND_MAX_AGE_S` ago or more than `COMMAND_MAX_SKEW_S`
     ahead of this host's clock: a file that sat while the host was down does not run later,
     out of context;
  5. otherwise **received** is audited *before* the dispatch and the verdict after it. A host
     that dies between the two finds the id on its next boot and refuses the file as a replay:
     a command takes effect at most once, never twice.

Whatever the verdict, the file is discarded so it is not judged again. A command whose audit
line cannot be written is not executed: an action nobody can account for does not happen.

The executor is the application's own command path (`BotHostCommandExecutor`); this class knows
no bot, no venue and no file.

@par Threads
`poll()` runs on the scheduler's thread, one call at a time (a job does not overlap itself).
"""

from __future__ import annotations

import logging
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.operations.application.host_command_codec import (
    MalformedDocument,
    parse_command,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_command import (
    COMMAND_MAX_AGE_S,
    COMMAND_MAX_SKEW_S,
    ControlAuditEntry,
    ControlVerdict,
    HostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_command_executor import (
    IHostCommandExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_command_inbox import (
    IHostCommandInbox,
    InboxEntry,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_control_audit import (
    IHostControlAudit,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)

logger = logging.getLogger("App.Operations.Control")


class HostCommandProcessor:
    def __init__(
        self,
        inbox: IHostCommandInbox,
        audit: IHostControlAudit,
        executor: IHostCommandExecutor,
        clock: IOperationsClock,
    ) -> None:
        self._inbox = inbox
        self._audit = audit
        self._executor = executor
        self._clock = clock

    def poll(self) -> None:
        for entry in self._inbox.collect():
            try:
                self._handle(entry)
            except Exception:
                logger.exception("[control] %s could not be handled", entry.name)
            finally:
                self._inbox.discard(entry)

    def _handle(self, entry: InboxEntry) -> None:
        stem = entry.name.removeprefix("cmd-").removesuffix(".json")
        if not entry.authorised:
            self._refuse(stem, ControlVerdict.UNAUTHORISED, entry.problem)
            return
        parsed = parse_command(entry.text)
        if isinstance(parsed, MalformedDocument):
            self._refuse(
                parsed.command_id or stem, ControlVerdict.MALFORMED, parsed.reason
            )
            return
        if self._audit.has_seen(parsed.command_id):
            self._refuse(
                parsed.command_id,
                ControlVerdict.REPLAYED,
                "this command id was already seen",
                parsed,
            )
            return
        stale = self._staleness_of(parsed.issued_at)
        if stale:
            self._refuse(parsed.command_id, ControlVerdict.EXPIRED, stale, parsed)
            return
        self._run(parsed)

    def _staleness_of(self, issued_at: datetime) -> str:
        age_s = (self._clock.now() - issued_at).total_seconds()
        if age_s > COMMAND_MAX_AGE_S:
            return (
                f"it was written {age_s:.0f} s ago (the limit is {COMMAND_MAX_AGE_S} s)"
            )
        if -age_s > COMMAND_MAX_SKEW_S:
            return f"it is dated {-age_s:.0f} s in the future (the limit is {COMMAND_MAX_SKEW_S} s)"
        return ""

    def _run(self, command: HostCommand) -> None:
        if not self._record(command.command_id, ControlVerdict.RECEIVED, "", command):
            logger.error(
                "[control] command %s was not run: its audit line could not be written",
                command.command_id,
            )
            return
        try:
            outcome = self._executor.execute(command)
        except Exception as failure:
            logger.exception("[control] command %s failed", command.command_id)
            self._record(
                command.command_id,
                ControlVerdict.FAILED,
                type(failure).__name__,
                command,
            )
            return
        verdict = (
            ControlVerdict.EXECUTED if outcome.accepted else ControlVerdict.REFUSED
        )
        logger.info(
            "[control] command %s: %s on %s -> %s (%s)",
            command.command_id,
            command.action.value,
            command.bot_id,
            verdict.value,
            outcome.message,
        )
        self._record(command.command_id, verdict, outcome.message, command)

    def _refuse(
        self,
        command_id: str,
        verdict: ControlVerdict,
        reason: str,
        command: HostCommand | None = None,
    ) -> None:
        logger.warning(
            "[control] command %s refused (%s): %s", command_id, verdict.value, reason
        )
        self._record(command_id, verdict, reason, command)

    def _record(
        self,
        command_id: str,
        verdict: ControlVerdict,
        message: str,
        command: HostCommand | None,
    ) -> bool:
        entry = ControlAuditEntry(
            command_id=command_id,
            at=self._clock.now(),
            verdict=verdict,
            action=command.action.value if command else "",
            bot_id=command.bot_id if command else "",
            message=message,
        )
        try:
            self._audit.record(entry)
        except OSError:
            logger.exception(
                "[control] the audit line for %s could not be written", command_id
            )
            return False
        return True
