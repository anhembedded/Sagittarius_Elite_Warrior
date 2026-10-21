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
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_settings_source import (
    IAlertSettingsSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_outbox import IOutbox
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.outbox_records import (
    DeliveryRecord,
    HistoryEntry,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    SubjectScope,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)

#: A delivery in one of these states did not get through.
_NOT_THROUGH = frozenset({DeliveryState.FAILED, DeliveryState.EXPIRED})
APP_SUBJECT = "Application"


class OutboxAlertHistory(IAlertHistory):
    def __init__(
        self,
        outbox: IOutbox,
        catalog: IAlertChannelCatalog,
        settings: IAlertSettingsSource,
    ) -> None:
        self._outbox = outbox
        self._catalog = catalog
        self._settings = settings

    def read(self, limit: int) -> AlertHistoryReport:
        entries = self._outbox.history(limit)
        disabled = self._settings.current().disabled_channels
        return AlertHistoryReport(
            tuple(_row_of(entry) for entry in entries),
            tuple(
                self._health_of(channel_id, disabled)
                for channel_id in self._catalog.channel_ids()
            ),
        )

    def _health_of(self, channel_id: str, disabled: frozenset[str]) -> ChannelHealth:
        enabled = channel_id not in disabled
        newest = self._outbox.latest_real_delivery(channel_id)
        return ChannelHealth(
            channel_id,
            failing=enabled and newest is not None and _did_not_get_through(newest),
            waiting=self._outbox.pending_count(channel_id),
            enabled=enabled,
        )


def _did_not_get_through(delivery: DeliveryRecord) -> bool:
    """Failed or expired; or retrying after a real failed try. A delivery asked to wait (a rate
    limit, the channel's own pacing) is `RETRYING` with no attempt used, and is not a failure: a
    burst must not raise the notice."""
    if delivery.state in _NOT_THROUGH:
        return True
    return delivery.state is DeliveryState.RETRYING and delivery.attempts >= 1


def _row_of(entry: HistoryEntry) -> AlertHistoryRow:
    alert = entry.record.alert
    return AlertHistoryRow(
        entry.record.alert_id,
        alert.at,
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
