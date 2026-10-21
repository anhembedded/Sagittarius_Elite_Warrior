"""`bot stop`, `bot pause`, `bot resume`, `bot start`, `bot edit`, `bot add` and `bot delete` (`EPIC-038J`, `EPIC-038K`, `EPIC-038L`, `EPIC-045`, decision O4, channel A).

Seven verbs of the `bot` command that change a bot **in another process**: the running `run`
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
    (`EPIC-038L`) too, with a `_request_of` of its own for the settings it carries; `add`
    (`EPIC-045A`) reads a plan file for its entry, `delete` (`EPIC-045B`) is the plain shape.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    ADD_SUBJECT,
    LOSS_CAP_SUBJECT,
    STRATEGY_SUBJECT,
    HostControlAction,
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    MAX_SETTINGS_PER_EDIT,
    ParameterSetting,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    PlannedBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_parser import (
    InvalidBotPlanError,
    parse_plan,
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
        request = self._request_of(args, world)
        if isinstance(request, CliOutcome):
            return request
        reply = world.host_control.send(request, args.wait)
        if reply.status is HostControlStatus.DONE:
            return world.printer.print_report(control_report(request, reply), args)
        return _failure(request, reply)

    def _request_of(
        self, args: argparse.Namespace, world: BotVerbWorld
    ) -> HostControlRequest | CliOutcome:
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


class ConfirmResumeBotVerb(_ControlVerb):
    """`bot confirm-resume <id>`: lay the ladder `bot resume` proposed, as the tab's Confirm resume does."""

    name = "confirm-resume"
    action = HostControlAction.CONFIRM_RESUME


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

    def _request_of(
        self, args: argparse.Namespace, world: BotVerbWorld
    ) -> HostControlRequest | CliOutcome:
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


class DeleteBotVerb(_ControlVerb):
    """`bot delete <id>`: the screen's Delete, for one bot at rest, on the running host (`EPIC-045B`).

    The plain shape of a control verb: it names a bot and nothing else. Whether the bot may be
    forgotten (DRAFT or STOPPED, and nothing left on the exchange) is the host's answer, in words.
    """

    name = "delete"
    action = HostControlAction.DELETE


class MoveBotVerb(_ControlVerb):
    """`bot move <id> --venue <venue>`: the screen's Venue field, for one DRAFT that never ran, on the running host (`EPIC-045G`).

    The bot keeps its id and stays DRAFT; a move places no order and asks no `--confirm-venue` (the
    real-money question is at `bot start`). Whether the bot may move (a Spot bot, a DRAFT that never ran)
    and whether the venue is one this build trades on is the host's answer, in words.
    """

    name = "move"
    action = HostControlAction.MOVE

    def _request_of(
        self, args: argparse.Namespace, world: BotVerbWorld
    ) -> HostControlRequest | CliOutcome:
        if not args.venue:
            return CliOutcome(ExitCode.USAGE, "bot move needs --venue <venue>")
        return HostControlRequest(self.action, args.bot_id, to_venue=args.venue)


class AddBotVerb(_ControlVerb):
    """`bot add <plan.json> [--name X] [--venue V]`: the screen's New bot, from one entry of a plan file, on the running host (`EPIC-045A`).

    The file is read and judged here for its shape by the plan parser the other plan verbs use
    (`parse_plan`), so a typo never reaches the host; whether the kind, the venue and the
    parameters are ones the host can store is the host's answer, in words. A plan names its
    bots by name and venue: without `--name` the plan must hold exactly one bot. `desired_state`
    in the entry is ignored: an add starts nothing, and records no desired state.
    """

    name = "add"
    action = HostControlAction.ADD

    def _request_of(
        self, args: argparse.Namespace, world: BotVerbWorld
    ) -> HostControlRequest | CliOutcome:
        path = Path(args.plan)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as failure:
            reason = getattr(failure, "strerror", None) or type(failure).__name__
            return CliOutcome(ExitCode.USAGE, f"cannot read the plan {path}: {reason}")
        try:
            plan = parse_plan(text, world.kinds)
        except InvalidBotPlanError as invalid:
            listed = "\n".join(f"  - {problem}" for problem in invalid.problems)
            return CliOutcome(
                ExitCode.USAGE, f"{path} is not a plan this build can read:\n{listed}"
            )
        chosen = _chosen(plan.bots, args.name, args.venue)
        if isinstance(chosen, CliOutcome):
            return chosen
        try:
            entry = NewBotEntry(
                chosen.name,
                chosen.kind,
                chosen.venue.value,
                chosen.symbol,
                tuple(ParameterSetting(k, v) for k, v in chosen.params.items()),
            )
        except ValueError as invalid_entry:
            return CliOutcome(
                ExitCode.USAGE,
                f"{path}: the bot {chosen.name!r} cannot be sent to the host: {invalid_entry}",
            )
        return HostControlRequest(self.action, ADD_SUBJECT, entry=entry)


def _chosen(
    bots: tuple[PlannedBot, ...], name: str | None, venue: str | None
) -> PlannedBot | CliOutcome:
    """The one entry the operator means: by name (and venue), or the only one."""
    matching = [
        bot
        for bot in bots
        if (name is None or bot.name == name)
        and (venue is None or bot.venue.value == venue)
    ]
    if len(matching) == 1:
        return matching[0]
    listed = "; ".join(f"{bot.name} on {bot.venue.value}" for bot in bots) or "none"
    if not matching:
        return CliOutcome(
            ExitCode.USAGE,
            f"no bot of the plan matches (it holds: {listed}); name one with --name"
            " (and --venue)",
        )
    return CliOutcome(
        ExitCode.USAGE,
        f"{len(matching)} bots of the plan match (it holds: {listed}); choose one with "
        "--name and, for a name on two venues, --venue",
    )


class AcknowledgeLossCapVerb(_ControlVerb):
    """`bot loss-cap-ack`: the owner clears the latched loss cap so bots may start again (`EPIC-026L`).

    It names no bot; the request's `bot_id` is the fixed subject word. It starts nothing: each bot
    is started or resumed afterwards by the owner, through the commands that always ask.
    """

    name = "loss-cap-ack"
    action = HostControlAction.ACKNOWLEDGE_LOSS_CAP

    def _request_of(
        self, args: argparse.Namespace, world: BotVerbWorld
    ) -> HostControlRequest | CliOutcome:
        return HostControlRequest(self.action, LOSS_CAP_SUBJECT)


class ArmStrategyVerb(_ControlVerb):
    """`bot arm-strategy --venue <venue>`: the screen's Arm strategy, for the venue's saved arming, on the running host (`EPIC-045G`).

    It names no bot (the request's `bot_id` is the fixed subject word) and types no parameter: the strategy,
    symbol, interval, sizing, leverage and parameters are the saved arming's (owner decision O2). An armed
    strategy places orders by itself, so on a mainnet venue `--confirm-venue` must repeat the venue.
    """

    name = "arm-strategy"
    action = HostControlAction.ARM_STRATEGY

    def _request_of(
        self, args: argparse.Namespace, world: BotVerbWorld
    ) -> HostControlRequest | CliOutcome:
        if not args.venue:
            return CliOutcome(ExitCode.USAGE, "bot arm-strategy needs --venue <venue>")
        return HostControlRequest(
            self.action,
            STRATEGY_SUBJECT,
            getattr(args, "confirm_venue", None),
            strategy_venue=args.venue,
        )


class DisarmStrategyVerb(_ControlVerb):
    """`bot disarm-strategy --venue <venue>`: the screen's Disarm strategy, on the running host (`EPIC-045G`).

    It sells and cancels nothing, so it asks no `--confirm-venue`; a position open on the strategy's symbol
    refuses it, in the screen's words.
    """

    name = "disarm-strategy"
    action = HostControlAction.DISARM_STRATEGY

    def _request_of(
        self, args: argparse.Namespace, world: BotVerbWorld
    ) -> HostControlRequest | CliOutcome:
        if not args.venue:
            return CliOutcome(
                ExitCode.USAGE, "bot disarm-strategy needs --venue <venue>"
            )
        return HostControlRequest(
            self.action, STRATEGY_SUBJECT, strategy_venue=args.venue
        )
