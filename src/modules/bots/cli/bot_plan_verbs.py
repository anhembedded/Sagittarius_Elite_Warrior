"""`bot apply` and `bot export` (`EPIC-038I`): a plan file in, bots that match it out.

Both are verbs of the `bot` command (`BOT_VERBS`), thin over the plan code in
`application/plan/`: they read the file, call it, print the `Report` and choose the exit
code. Everything that changes a bot is a command dispatched through `ICommandDispatcher`
(`PlanApplier`), so the lifecycle table and the read-only rule apply as on the screen.

@par Exit codes (decision D9)
  · `0` - applied, or nothing to do; a dry run printed its diff;
  · `2` - the plan or the arguments are wrong, or an entry needs a stop first (the others
    were still applied and are listed);
  · `3` - another copy holds the data root and `apply` would change bots (a dry run does
    not need the lock).
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    BotPlanDocument,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_parser import (
    InvalidBotPlanError,
    parse_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_applier import (
    ApplyResult,
    PlanApplier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_change import (
    ChangeAction,
    PlanDiff,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_differ import (
    PrunePolicy,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.export_bot_plan_to_file import (
    ExportBotPlanToFileCommand,
    PlanFileExport,
    PlanFileNotExported,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_control_verbs import (
    EXIT_OF_HOST_STATUS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_plan_host_apply import (
    HostPlanApplier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_plan_reports import (
    apply_report,
    export_report,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_verb_world import BotVerbWorld
from Sagittarius_Elite_Warrior.src.modules.bots.cli.i_bot_verb import IBotVerb


class ApplyBotPlanVerb(IBotVerb):
    name = "apply"

    def run(self, args: argparse.Namespace, world: BotVerbWorld) -> CliOutcome | None:
        loaded = _load_plan(Path(args.plan), world)
        if isinstance(loaded, CliOutcome):
            return loaded
        prune = PrunePolicy.PRUNE if args.prune else PrunePolicy.KEEP
        applier = PlanApplier(world.dispatcher, world.plans)
        if args.dry_run:
            return self._dry_run(applier, loaded, prune, args, world)
        if world.instance.read_only:
            return self._beside_a_host(applier, loaded, prune, args, world)
        result = applier.apply(loaded, prune)
        printed = world.printer.print_report(
            apply_report(result.diff, result, result.notes), args
        )
        if printed is not None:
            return printed
        return _needs_attention(result.diff)

    @staticmethod
    def _beside_a_host(
        applier: PlanApplier,
        plan: BotPlanDocument,
        prune: PrunePolicy,
        args: argparse.Namespace,
        world: BotVerbWorld,
    ) -> CliOutcome | None:
        """Another copy holds the data root: ask it, entry by entry (`EPIC-045C`, `HostPlanApplier`)."""
        if not math.isfinite(args.wait) or args.wait < 0:
            return CliOutcome(
                ExitCode.USAGE, "--wait must be a finite number of seconds, 0 or more"
            )
        run = HostPlanApplier(applier, world.host_control, world.plans).run(
            plan, prune, args.wait
        )
        if run.problems:
            listed = "\n".join(f"  - {problem}" for problem in run.problems)
            return CliOutcome(
                ExitCode.USAGE,
                "the plan has entries a command file cannot carry; nothing was sent "
                f"or changed:\n{listed}",
            )
        if run.result is None:
            host = run.stopped_by
            return CliOutcome(
                EXIT_OF_HOST_STATUS.get(host.status, ExitCode.LOCK_HELD)
                if host
                else ExitCode.LOCK_HELD,
                f"{world.instance.reason} `bot apply` changes bots and the running copy did not "
                f"take the plan: {host.message if host else 'no answer'}. Nothing was changed. "
                "`bot apply --dry-run` works here.",
            )
        notes = (*run.result.notes, *_failure_notes(run.result))
        printed = world.printer.print_report(
            apply_report(run.result.diff, run.result, notes), args
        )
        if printed is not None:
            return printed
        if run.unsent or run.unknown:
            return CliOutcome(
                ExitCode.HOST_UNHEALTHY,
                f"{run.unsent} change(s) were not sent and {run.unknown} were sent with the outcome unknown "
                "because the host stopped answering; the earlier ones were applied and all are listed above. "
                "Read `bot list`, then run the same plan again.",
            )
        return _needs_attention(run.result.diff) or _refused_by_host(run.result)

    @staticmethod
    def _dry_run(
        applier: PlanApplier,
        plan: BotPlanDocument,
        prune: PrunePolicy,
        args: argparse.Namespace,
        world: BotVerbWorld,
    ) -> CliOutcome | None:
        preview = applier.preview(plan, prune)
        printed = world.printer.print_report(
            apply_report(preview.diff, None, preview.notes), args
        )
        return printed if printed is not None else _needs_attention(preview.diff)


class ExportBotPlanVerb(IBotVerb):
    name = "export"

    def run(self, args: argparse.Namespace, world: BotVerbWorld) -> CliOutcome | None:
        ids = (args.bot_id,) if args.bot_id else ()
        if not args.all and not ids:
            return CliOutcome(ExitCode.USAGE, "bot export needs --all or --bot-id <id>")
        if args.all and ids:
            return CliOutcome(
                ExitCode.USAGE, "bot export takes --all or --bot-id, not both"
            )
        target = Path(args.output)
        exported = cast(
            PlanFileExport,
            world.dispatcher.dispatch(
                ExportBotPlanToFileCommand,
                ExportBotPlanToFileCommand(target, ids),
            ),
        )
        if isinstance(exported, PlanFileNotExported):
            return _export_refusal(exported)
        return world.printer.print_report(
            export_report(str(target), exported.bot_count), args
        )


def _export_refusal(refused: PlanFileNotExported) -> CliOutcome:
    target = refused.path
    if refused.reason == "unknown_bots":
        return CliOutcome(ExitCode.USAGE, refused.detail)
    if refused.reason == "exists":
        return CliOutcome(
            ExitCode.USAGE,
            f"{target} already exists; export never overwrites a plan - choose a new name",
        )
    return CliOutcome(ExitCode.USAGE, f"cannot write {target}: {refused.detail}")


def _load_plan(path: Path, world: BotVerbWorld) -> BotPlanDocument | CliOutcome:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as failure:
        reason = getattr(failure, "strerror", None) or type(failure).__name__
        return CliOutcome(ExitCode.USAGE, f"cannot read the plan {path}: {reason}")
    try:
        return parse_plan(text, world.kinds)
    except InvalidBotPlanError as invalid:
        listed = "\n".join(f"  - {problem}" for problem in invalid.problems)
        return CliOutcome(
            ExitCode.USAGE, f"{path} is not a plan this build can apply:\n{listed}"
        )


def _needs_attention(diff: PlanDiff) -> CliOutcome | None:
    blocked = diff.blocked
    if not blocked:
        return None
    named = "; ".join(f"{c.name} on {c.venue.value}" for c in blocked)
    return CliOutcome(
        ExitCode.USAGE,
        f"{len(blocked)} entr{'y' if len(blocked) == 1 else 'ies'} need attention "
        f"(needs stop first, or a new name): {named}. The others were applied or are listed above.",
    )


def _failure_notes(result: ApplyResult) -> tuple[str, ...]:
    """The host's sentence for every change it did not carry out, so the report says why."""
    return tuple(
        f"{o.change.name} on {o.change.venue.value}: {o.message}"
        for o in result.outcomes
        if not o.done and o.change.action is not ChangeAction.BLOCKED
    )


def _refused_by_host(result: ApplyResult) -> CliOutcome | None:
    refused = [
        o
        for o in result.outcomes
        if not o.done and o.change.action is not ChangeAction.BLOCKED
    ]
    if not refused:
        return None
    named = "; ".join(f"{o.change.name} on {o.change.venue.value}" for o in refused)
    return CliOutcome(
        ExitCode.USAGE,
        f"{len(refused)} entr{'y' if len(refused) == 1 else 'ies'} the host did not carry out: "
        f"{named}. The others were applied or are listed above.",
    )
