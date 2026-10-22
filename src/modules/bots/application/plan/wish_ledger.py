"""`EPIC-045C` - the applied-plan record, one wish at a time.

Offline, `bot apply` rewrites the record whole from the plan. Beside a running host the plan is carried
out entry by entry (`ApplyPlanEntryForHostCommandHandler`), so the record is changed a row at a time: a row is
set when an entry is applied and forgotten when the plan no longer names its bot or the bot is deleted.
After a complete run the record is the one an offline apply would have written (decision C6). The host is
the record's only writer; a record that cannot be read is replaced, as an offline apply replaces it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedBot,
    AppliedPlan,
    AppliedPlanUnreadableError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_applied_plan_store import (
    IAppliedPlanStore,
)


def previous_record(store: IAppliedPlanStore) -> AppliedPlan | None:
    """The record, or `None` when there is none or it cannot be read (then writing replaces it)."""
    try:
        return store.read()
    except AppliedPlanUnreadableError:
        return None


def set_wish(store: IAppliedPlanStore, wish: AppliedBot) -> None:
    """Record `wish` for its bot, replacing the bot's row; the file is written only if it changes."""
    before = previous_record(store)
    kept = tuple(
        row for row in (before.bots if before else ()) if row.bot_id != wish.bot_id
    )
    after = AppliedPlan((*kept, wish))
    if after != before:
        store.write(after)


def forget_wish(store: IAppliedPlanStore, bot_id: str) -> bool:
    """Drop the bot's row; `True` when there was one. A record that is absent or unreadable has none."""
    before = previous_record(store)
    if before is None or all(row.bot_id != bot_id for row in before.bots):
        return False
    store.write(AppliedPlan(tuple(row for row in before.bots if row.bot_id != bot_id)))
    return True
