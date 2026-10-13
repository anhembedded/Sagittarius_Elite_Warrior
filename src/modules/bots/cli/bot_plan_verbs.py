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
    PlanApplier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_change import (
    PlanDiff,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_differ import (
    PrunePolicy,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_export import (
    UnknownBotsError,
    export_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    BotList,
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_plan_reports import (
    apply_report,
    export_report,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_verb_world import BotVerbWorld
from Sagittarius_Elite_Warrior.src.modules.bots.cli.i_bot_verb import IBotVerb
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedPlan,
    AppliedPlanUnreadableError,
)


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
            return CliOutcome(
                ExitCode.LOCK_HELD,
                f"{world.instance.reason} `bot apply` changes bots, so it needs to be the "
                "writable copy; nothing was changed. `bot apply --dry-run` works here.",
            )
        result = applier.apply(loaded, prune)
        printed = world.printer.print_report(
            apply_report(result.diff, result, result.notes), args
        )
        if printed is not None:
            return printed
        return _needs_attention(result.diff)

    @staticmethod
    def _dry_run(
        applier: PlanApplier,
        plan: BotPlanDocument,
        prune: PrunePolicy,
        args: argparse.Namespace,
        world: BotVerbWorld,
    ) -> CliOutcome | None:
        diff = applier.diff(plan, prune)
        printed = world.printer.print_report(apply_report(diff, None, ()), args)
        return printed if printed is not None else _needs_attention(diff)


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
        listing = cast(
            BotList, world.dispatcher.dispatch(ListBotsQuery, ListBotsQuery())
        )
        try:
            document = export_plan(listing.bots, _recorded(world), ids)
        except UnknownBotsError as unknown:
            return CliOutcome(ExitCode.USAGE, str(unknown))
        target = Path(args.output)
        try:
            with target.open("x", encoding="utf-8") as stream:
                stream.write(document.to_json_text())
        except FileExistsError:
            return CliOutcome(
                ExitCode.USAGE,
                f"{target} already exists; export never overwrites a plan - choose a new name",
            )
        except OSError as failure:
            return CliOutcome(
                ExitCode.USAGE, f"cannot write {target}: {failure.strerror}"
            )
        return world.printer.print_report(
            export_report(str(target), len(document.bots)), args
        )


def _recorded(world: BotVerbWorld) -> AppliedPlan | None:
    try:
        return world.plans.read()
    except AppliedPlanUnreadableError:
        return None


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
