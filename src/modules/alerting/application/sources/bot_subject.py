"""The alert subject of one bot, as the status report names it (shared by the bot sources)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
)


def subject_of(entry: BotStatusEntry) -> AlertSubject:
    return AlertSubject.bot(
        entry.bot_id, entry.name, entry.kind, entry.venue, entry.symbol
    )
