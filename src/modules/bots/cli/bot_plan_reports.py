"""`bot apply` and `bot export` as `Report`s (`EPIC-038I`).

The payload is the contract with scripts (`sew.bot-apply/1`, `sew.bot-export/1`): a key is
added within a version, never renamed. Neither holds a parameter value of a secret nature:
a plan holds none (`bot_plan_parser.py`), and a change's `detail` names parameters, not
credentials.
"""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.core.contracts.report import (
    JsonValue,
    Report,
    ReportCell,
    ReportRow,
    ReportSection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_applier import (
    ApplyResult,
    ChangeOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_change import (
    ChangeAction,
    PlanChange,
    PlanDiff,
)

APPLY_COMMAND = "bot-apply"
EXPORT_COMMAND = "bot-export"
SCHEMA_VERSION = 1

_ACTION_WIDTH = 8
_NAME_WIDTH = 24
_VENUE_WIDTH = 14
_ID_WIDTH = 8


def apply_report(
    diff: PlanDiff,
    result: ApplyResult | None,
    notes: Sequence[str],
) -> Report:
    """`result` is `None` for a dry run: nothing was done, so nothing is `done`."""
    outcomes = {id(o.change): o for o in result.outcomes} if result is not None else {}
    summary = {action.value: 0 for action in ChangeAction}
    for change in diff.changes:
        summary[change.action.value] += 1
    payload: dict[str, JsonValue] = {
        "dry_run": result is None,
        "has_changes": diff.has_changes,
        "changes": [_change_payload(c, outcomes.get(id(c))) for c in diff.changes],
        "summary": dict(summary),
        "notes": list(notes),
        "all_applied": result is not None and result.exit_ok,
    }
    return Report(
        APPLY_COMMAND, SCHEMA_VERSION, payload, _apply_layout(diff, result, notes)
    )


def export_report(output: str, count: int) -> Report:
    payload: dict[str, JsonValue] = {"output": output, "bots": count}
    layout = (
        ReportSection(None, (ReportRow.of(f"Wrote {count} bot(s) to {output}"),)),
    )
    return Report(EXPORT_COMMAND, SCHEMA_VERSION, payload, layout)


def _change_payload(
    change: PlanChange, outcome: ChangeOutcome | None
) -> dict[str, JsonValue]:
    """`bot_id` of a bot that was just created is the new bot's, so a script can find it."""
    return {
        "action": change.action.value,
        "name": change.name,
        "venue": change.venue.value,
        "bot_id": outcome.bot_id if outcome and outcome.bot_id else change.bot_id,
        "state": change.state,
        "desired_state": change.desired_after.value if change.desired_after else None,
        "detail": change.detail,
        "done": outcome.done if outcome is not None else False,
    }


def _apply_layout(
    diff: PlanDiff, result: ApplyResult | None, notes: Sequence[str]
) -> tuple[ReportSection, ...]:
    sections: list[ReportSection] = []
    if notes:
        sections.append(ReportSection("Notes", tuple(ReportRow.of(n) for n in notes)))
    if not diff.changes:
        sections.append(
            ReportSection(None, (ReportRow.of("No bots in the plan or the store."),))
        )
    elif not diff.has_changes and not diff.blocked:
        sections.append(ReportSection(None, (ReportRow.of("No changes."),)))
    if diff.changes:
        title = "Plan (dry run, nothing changed)" if result is None else "Plan applied"
        sections.append(ReportSection(title, tuple(_row(c) for c in diff.changes)))
    return tuple(sections)


def _row(change: PlanChange) -> ReportRow:
    return ReportRow(
        (
            ReportCell(change.action.value.upper(), _ACTION_WIDTH),
            ReportCell(change.name, _NAME_WIDTH),
            ReportCell(change.venue.value, _VENUE_WIDTH),
            ReportCell(change.bot_id or "-", _ID_WIDTH),
            ReportCell(change.detail),
        )
    )
