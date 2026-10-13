"""Rows of the outbox to domain objects and back.

Times are stored as UTC ISO-8601 text with microseconds, a fixed width form whose
text order is its time order, so SQL can compare and sort them.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.outbox_records import (
    AlertRecord,
    DeliveryRecord,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
    SubjectScope,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity

#: The queries whose columns `alert_from_row`, `alert_record_from_row` and
#: `delivery_from_row` read, in this order. Whole literals, next to the readers
#: that depend on their column order: assembling SQL from pieces is what the
#: injection rule (S608) exists to catch, and these have no input in them.
DUE_QUERY = (
    "SELECT d.delivery_id, d.alert_id, d.channel_id, d.loudness, d.state, "
    "d.attempts, d.next_attempt_at, d.reason, "
    "a.alert_id, a.kind, a.severity, a.scope, a.bot_id, a.bot_name, a.bot_kind, "
    "a.venue, a.symbol, a.title, a.detail, a.at, a.dedup_key, a.recovery "
    "FROM deliveries d JOIN alerts a ON a.alert_id = d.alert_id "
    "WHERE d.channel_id = ? AND d.state IN ('pending', 'retrying') "
    "AND d.next_attempt_at <= ? "
    "ORDER BY a.severity DESC, d.delivery_id ASC LIMIT ?"
)

HISTORY_ALERTS_QUERY = (
    "SELECT a.alert_id, a.kind, a.severity, a.scope, a.bot_id, a.bot_name, "
    "a.bot_kind, a.venue, a.symbol, a.title, a.detail, a.at, a.dedup_key, "
    "a.recovery, a.count, a.last_at FROM alerts a ORDER BY a.alert_id DESC LIMIT ?"
)

HISTORY_DELIVERIES_QUERY = (
    "SELECT d.delivery_id, d.alert_id, d.channel_id, d.loudness, d.state, "
    "d.attempts, d.next_attempt_at, d.reason FROM deliveries d "
    "WHERE d.alert_id = ? ORDER BY d.delivery_id"
)

#: How many leading columns of a `DUE_QUERY` row are the delivery's.
DELIVERY_WIDTH = 8


def stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="microseconds")


def unstamp(text: str) -> datetime:
    return datetime.fromisoformat(text)


def alert_from_row(row: tuple[object, ...]) -> Alert:
    (_, kind, severity, scope, bot_id, bot_name, bot_kind, venue, symbol) = row[:9]
    title, detail, at, dedup_key, recovery = row[9:14]
    return Alert(
        AlertKind(str(kind)),
        Severity(int(str(severity))),
        AlertSubject(
            SubjectScope(str(scope)),
            str(bot_id),
            str(bot_name),
            str(bot_kind),
            str(venue),
            str(symbol),
        ),
        str(title),
        str(detail),
        unstamp(str(at)),
        str(dedup_key),
        bool(recovery),
    )


def alert_record_from_row(row: tuple[object, ...]) -> AlertRecord:
    return AlertRecord(
        int(str(row[0])), alert_from_row(row), int(str(row[14])), unstamp(str(row[15]))
    )


def delivery_from_row(row: tuple[object, ...] | sqlite3.Row) -> DeliveryRecord:
    delivery_id, alert_id, channel_id, loudness, state, attempts, next_at, reason = row
    return DeliveryRecord(
        int(str(delivery_id)),
        int(str(alert_id)),
        str(channel_id),
        Loudness(str(loudness)),
        DeliveryState(str(state)),
        int(str(attempts)),
        unstamp(str(next_at)),
        str(reason),
    )
