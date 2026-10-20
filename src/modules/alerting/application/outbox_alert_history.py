"""`IAlertHistory` over the outbox and the channels this run has (`EPIC-036D2`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.alert_history_report import (
    AlertHistoryReport,
    AlertHistoryRow,
    ChannelHealth,
    ChannelOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel_catalog import (
    IAlertChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_history import (
    IAlertHistory,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_outbox import IOutbox
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.outbox_records import (
    HistoryEntry,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    SubjectScope,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)

#: A delivery in one of these states did not get through (yet).
_NOT_THROUGH = frozenset(
    {DeliveryState.RETRYING, DeliveryState.FAILED, DeliveryState.EXPIRED}
)
APP_SUBJECT = "Application"


class OutboxAlertHistory(IAlertHistory):
    def __init__(self, outbox: IOutbox, catalog: IAlertChannelCatalog) -> None:
        self._outbox = outbox
        self._catalog = catalog

    def read(self, limit: int) -> AlertHistoryReport:
        entries = self._outbox.history(limit)
        return AlertHistoryReport(
            tuple(_row_of(entry) for entry in entries),
            tuple(
                self._health_of(channel_id, entries)
                for channel_id in self._catalog.channel_ids()
            ),
        )

    def _health_of(
        self, channel_id: str, entries: tuple[HistoryEntry, ...]
    ) -> ChannelHealth:
        newest = _newest_delivery_state(channel_id, entries)
        return ChannelHealth(
            channel_id,
            failing=newest in _NOT_THROUGH,
            waiting=self._outbox.pending_count(channel_id),
        )


def _newest_delivery_state(
    channel_id: str, entries: tuple[HistoryEntry, ...]
) -> DeliveryState | None:
    """Entries are newest first, so the first delivery found on the channel is its newest.
    A dropped or still-pending delivery says nothing about whether the channel works, so
    the search goes on past it."""
    for entry in entries:
        for delivery in entry.deliveries:
            if delivery.channel_id == channel_id and delivery.state not in (
                DeliveryState.PENDING,
                DeliveryState.DROPPED,
            ):
                return delivery.state
    return None


def _row_of(entry: HistoryEntry) -> AlertHistoryRow:
    alert = entry.record.alert
    return AlertHistoryRow(
        entry.record.alert_id,
        entry.record.last_at,
        alert.kind,
        alert.severity,
        _subject_text(
            alert.subject.scope,
            alert.subject.bot_name or alert.subject.bot_id,
            alert.subject.venue,
        ),
        alert.title,
        entry.record.count,
        tuple(
            ChannelOutcome(d.channel_id, d.state, d.attempts) for d in entry.deliveries
        ),
    )


def _subject_text(scope: SubjectScope, bot: str, venue: str) -> str:
    if scope is SubjectScope.BOT:
        return bot
    if scope is SubjectScope.VENUE:
        return venue
    return APP_SUBJECT
