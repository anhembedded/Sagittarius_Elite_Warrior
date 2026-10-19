"""`IOutbox` on a SQLite file under `<data root>/state/` (N2).

One connection shared by every thread behind a lock; each public method is one
short transaction, so the lock is never held across a channel call. Autocommit
mode with explicit `BEGIN`, journal in WAL, so a process killed mid-write leaves
the last committed state, never a half-written one.

The file belongs to the writable copy only (`EPIC-035H`): the module opens it
from `boot()` and binds a null publisher for a read-only copy.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.outbox_row_codec import (
    DELIVERY_WIDTH,
    DUE_QUERY,
    HISTORY_ALERTS_QUERY,
    HISTORY_DELIVERIES_QUERY,
    alert_from_row,
    alert_record_from_row,
    delivery_from_row,
    stamp,
    unstamp,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_outbox import IOutbox
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.outbox_records import (
    DeliveryTarget,
    DeliveryUpdate,
    DueDelivery,
    HistoryEntry,
    OutboxBacklog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity

logger = logging.getLogger("App.Alerting")

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    alert_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT    NOT NULL,
    severity   INTEGER NOT NULL,
    scope      TEXT    NOT NULL,
    bot_id     TEXT    NOT NULL,
    bot_name   TEXT    NOT NULL,
    bot_kind   TEXT    NOT NULL,
    venue      TEXT    NOT NULL,
    symbol     TEXT    NOT NULL,
    title      TEXT    NOT NULL,
    detail     TEXT    NOT NULL,
    at         TEXT    NOT NULL,
    dedup_key  TEXT    NOT NULL,
    recovery   INTEGER NOT NULL,
    count      INTEGER NOT NULL,
    last_at    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS alerts_at ON alerts (at);
CREATE TABLE IF NOT EXISTS deliveries (
    delivery_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id        INTEGER NOT NULL REFERENCES alerts (alert_id) ON DELETE CASCADE,
    channel_id      TEXT    NOT NULL,
    loudness        TEXT    NOT NULL,
    state           TEXT    NOT NULL,
    attempts        INTEGER NOT NULL,
    next_attempt_at TEXT    NOT NULL,
    reason          TEXT    NOT NULL,
    created_at      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS deliveries_due
    ON deliveries (channel_id, state, next_attempt_at);
CREATE INDEX IF NOT EXISTS deliveries_alert ON deliveries (alert_id);
"""


class UnsupportedOutboxSchemaError(RuntimeError):
    """The file was written by a newer version; opening it could corrupt it."""


class SqliteOutbox(IOutbox):
    def __init__(self, path: Path) -> None:
        self._lock = threading.RLock()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        try:
            self._prepare()
        except Exception:
            self._db.close()
            raise
        logger.info("[alert-outbox] opened %s (schema %s)", path, SCHEMA_VERSION)

    def _prepare(self) -> None:
        found = int(self._db.execute("PRAGMA user_version").fetchone()[0])
        if found > SCHEMA_VERSION:
            raise UnsupportedOutboxSchemaError(
                f"The alert outbox has schema {found}; this version reads {SCHEMA_VERSION}"
            )
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript(_SCHEMA)
        self._db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield self._db
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            self._db.execute("COMMIT")

    def enqueue(
        self, alert: Alert, targets: Sequence[DeliveryTarget], now: datetime
    ) -> int:
        with self._transaction() as db:
            cursor = db.execute(
                "INSERT INTO alerts (kind, severity, scope, bot_id, bot_name, bot_kind, "
                "venue, symbol, title, detail, at, dedup_key, recovery, count, last_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (
                    alert.kind.value,
                    int(alert.severity),
                    alert.subject.scope.value,
                    alert.subject.bot_id,
                    alert.subject.bot_name,
                    alert.subject.bot_kind,
                    alert.subject.venue,
                    alert.subject.symbol,
                    alert.title,
                    alert.detail,
                    stamp(alert.at),
                    alert.dedup_key,
                    int(alert.recovery),
                    stamp(alert.at),
                ),
            )
            alert_id = int(cursor.lastrowid or 0)
            for target in targets:
                self._insert_delivery(db, alert_id, target, now)
        return alert_id

    def add_delivery(self, alert_id: int, target: DeliveryTarget, now: datetime) -> int:
        with self._transaction() as db:
            return self._insert_delivery(db, alert_id, target, now)

    @staticmethod
    def _insert_delivery(
        db: sqlite3.Connection, alert_id: int, target: DeliveryTarget, now: datetime
    ) -> int:
        reason = "no room in the queue" if target.state is DeliveryState.DROPPED else ""
        cursor = db.execute(
            "INSERT INTO deliveries (alert_id, channel_id, loudness, state, attempts, "
            "next_attempt_at, reason, created_at) VALUES (?, ?, ?, ?, 0, ?, ?, ?)",
            (
                alert_id,
                target.channel_id,
                target.loudness.value,
                target.state.value,
                stamp(now),
                reason,
                stamp(now),
            ),
        )
        return int(cursor.lastrowid or 0)

    def bump(self, alert_id: int, at: datetime) -> None:
        with self._transaction() as db:
            db.execute(
                "UPDATE alerts SET count = count + 1, last_at = ? WHERE alert_id = ?",
                (stamp(at), alert_id),
            )

    def channels_of(self, alert_id: int) -> frozenset[str]:
        with self._lock:
            rows = self._db.execute(
                "SELECT DISTINCT channel_id FROM deliveries WHERE alert_id = ?",
                (alert_id,),
            ).fetchall()
        return frozenset(str(row[0]) for row in rows)

    def due(
        self, channel_id: str, now: datetime, limit: int
    ) -> tuple[DueDelivery, ...]:
        with self._lock:
            rows = self._db.execute(
                DUE_QUERY, (channel_id, stamp(now), limit)
            ).fetchall()
        return tuple(
            DueDelivery(
                delivery_from_row(row[:DELIVERY_WIDTH]),
                alert_from_row(row[DELIVERY_WIDTH:]),
            )
            for row in rows
        )

    def mark(self, delivery_id: int, update: DeliveryUpdate) -> None:
        with self._transaction() as db:
            db.execute(
                "UPDATE deliveries SET state = ?, attempts = ?, next_attempt_at = ?, "
                "reason = ? WHERE delivery_id = ?",
                (
                    update.state.value,
                    update.attempts,
                    stamp(update.next_attempt_at),
                    update.reason,
                    delivery_id,
                ),
            )

    def expire_before(self, cutoff: datetime) -> int:
        with self._transaction() as db:
            cursor = db.execute(
                "UPDATE deliveries SET state = 'expired', "
                "reason = 'older than the expiry' "
                "WHERE state IN ('pending', 'retrying') AND alert_id IN "
                "(SELECT alert_id FROM alerts WHERE at < ?)",
                (stamp(cutoff),),
            )
        return cursor.rowcount

    def retry_horizon(self, channel_id: str) -> datetime | None:
        with self._lock:
            row = self._db.execute(
                "SELECT MAX(next_attempt_at) FROM deliveries "
                "WHERE channel_id = ? AND state = 'retrying'",
                (channel_id,),
            ).fetchone()
        return None if row[0] is None else unstamp(str(row[0]))

    def pending_count(self, channel_id: str) -> int:
        with self._lock:
            row = self._db.execute(
                "SELECT COUNT(*) FROM deliveries WHERE channel_id = ? "
                "AND state IN ('pending', 'retrying')",
                (channel_id,),
            ).fetchone()
        return int(row[0])

    def shed_lowest(self, channel_id: str, below: Severity) -> bool:
        with self._transaction() as db:
            row = db.execute(
                "SELECT d.delivery_id FROM deliveries d "
                "JOIN alerts a ON a.alert_id = d.alert_id "
                "WHERE d.channel_id = ? AND d.state IN ('pending', 'retrying') "
                "AND a.severity < ? "
                "ORDER BY a.severity ASC, d.delivery_id ASC LIMIT 1",
                (channel_id, int(below)),
            ).fetchone()
            if row is None:
                return False
            db.execute(
                "UPDATE deliveries SET state = 'dropped', reason = 'no room in the queue' "
                "WHERE delivery_id = ?",
                (row[0],),
            )
        return True

    def shed_surplus(self, channel_id: str, kind: AlertKind, keep: int) -> int:
        with self._transaction() as db:
            cursor = db.execute(
                "UPDATE deliveries SET state = 'dropped', reason = 'no room for fill messages' "
                "WHERE delivery_id IN (SELECT d.delivery_id FROM deliveries d "
                "JOIN alerts a ON a.alert_id = d.alert_id "
                "WHERE d.channel_id = ? AND d.state IN ('pending', 'retrying') "
                "AND a.kind = ? ORDER BY d.delivery_id DESC LIMIT -1 OFFSET ?)",
                (channel_id, kind.value, keep),
            )
        return cursor.rowcount

    def purge_finished_before(self, cutoff: datetime) -> int:
        with self._transaction() as db:
            cursor = db.execute(
                "DELETE FROM alerts WHERE last_at < ? AND NOT EXISTS "
                "(SELECT 1 FROM deliveries d WHERE d.alert_id = alerts.alert_id "
                "AND d.state IN ('pending', 'retrying'))",
                (stamp(cutoff),),
            )
        return cursor.rowcount

    def history(self, limit: int) -> tuple[HistoryEntry, ...]:
        with self._lock:
            alert_rows = self._db.execute(HISTORY_ALERTS_QUERY, (limit,)).fetchall()
            entries = []
            for row in alert_rows:
                delivery_rows = self._db.execute(
                    HISTORY_DELIVERIES_QUERY, (row[0],)
                ).fetchall()
                entries.append(
                    HistoryEntry(
                        alert_record_from_row(row),
                        tuple(delivery_from_row(d) for d in delivery_rows),
                    )
                )
        return tuple(entries)

    def backlog(self, now: datetime) -> OutboxBacklog:
        with self._lock:
            row = self._db.execute(
                "SELECT COUNT(*), MIN(created_at) FROM deliveries "
                "WHERE state IN ('pending', 'retrying')"
            ).fetchone()
        depth, oldest = int(row[0]), row[1]
        age: timedelta | None = None if oldest is None else now - unstamp(str(oldest))
        return OutboxBacklog(depth, age)

    def close(self) -> None:
        with self._lock:
            self._db.close()
