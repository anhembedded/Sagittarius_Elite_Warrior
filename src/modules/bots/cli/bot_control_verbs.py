"""`bot stop`, `bot pause`, `bot resume`, `bot start` and `bot delete` (`EPIC-038J`, `EPIC-038K`, decision O4, channel A).

Five verbs of the `bot` command that change a bot **in another process**: the running `run`
host. This process is a read-only copy (`"read_only": true` in `cli_commands.json`) and changes
nothing; each verb hands a request to `IHostControl`, which writes it where the host reads it,
and waits for the host's recorded answer. The bot is changed by the host, through the command
the Bots tab dispatches - there is no second implementation of Stop here.

@par Exit codes (decision D9)
  · `0`  - the host ran the command and the bot accepted it;
  · `2`  - the bot's own gate refused (not found, not in a state that allows it, real money not
           confirmed, a HALTED bot to resume...), in the screen's words; nothing changed;
  · `1`  - the host refused the command itself (malformed, expired, replayed, failed);
  · `5`  - this account has no control over the running copy (no directory, no permission);
  · `10` - no host is running; nothing was written;
  · `11` - a host is running but recorded no answer in time (`--wait`).

@par Extension cases
  · a new verb (`bot archive`) - a `HostControlAction` member, a row in the host's executor, one
    class here and one `BOT_VERBS` entry; `start` and `delete` (`EPIC-038K`) were added so.
"""

from __future__ import annotations

import argparse
import math

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_control_reports import (
    control_report,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_verb_world import BotVerbWorld
from Sagittarius_Elite_Warrior.src.modules.bots.cli.i_bot_verb import IBotVerb

_EXIT_OF: dict[HostControlStatus, ExitCode] = {
    HostControlStatus.REFUSED: ExitCode.USAGE,
    HostControlStatus.REJECTED: ExitCode.ERROR,
    HostControlStatus.NO_CONTROL: ExitCode.CONFIGURATION,
    HostControlStatus.NOT_RUNNING: ExitCode.HOST_NOT_RUNNING,
    HostControlStatus.NO_ANSWER: ExitCode.HOST_UNHEALTHY,
}


class _ControlVerb(IBotVerb):
    action: HostControlAction

    def run(self, args: argparse.Namespace, world: BotVerbWorld) -> CliOutcome | None:
        if not math.isfinite(args.wait) or args.wait < 0:
            return CliOutcome(
                ExitCode.USAGE, "--wait must be a finite number of seconds, 0 or more"
            )
        request = HostControlRequest(
            self.action,
            args.bot_id,
            getattr(args, "confirm_venue", None),
            getattr(args, "close_position", False),
        )
        reply = world.host_control.send(request, args.wait)
        if reply.status is HostControlStatus.DONE:
            return world.printer.print_report(control_report(request, reply), args)
        return _failure(request, reply)


def _failure(request: HostControlRequest, reply: HostControlReply) -> CliOutcome:
    return CliOutcome(
        _EXIT_OF[reply.status],
        f"bot {request.action.value} {request.bot_id}: {reply.message}",
    )


class StopBotVerb(_ControlVerb):
    name = "stop"
    action = HostControlAction.STOP


class PauseBotVerb(_ControlVerb):
    name = "pause"
    action = HostControlAction.PAUSE


class ResumeBotVerb(_ControlVerb):
    name = "resume"
    action = HostControlAction.RESUME


class StartBotVerb(_ControlVerb):
    name = "start"
    action = HostControlAction.START


class DeleteBotVerb(_ControlVerb):
    name = "delete"
    action = HostControlAction.DELETE
