"""`bot apply` beside a running host (`EPIC-045C`): the same plan, carried out entry by entry through the command directory.

The second process is a read-only copy of the data root, so it cannot dispatch a bot command or write the applied-plan
record. It does what `--dry-run` does (compares the plan with the stored bots, which it can read) and then asks the host
to carry out each change, one command file per change, waiting for the host's answer to each (decision C1, C2):

  · every plan entry that the comparison does not block becomes an `apply-entry` (the host creates a DRAFT, edits, or
    leaves, with the offline apply's own `PlanApplier`, and records the entry's wish);
  · a recorded wish that will not get a fresh row from this run becomes an `unplan`: a bot the plan does not name
    (whether or not it is then pruned) and a named entry the lifecycle table blocks, so the record ends as an offline
    apply would leave it (C6), and a bot is never started on a wish whose parameters were not applied;
  · a stored bot the plan does not name, under `--prune` and at rest, becomes a `delete`, which the host judges again
    (the lifecycle table and its exposure refusal, C8).

The plan is checked whole before the first command is sent, so a plan that cannot be carried changes nothing. A refusal
of one entry never stops the others; a host that stops answering stops the run, and every change not sent is listed as
not sent, never as done (C4). A host that took a command file and recorded no outcome may still have run it, so that
change is reported as sent with the outcome unknown, never as not sent or unchanged. Applying starts no bot and places no order (C5).
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    PLAN_SUBJECT,
    HostControlAction,
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_host_control import IHostControl
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    ParameterSetting,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    BotPlanDocument,
    PlannedBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_applier import (
    ApplyResult,
    ChangeOutcome,
    PlanApplier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_change import (
    ChangeAction,
    PlanChange,
    PlanDiff,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_differ import (
    PrunePolicy,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedPlanUnreadableError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_applied_plan_store import (
    IAppliedPlanStore,
)

#: The statuses that say nothing was written for the host: there is no host, or it takes no commands.
_NOT_DELIVERED = frozenset(
    {HostControlStatus.NOT_RUNNING, HostControlStatus.NO_CONTROL}
)
#: Taken by the host, no outcome recorded in time: the command may still run.
_UNKNOWN = HostControlStatus.NO_ANSWER


@dataclass(frozen=True, slots=True)
class HostApplyRun:
    """What the run did. `unreachable` is set when no command could be sent at all (the host is not there)."""

    result: ApplyResult | None
    #: Plan entries that cannot be sent, each with why; nothing was sent when this is not empty.
    problems: tuple[str, ...] = ()
    #: The reply that ended the run early, or that showed there was no host to talk to.
    stopped_by: HostControlReply | None = None
    unsent: int = 0
    #: Changes whose command was taken by the host without an outcome in time: they may have run.
    unknown: int = 0

    @property
    def unreachable(self) -> bool:
        return self.result is None and not self.problems


class HostPlanApplier:
    def __init__(
        self, applier: PlanApplier, host: IHostControl, plans: IAppliedPlanStore
    ) -> None:
        self._applier = applier
        self._host = host
        self._plans = plans

    def run(
        self, plan: BotPlanDocument, prune: PrunePolicy, wait_s: float
    ) -> HostApplyRun:
        preview = self._applier.preview(plan, prune)
        diff = preview.diff
        entries = _entries_of(diff)
        if isinstance(entries, tuple):
            return HostApplyRun(None, problems=entries)
        wishes = self._recorded_wishes()
        outcomes: dict[int, ChangeOutcome] = {}
        notes = list(preview.notes)
        stopped: HostControlReply | None = None
        wishes_unsent = 0
        first = True
        for change, request in _requests_of(diff, entries, wishes):
            if request is None:
                outcomes[id(change)] = _local_outcome(change)
                continue
            if (
                request.action is HostControlAction.UNPLAN
                and change.action is not ChangeAction.DELETE
            ):
                # The change is reported as the comparison said (kept, blocked, not pruned); the row is a side effect.
                outcomes.setdefault(id(change), _local_outcome(change))
            if stopped is not None:
                if request.action is HostControlAction.UNPLAN:
                    wishes_unsent += 1
                    notes.append(_wish_not_removed(request, "not sent"))
                continue
            reply = self._host.send(request, wait_s)
            if reply.status in _NOT_DELIVERED and first:
                return HostApplyRun(None, stopped_by=reply)
            first = False
            if reply.status in _NOT_DELIVERED or reply.status is _UNKNOWN:
                stopped = reply
            self._record(change, request, reply, outcomes, notes)
        everything = tuple(
            outcomes.get(id(c)) or _unsent(c, stopped) for c in diff.changes
        )
        unsent = wishes_unsent + sum(
            1 for o in everything if o.message.startswith("not sent")
        )
        unknown = sum(1 for o in everything if o.message.startswith("sent, "))
        result = ApplyResult(diff, everything, tuple(notes))
        return HostApplyRun(result, stopped_by=stopped, unsent=unsent, unknown=unknown)

    def _recorded_wishes(self) -> frozenset[str]:
        try:
            record = self._plans.read()
        except AppliedPlanUnreadableError:
            return frozenset()
        return frozenset(row.bot_id for row in record.bots) if record else frozenset()

    @staticmethod
    def _record(
        change: PlanChange,
        request: HostControlRequest,
        reply: HostControlReply,
        outcomes: dict[int, ChangeOutcome],
        notes: list[str],
    ) -> None:
        if request.action is HostControlAction.UNPLAN:
            if reply.status is not HostControlStatus.DONE:
                notes.append(_wish_not_removed(request, reply.message))
                if change.action is not ChangeAction.DELETE:
                    outcomes[id(change)] = ChangeOutcome(
                        change,
                        False,
                        f"its wish could not be removed from the applied plan: {reply.message}",
                        change.bot_id,
                    )
            return
        outcomes[id(change)] = _outcome_of_reply(change, reply)


def _outcome_of_reply(change: PlanChange, reply: HostControlReply) -> ChangeOutcome:
    if reply.status is HostControlStatus.DONE:
        return ChangeOutcome(change, True, reply.message, reply.bot_id or change.bot_id)
    if reply.status is _UNKNOWN:
        words = f"sent, outcome unknown: {reply.message} Read `bot list` before applying again"
    else:
        words = f"the host did not carry it out: {reply.message}"
    return ChangeOutcome(change, False, words, change.bot_id)


def _wish_not_removed(request: HostControlRequest, why: str) -> str:
    return (
        f"the wish of bot {request.bot_id} was not removed from the applied plan ({why}): "
        "`run --start-planned` would still act on it"
    )


def _entries_of(diff: PlanDiff) -> dict[int, NewBotEntry] | tuple[str, ...]:
    """The wire form of every plan entry, or why some cannot be sent (all listed; nothing is sent then)."""
    entries: dict[int, NewBotEntry] = {}
    problems: list[str] = []
    for change in diff.changes:
        if change.planned is None:
            continue
        try:
            entries[id(change)] = _entry_of(change.planned)
        except ValueError as invalid:
            problems.append(f"{change.name} on {change.venue.value}: {invalid}")
    return tuple(problems) if problems else entries


def _entry_of(planned: PlannedBot) -> NewBotEntry:
    return NewBotEntry(
        planned.name,
        planned.kind,
        planned.venue.value,
        planned.symbol,
        tuple(ParameterSetting(k, v) for k, v in planned.params.items()),
    )


def _requests_of(
    diff: PlanDiff, entries: dict[int, NewBotEntry], wishes: frozenset[str]
) -> list[tuple[PlanChange, HostControlRequest | None]]:
    """Entries first, then every wish that gets no fresh row, then the deletes: a delete is the last thing done.

    A wish gets no fresh row when the plan does not name its bot (pruned or not) or names it in an entry the
    lifecycle table blocks; an offline apply writes a row only for an entry it carried out. The `unplan` goes
    before the `delete`, so a delete the host refuses (exposure left) still leaves no wish behind.
    """
    named: list[tuple[PlanChange, HostControlRequest | None]] = []
    forgets: list[tuple[PlanChange, HostControlRequest | None]] = []
    deletes: list[tuple[PlanChange, HostControlRequest | None]] = []
    for change in diff.changes:
        named_entry = change.planned is not None
        if named_entry:
            named.append((change, _apply_request(change, entries)))
        elif change.action is not ChangeAction.DELETE:
            named.append((change, None))
        gets_no_row = change.action is ChangeAction.BLOCKED or not named_entry
        if gets_no_row and change.bot_id and change.bot_id in wishes:
            forgets.append(
                (change, HostControlRequest(HostControlAction.UNPLAN, change.bot_id))
            )
        if change.action is ChangeAction.DELETE and change.bot_id and not named_entry:
            deletes.append(
                (change, HostControlRequest(HostControlAction.DELETE, change.bot_id))
            )
    return named + forgets + deletes


def _apply_request(
    change: PlanChange, entries: dict[int, NewBotEntry]
) -> HostControlRequest | None:
    if change.action is ChangeAction.BLOCKED or change.planned is None:
        return None
    return HostControlRequest(
        HostControlAction.APPLY_ENTRY,
        PLAN_SUBJECT,
        entry=entries[id(change)],
        desired_state=change.planned.desired_state.value,
    )


def _local_outcome(change: PlanChange) -> ChangeOutcome:
    """A change that needs no command: left as it is, or blocked by the lifecycle table (nothing is sent for it)."""
    return ChangeOutcome(
        change, change.action is not ChangeAction.BLOCKED, change.detail, change.bot_id
    )


def _unsent(change: PlanChange, stopped: HostControlReply | None) -> ChangeOutcome:
    why = stopped.message if stopped is not None else "no answer"
    return ChangeOutcome(
        change, False, f"not sent: the host stopped answering ({why})", change.bot_id
    )
