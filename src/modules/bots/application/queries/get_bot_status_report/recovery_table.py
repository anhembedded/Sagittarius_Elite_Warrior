"""`EPIC-042G` — a bot's effective halt-recovery table, as data for `bot show`.

The rows are `recovery_policy_of`'s, the function the director resolves a bot's policy with, so
the report cannot disagree with what the bot does (ADR 042 D15); nothing here merges layers.
"""

from __future__ import annotations

from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotRecoveryTable,
    RecoveryRuleLine,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
    UnknownBotKindError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    recovery_policy_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.recovery_ledger import (
    attempts_within,
)


def recovery_table_of(
    bot: BotSnapshot, kinds: IBotKindCatalog, now: datetime
) -> BotRecoveryTable | None:
    """What `bot` recovers from by itself, or `None` for a kind this build does not know."""
    try:
        kind = kinds.kind(bot.kind)
    except UnknownBotKindError:
        return None
    policy = recovery_policy_of(kind.recovery_layer(), bot.venue)
    return BotRecoveryTable(
        rules=tuple(
            RecoveryRuleLine(
                code=row.code,
                dwell_s=int(row.rule.dwell.total_seconds()),
                max_attempts=row.rule.max_attempts,
                window_s=int(row.rule.window.total_seconds()),
                stalled_after_s=int(row.rule.stalled_after.total_seconds()),
                decided_by=row.decided_by,
                attempts_used=attempts_within(
                    bot.recovery_attempts, row.rule.window, now
                ),
            )
            for row in policy.rows
        ),
        none_decided_by=policy.emptied_by,
    )
