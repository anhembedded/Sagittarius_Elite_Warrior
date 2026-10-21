"""`IDeliveryRequeue` on the outbox file (`EPIC-036D5`).

A connection of its own, opened for the one call and closed after it: the owner presses Retry
failed rarely, so nothing is held open and there is nothing to close at shutdown. The file is
`SqliteOutbox`'s, which has made the schema and keeps it in WAL mode, so this write waits for the
outbox's own short transaction (the connection's busy timeout) and never reads a half-written one.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.outbox_row_codec import (
    stamp,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_delivery_requeue import (
    IDeliveryRequeue,
)


class SqliteDeliveryRequeue(IDeliveryRequeue):
    def __init__(self, path: Path) -> None:
        self._path = path

    def requeue_failed(self, cutoff: datetime, now: datetime) -> int:
        with closing(sqlite3.connect(self._path)) as db, db:
            cursor = db.execute(
                "UPDATE deliveries SET state = 'pending', attempts = 0, "
                "next_attempt_at = ?, reason = 'retried by the owner' "
                "WHERE state = 'failed' AND alert_id IN "
                "(SELECT alert_id FROM alerts WHERE at >= ?)",
                (stamp(now), stamp(cutoff)),
            )
            return cursor.rowcount
