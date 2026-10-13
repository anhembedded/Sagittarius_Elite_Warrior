"""Apply a plan through the commands the Bots screen uses (`EPIC-038I`).

The plan path and the screen path are one path (decision D2): a bot is created, edited
and deleted by `CreateBotCommand`, `EditBotCommand` and `DeleteBotCommand`, dispatched
through `ICommandDispatcher`, so the lifecycle table and every other rule apply. Nothing
here writes a bot file, and nothing here starts or stops a bot.

Each entry is applied on its own: an entry the table refuses does not keep the others from
being applied, and the result lists them all. A refused or failed entry is **not recorded**
as wanted: `run --start-planned` must not start a bot with parameters the operator thought
they had changed and did not get.

@par The record
After the commands, the plan's desired states are recorded per bot id (`IAppliedPlanStore`).
It is rewritten only when it would change, so a second apply of the same plan touches nothing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    BotPlanDocument,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_change import (
    ChangeAction,
    PlanChange,
    PlanDiff,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_differ import (
    PrunePolicy,
    diff_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    BotList,
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot.command import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.delete_bot.command import (
    DeleteBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot.command import (
    EditBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedBot,
    AppliedPlan,
    AppliedPlanUnreadableError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_applied_plan_store import (
    IAppliedPlanStore,
)

logger = logging.getLogger("App.Bots.Plan")


@dataclass(frozen=True, slots=True)
class ChangeOutcome:
    """One change, and whether it was carried out."""

    change: PlanChange
    #: A change that needed no command (`LEAVE`) is done.
    done: bool
    message: str = ""
    bot_id: str | None = None


@dataclass(frozen=True, slots=True)
class ApplyResult:
    diff: PlanDiff
    outcomes: tuple[ChangeOutcome, ...]
    notes: tuple[str, ...] = ()

    @property
    def exit_ok(self) -> bool:
        """False when any entry was blocked by the table or refused by its command."""
        return all(
            outcome.done or outcome.change.action is ChangeAction.LEAVE
            for outcome in self.outcomes
        )


@dataclass(frozen=True, slots=True)
class PlanPreview:
    """What an apply would do, and what the operator must be told about the comparison."""

    diff: PlanDiff
    notes: tuple[str, ...] = ()


class PlanApplier:
    def __init__(
        self, dispatcher: ICommandDispatcher, store: IAppliedPlanStore
    ) -> None:
        self._dispatcher = dispatcher
        self._store = store

    def preview(self, plan: BotPlanDocument, prune: PrunePolicy) -> PlanPreview:
        """What `apply` would do, with the same notes an apply carries (an unreadable bot
        file or record changes what the diff can see); nothing is dispatched or written."""
        diff, notes = self._compare(plan, prune)
        return PlanPreview(diff, notes)

    def apply(self, plan: BotPlanDocument, prune: PrunePolicy) -> ApplyResult:
        diff, notes = self._compare(plan, prune)
        outcomes = tuple(self._carry_out(change) for change in diff.changes)
        record = self._record_of(plan, outcomes)
        if record != self._previous_record():
            self._store.write(record)
        result = ApplyResult(diff, outcomes, notes)
        logger.info("[plan] applied: %s", _counts(result))
        return result

    # --- internals ------------------------------------------------------------

    def _compare(
        self, plan: BotPlanDocument, prune: PrunePolicy
    ) -> tuple[PlanDiff, tuple[str, ...]]:
        listing = cast(
            BotList, self._dispatcher.dispatch(ListBotsQuery, ListBotsQuery())
        )
        notes: list[str] = []
        try:
            recorded = self._store.read()
        except AppliedPlanUnreadableError as unreadable:
            recorded = None
            notes.append(
                f"the previous record of the applied plan could not be read ({unreadable}); "
                "applying replaces it"
            )
        if listing.refused:
            names = ", ".join(file.name for file in listing.refused)
            notes.append(
                f"{len(listing.refused)} bot file(s) this build cannot read are not part "
                f"of the comparison: {names}"
            )
        return diff_plan(plan, listing.bots, recorded, prune), tuple(notes)

    def _previous_record(self) -> AppliedPlan | None:
        try:
            return self._store.read()
        except AppliedPlanUnreadableError:
            return None

    def _carry_out(self, change: PlanChange) -> ChangeOutcome:
        entry = change.planned
        if change.action is ChangeAction.CREATE and entry is not None:
            return self._outcome(
                change,
                self._dispatch(
                    CreateBotCommand,
                    CreateBotCommand(
                        entry.name, entry.kind, entry.venue, entry.symbol, entry.params
                    ),
                ),
            )
        if change.action is ChangeAction.EDIT and entry is not None and change.bot_id:
            return self._outcome(
                change,
                self._dispatch(
                    EditBotCommand,
                    EditBotCommand(change.bot_id, entry.name, entry.params),
                ),
            )
        if change.action is ChangeAction.DELETE and change.bot_id:
            return self._outcome(
                change,
                self._dispatch(DeleteBotCommand, DeleteBotCommand(change.bot_id)),
            )
        if change.action is ChangeAction.BLOCKED:
            return ChangeOutcome(change, False, change.detail, change.bot_id)
        return ChangeOutcome(change, True, change.detail, change.bot_id)

    def _dispatch(self, handler_class: type, command: object) -> BotCommandResult:
        return cast(BotCommandResult, self._dispatcher.dispatch(handler_class, command))

    @staticmethod
    def _outcome(change: PlanChange, result: BotCommandResult) -> ChangeOutcome:
        if result.accepted:
            return ChangeOutcome(change, True, change.detail, result.bot_id)
        reason = result.refusal.value if result.refusal is not None else "REFUSED"
        return ChangeOutcome(
            change, False, f"refused by the bot command ({reason}): {result.message}"
        )

    @staticmethod
    def _record_of(
        plan: BotPlanDocument, outcomes: tuple[ChangeOutcome, ...]
    ) -> AppliedPlan:
        """The plan's wishes for the entries that now match it, by bot id."""
        wanted = {entry.identity: entry for entry in plan.bots}
        applied: list[AppliedBot] = []
        for outcome in outcomes:
            change = outcome.change
            entry = (
                wanted.get((change.name, change.venue))
                if change.planned is not None
                else None
            )
            if entry is None or not outcome.done or outcome.bot_id is None:
                continue
            applied.append(
                AppliedBot(
                    outcome.bot_id,
                    entry.name,
                    entry.venue.value,
                    entry.desired_state,
                )
            )
        return AppliedPlan(tuple(applied))


def _counts(result: ApplyResult) -> str:
    """`1 create, 0 edit, ...`: what the apply did, as one greppable line."""
    counts = {action: 0 for action in ChangeAction}
    for outcome in result.outcomes:
        counts[outcome.change.action] += 1
    return ", ".join(f"{counts[action]} {action.value}" for action in ChangeAction)
