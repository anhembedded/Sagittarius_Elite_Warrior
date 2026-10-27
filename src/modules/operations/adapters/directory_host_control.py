"""The operator's side of control: write a command file, read the host's answer (`EPIC-038J`).

Runs in the second process (`bot stop`, `bot pause`, `bot resume`, `bot start`, `bot edit`), which is a read-only copy and
changes nothing itself. In order:

  1. no copy holds the data root's lock -> `NOT_RUNNING`, and **nothing is written**;
  2. the control directory is absent -> `NO_CONTROL`: the copy that runs is not a `run` host, or
     the host runs as another account;
  3. the command is written under a dot-name, `0600`, then renamed to `cmd-<id>.json` - the host
     never sees half a file - and the audit is polled for that id;
  4. the verdict the host recorded becomes the reply.

**The same command id sent again does the work once** (`EPIC-047C`: the remote link's bridge sends
the id the desktop made, and a desktop that lost its connection sends it again). An id the host
has already settled is answered from the audit, whatever the host does now, and nothing is written;
an id whose file still waits for the host, or that the host has claimed, is waited for and not
written again. The command line's ids are fresh random ones, so it never meets either case.

**A timeout never leaves a hidden command.** The writer tries to remove its own file. The host
claims a file by renaming it **before** reading it (`DirectoryHostCommandInbox`), so the removal
succeeds only while the host has not taken it: then the reply says "withdrawn, nothing happened"
and it is true. If the file is already gone the host has it, so the writer waits a short grace for the outcome and, failing that,
says the command was taken and its outcome is not recorded - which is true, and which the operator
resolves by looking at `bot show`.

The waits are injected (`sleep`, `monotonic`), so a test pumps the host from `sleep` and nothing
sleeps for real.
"""

from __future__ import annotations

import logging
import math
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_host_control import IHostControl
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_probe import (
    IInstanceProbe,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.control_directory import (
    claimed_name,
    command_file_name,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_command_codec import (
    encode_command,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_command import (
    ControlAuditEntry,
    ControlVerdict,
    HostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_control_audit import (
    IHostControlAudit,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)

logger = logging.getLogger("App.Operations.Control")

POLL_STEP_S = 0.1
#: How long the writer waits for an outcome after the host has taken the file.
TAKEN_GRACE_S = 5.0

_CREATE_NEW = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
_PRIVATE_FILE = 0o600


class DirectoryHostControl(IHostControl):
    def __init__(
        self,
        directory: Path,
        probe: IInstanceProbe,
        audit: IHostControlAudit,
        clock: IOperationsClock,
        new_command_id: Callable[[], str],
        sleep: Callable[[float], None],
        monotonic: Callable[[], float],
    ) -> None:
        self._directory = directory
        self._probe = probe
        self._audit = audit
        self._clock = clock
        self._new_command_id = new_command_id
        self._sleep = sleep
        self._monotonic = monotonic

    def send(self, request: HostControlRequest, wait_s: float) -> HostControlReply:
        if not math.isfinite(wait_s) or wait_s < 0:
            raise ValueError(
                f"wait_s must be a finite, non-negative number, not {wait_s}"
            )
        command_id = self._new_command_id()
        settled = self._audit.final_entry_of(command_id)
        if settled is not None:
            return _replay_of(settled, request)
        if not self._probe.is_held():
            return HostControlReply(
                HostControlStatus.NOT_RUNNING,
                "No host is running on this data root, so nothing was sent and nothing changed.",
            )
        if not self._directory.is_dir():
            return HostControlReply(
                HostControlStatus.NO_CONTROL,
                f"The running copy offers no control: {self._directory} does not exist. Only "
                "`main.py run` accepts commands, and only for the account it runs as.",
            )
        command = HostCommand(
            command_id,
            request.action,
            request.bot_id,
            request.confirmed_venue,
            self._clock.now(),
            request.close_position,
            request.settings,
            request.entry,
            request.to_venue,
            request.proposal,
            request.strategy_venue,
            request.desired_state,
        )
        wrote = False
        if not self._is_waiting_for_the_host(command_id):
            written = self._write(command)
            if written.reply is not None:
                return written.reply
            wrote = written.wrote
        return self._await_outcome(command, wait_s, wrote=wrote)

    def _is_waiting_for_the_host(self, command_id: str) -> bool:
        """An earlier send of this id left its file for the host, or the host has taken it."""
        name = command_file_name(command_id)
        return (self._directory / name).exists() or (
            self._directory / claimed_name(name)
        ).exists()

    def _write(self, command: HostCommand) -> _Written:
        final = self._directory / command_file_name(command.command_id)
        scratch = self._directory / f".{command.command_id}.tmp"
        try:
            descriptor = os.open(scratch, _CREATE_NEW, _PRIVATE_FILE)
        except FileExistsError:
            # Another send of this id is writing its file right now: wait for it, never touch its scratch.
            return _Written(wrote=False)
        except OSError as failure:
            return _Written(wrote=False, reply=self._cannot_write(failure))
        try:
            with os.fdopen(descriptor, "wb") as opened:
                opened.write(encode_command(command).encode("utf-8"))
                opened.flush()
                os.fsync(opened.fileno())
            os.replace(scratch, final)
        except OSError as failure:
            scratch.unlink(missing_ok=True)
            return _Written(wrote=False, reply=self._cannot_write(failure))
        return _Written(wrote=True)

    def _cannot_write(self, failure: OSError) -> HostControlReply:
        return HostControlReply(
            HostControlStatus.NO_CONTROL,
            f"This account cannot write to {self._directory} ({type(failure).__name__}): "
            "only the account the host runs as may send it a command.",
        )

    def _await_outcome(
        self, command: HostCommand, wait_s: float, *, wrote: bool
    ) -> HostControlReply:
        settled = self._wait_for(command.command_id, wait_s)
        if settled is not None:
            return _reply_of(settled)
        if not wrote:
            return self._unanswered_earlier_send(command, wait_s)
        file = self._directory / command_file_name(command.command_id)
        try:
            file.unlink()
        except FileNotFoundError:
            return self._after_taken(command)
        except OSError as failure:
            return HostControlReply(
                HostControlStatus.NO_ANSWER,
                f"The host recorded no answer in {wait_s:g} s and the command could not be "
                f"withdrawn ({type(failure).__name__}); it may still run.",
                command.command_id,
            )
        return HostControlReply(
            HostControlStatus.NO_ANSWER,
            f"The host did not pick the command up within {wait_s:g} s; it was withdrawn and "
            "nothing happened. Is the host running, and is it a `run` host?",
            command.command_id,
        )

    def _unanswered_earlier_send(
        self, command: HostCommand, wait_s: float
    ) -> HostControlReply:
        """This send wrote nothing: an earlier send of the id did. It is not this send's to withdraw,
        and what it says must be true of what it saw (the file there, taken, or gone)."""
        name = command_file_name(command.command_id)
        if (self._directory / claimed_name(name)).exists():
            words = (
                "The host took the command an earlier send of this id left and recorded no outcome "
                f"within {wait_s:g} s. Check `bot show` for the bot's state."
            )
        elif (self._directory / name).exists():
            words = (
                f"The command an earlier send of this id left is still waiting for the host after "
                f"{wait_s:g} s; it was not withdrawn. Is the host running, and is it a `run` host?"
            )
        else:
            words = (
                "The command an earlier send of this id left is gone and the host recorded no "
                "outcome: if that send withdrew it, nothing happened. Check `bot show`, or send "
                "the command again under a new id."
            )
        return HostControlReply(HostControlStatus.NO_ANSWER, words, command.command_id)

    def _after_taken(self, command: HostCommand) -> HostControlReply:
        settled = self._wait_for(command.command_id, TAKEN_GRACE_S)
        if settled is not None:
            return _reply_of(settled)
        return HostControlReply(
            HostControlStatus.NO_ANSWER,
            "The host took the command but recorded no outcome. Check `bot show` for the bot's "
            f"state; the command id is {command.command_id}.",
            command.command_id,
        )

    def _wait_for(self, command_id: str, seconds: float) -> ControlAuditEntry | None:
        deadline = self._monotonic() + seconds
        while True:
            settled = self._audit.final_entry_of(command_id)
            if settled is not None:
                return settled
            if self._monotonic() >= deadline:
                return None
            self._sleep(POLL_STEP_S)


@dataclass(frozen=True, slots=True)
class _Written:
    """Whether this send wrote the command file, and the reply when it could not."""

    wrote: bool
    reply: HostControlReply | None = None


def _replay_of(
    entry: ControlAuditEntry, request: HostControlRequest
) -> HostControlReply:
    """An id the host already settled: its recorded outcome, if the request is the same action."""
    if entry.action != request.action.value:
        return HostControlReply(
            HostControlStatus.REJECTED,
            f"The command id {entry.command_id} already settled a '{entry.action}' command, not "
            f"'{request.action.value}': send this command under a new id.",
            entry.command_id,
        )
    return _reply_of(entry)


def _reply_of(entry: ControlAuditEntry) -> HostControlReply:
    if entry.verdict is ControlVerdict.EXECUTED:
        return HostControlReply(
            HostControlStatus.DONE, entry.message, entry.command_id, entry.bot_id
        )
    if entry.verdict is ControlVerdict.REFUSED:
        return HostControlReply(
            HostControlStatus.REFUSED, entry.message, entry.command_id
        )
    return HostControlReply(
        HostControlStatus.REJECTED,
        f"The host refused the command ({entry.verdict.value}): {entry.message}",
        entry.command_id,
    )
