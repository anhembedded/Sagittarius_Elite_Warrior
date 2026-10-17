"""`bot stop`, `bot pause`, `bot resume`, `bot start` and `bot edit` (`EPIC-038J`, `EPIC-038K`, `EPIC-038L`, decision O4, channel A).

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
    class here and one `BOT_VERBS` entry; `start` (`EPIC-038K`) was added so, and `edit`
    (`EPIC-038L`) too, with a `_request_of` of its own for the settings it carries.
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
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    MAX_SETTINGS_PER_EDIT,
    ParameterSetting,
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
        request = self._request_of(args)
        if isinstance(request, CliOutcome):
            return request
        reply = world.host_control.send(request, args.wait)
        if reply.status is HostControlStatus.DONE:
            return world.printer.print_report(control_report(request, reply), args)
        return _failure(request, reply)

    def _request_of(self, args: argparse.Namespace) -> HostControlRequest | CliOutcome:
        return HostControlRequest(
            self.action,
            args.bot_id,
            getattr(args, "confirm_venue", None),
            getattr(args, "close_position", False),
        )


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


class EditBotVerb(_ControlVerb):
    """`bot edit <id> --set key=value ...`: the screen's Save, for one bot at rest, on the running host.

    Everything the operator typed is judged here for its *shape* before a file is written, so a typo
    never reaches the host; whether a key exists and a value is readable is the bot kind's answer,
    given by the host in words (`IBotKind.parameter_problem`). The usage refusals never repeat a
    value: a value typed in the wrong place may be a secret, and this is a terminal that logs.
    """

    name = "edit"
    action = HostControlAction.EDIT

    def _request_of(self, args: argparse.Namespace) -> HostControlRequest | CliOutcome:
        given: list[str] = args.set or []
        if not given:
            return CliOutcome(
                ExitCode.USAGE, "bot edit needs at least one --set key=value"
            )
        if len(given) > MAX_SETTINGS_PER_EDIT:
            return CliOutcome(
                ExitCode.USAGE,
                f"bot edit takes at most {MAX_SETTINGS_PER_EDIT} --set, not {len(given)}",
            )
        settings: list[ParameterSetting] = []
        for position, text in enumerate(given, start=1):
            try:
                settings.append(ParameterSetting.parse(text))
            except ValueError as invalid:
                return CliOutcome(ExitCode.USAGE, f"--set {position}: {invalid}")
        keys = [setting.key for setting in settings]
        repeated = sorted({key for key in keys if keys.count(key) > 1})
        if repeated:
            return CliOutcome(
                ExitCode.USAGE,
                f"{', '.join(repeated)} is given more than once; set each parameter once",
            )
        return HostControlRequest(self.action, args.bot_id, settings=tuple(settings))
