"""`EPIC-045C` - the host's "carry out this entry of a plan", answered by `bot apply`'s own applier.

`bot apply plan.json` beside a running host arrives entry by entry (decision C2). This handler is one entry
reached through the command directory. It adds no way to create or edit a bot: it runs the very `PlanApplier`
the offline apply runs, on a plan of that one entry, so the entry becomes a `CreateBotCommand` (a DRAFT), an
`EditBotCommand`, nothing, or the same "needs stop first" the offline apply prints, through the Bots tab's own
commands and lifecycle table.

The entry crossed a trust boundary, so it is read again as a plan: it is written as a one-bot plan document
and parsed by the plan parser the file path uses (`parse_plan`), which judges the kind, the venue, the shape of
every field, the secret-like parameter names and the desired state, in the plan's own words. Nothing about the
entry is trusted because the CLI had already read the file.

Applying never starts a bot and never places or cancels an order. The entry's wish (`running` or `stopped`) is
recorded for the bot that now matches it, and only `run --start-planned` and `bot start` act on a wish
(decision C5). Everything runs under `BotCommandLock`, the lock a Start, an Edit, an Add and a Delete hold.
"""

from __future__ import annotations

import json

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import PLAN_SUBJECT
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    SCHEMA,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_parser import (
    InvalidBotPlanError,
    parse_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_applier import (
    ChangeOutcome,
    PlanApplier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_change import (
    ChangeAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_command_lock import (
    BotCommandLock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ApplyPlanEntryForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_applied_plan_store import (
    IAppliedPlanStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)


class ApplyPlanEntryForHostCommandHandler(
    ICommandHandler[ApplyPlanEntryForHostCommand, BotCommandResult]
):
    def __init__(
        self,
        dispatcher: ICommandDispatcher,
        plans: IAppliedPlanStore,
        kinds: IBotKindCatalog,
        lock: BotCommandLock,
    ) -> None:
        self._applier = PlanApplier(dispatcher, plans)
        self._kinds = kinds
        self._lock = lock

    def execute(self, command: ApplyPlanEntryForHostCommand) -> BotCommandResult:
        try:
            plan = parse_plan(_one_bot_plan(command), self._kinds)
        except InvalidBotPlanError as invalid:
            return _refused(BotRefusal.INVALID_DEFINITION, "; ".join(invalid.problems))
        (entry,) = plan.bots
        with self._lock.held():
            outcome = self._applier.apply_entry(entry)
        return _reply(outcome)


def _one_bot_plan(command: ApplyPlanEntryForHostCommand) -> str:
    entry = command.entry
    return json.dumps(
        {
            "schema": SCHEMA,
            "bots": [
                {
                    "name": entry.name,
                    "kind": entry.kind,
                    "venue": entry.venue,
                    "symbol": entry.symbol,
                    "params": {s.key: s.value for s in entry.params},
                    "desired_state": command.desired_state,
                }
            ],
        }
    )


def _reply(outcome: ChangeOutcome) -> BotCommandResult:
    change = outcome.change
    if outcome.done:
        return BotCommandResult(
            accepted=True,
            bot_id=outcome.bot_id,
            message=f"{change.action.value} {change.name} on {change.venue.value}: {outcome.message}",
        )
    refusal = (
        BotRefusal.INVALID_TRANSITION
        if change.action is ChangeAction.BLOCKED
        else BotRefusal.INVALID_DEFINITION
    )
    return BotCommandResult.refused(
        refusal,
        f"{change.name} on {change.venue.value}: {outcome.message}. Nothing was changed for this entry.",
        outcome.bot_id or PLAN_SUBJECT,
    )


def _refused(refusal: BotRefusal, words: str) -> BotCommandResult:
    return BotCommandResult.refused(
        refusal,
        f"The entry is not a plan entry this build can apply: {words}. Nothing was changed.",
        PLAN_SUBJECT,
    )
