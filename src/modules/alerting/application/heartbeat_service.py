"""The owner hears from the bots on a schedule (`EPIC-036E`).

**Heartbeat.** An INFO message every `AlertSettings.heartbeat_every` the owner chose (`EPIC-036D9`), else
`HeartbeatPolicy.heartbeat_every` (N4: six hours) saying the
app is up and what its bots are doing: each active bot's state, reason and resting orders, and
the `health` snapshot of `EPIC-035W` verbatim once that task fills it. It reads the bots'
status report (`GetBotStatusReportQuery`), the model the Bots tab and `status` read, so the
message and the screen cannot disagree; nothing is recomputed here. A report that cannot be read
is still a heartbeat, one that says so (and the run log holds the error): a missing message would
look like a dead app. It obeys quiet hours like any INFO alert.

**Daily summary.** One `DAILY_SUMMARY` a day, after `HeartbeatPolicy.summary_at` (UTC): the bots
by state, each run's earnings as its record has them, and the alerts of the last day by kind,
counted exactly by the outbox. It is the one INFO alert quiet hours do not hold
(`QuietHoursHold.holds`): held, it would reach the owner as a title in the digest of held alerts
and never as the summary. The digest is also a `DAILY_SUMMARY`; its key carries the instant it
was released and this one's the date, so neither swallows the other.

**Not the dead man's switch.** A heartbeat in Discord helps only if the owner notices its
absence; an app that dies cannot send it. `DeadMansSwitch` (`EPIC-036E1`) is what tells the owner
that.

**Survives a restart.** When the last heartbeat was sent and whether a day's summary exists are
read from the outbox (`IOutbox.latest_alert_at`, `has_alert_keyed`), so a crash loop sends one
heartbeat per interval and not one per start, whatever else was stored since. A summary is never
sent late after a restart: an app started after the day's time has missed that day's, and the
next is tomorrow's.

Runs on the housekeeping thread (`ThreadedDeliveryHost`): publishing only records, so it never
waits on a channel.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.heartbeat_text import (
    heartbeat_text,
    summary_text,
    unreadable_report_text,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_publisher import (
    IAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_settings_source import (
    IAlertSettingsSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_outbox import IOutbox
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_catalog import (
    label_of,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    DEFAULT_HEARTBEAT,
    HeartbeatPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusReport,
    GetBotStatusReportQuery,
)

logger = logging.getLogger("App.Alerting")


class HeartbeatService:
    def __init__(
        self,
        dispatcher: ICommandDispatcher,
        publisher: IAlertPublisher,
        outbox: IOutbox,
        clock: IAlertClock,
        settings: IAlertSettingsSource,
        policy: HeartbeatPolicy = DEFAULT_HEARTBEAT,
    ) -> None:
        self._dispatcher = dispatcher
        self._publisher = publisher
        self._outbox = outbox
        self._clock = clock
        self._settings = settings
        self._policy = policy
        self._primed = False
        self._last_heartbeat: datetime | None = None
        self._summary_days: set[str] = set()

    def tick(self) -> None:
        """Send what is due. Never raises: a scheduler that dies is a silent app."""
        try:
            self._tick()
        except Exception:
            logger.warning("[alert-heartbeat] pass failed", exc_info=True)

    def _tick(self) -> None:
        now = self._clock.now()
        if not self._primed:
            self._prime(now)
        if self._heartbeat_due(now):
            self._last_heartbeat = now
            self._send_heartbeat(now)
        day = f"{now:%Y-%m-%d}"
        if now.time() >= self._policy.summary_at and day not in self._summary_days:
            self._summary_days.add(day)
            if not self._outbox.has_alert_keyed(_summary_key(day)):
                self._send_summary(now, day)

    def _prime(self, now: datetime) -> None:
        self._primed = True
        self._last_heartbeat = self._outbox.latest_alert_at(AlertKind.HEARTBEAT)
        if now.time() >= self._policy.summary_at:
            # Started after today's time: that summary is missed, not sent late (the way an
            # alert past its expiry is, N2), and a restart cannot send one twice.
            self._summary_days.add(f"{now:%Y-%m-%d}")

    def _heartbeat_due(self, now: datetime) -> bool:
        last = self._last_heartbeat
        every = self._settings.current().heartbeat_every or self._policy.heartbeat_every
        return last is None or now - last >= every

    def _send_heartbeat(self, now: datetime) -> None:
        try:
            report = self._report()
        except Exception as error:
            logger.warning(
                "[alert-heartbeat] the bots' state could not be read for the heartbeat",
                exc_info=True,
            )
            detail = unreadable_report_text(error)
            title = f"{label_of(AlertKind.HEARTBEAT)}: bots unreadable"
        else:
            detail = heartbeat_text(report)
            title = f"{label_of(AlertKind.HEARTBEAT)}: {len(report.bots)} bot(s)"
        self._publisher.publish(
            Alert.raised(
                AlertKind.HEARTBEAT,
                AlertSubject.app(),
                title,
                detail,
                now,
                reason=now.isoformat(),
            )
        )
        logger.info("[alert-heartbeat] HEARTBEAT published")

    def _send_summary(self, now: datetime, day: str) -> None:
        try:
            detail = summary_text(
                self._report(),
                self._outbox.alert_counts_since(now - self._policy.summary_window),
                self._policy.summary_window,
            )
        except Exception as error:
            logger.warning(
                "[alert-heartbeat] the daily summary could not be built", exc_info=True
            )
            detail = unreadable_report_text(error)
        self._publisher.publish(
            Alert.raised(
                AlertKind.DAILY_SUMMARY,
                AlertSubject.app(),
                f"Daily summary {day}",
                detail,
                now,
                reason=f"daily-{day}",
            )
        )
        logger.info("[alert-heartbeat] DAILY_SUMMARY published for %s", day)

    def _report(self) -> BotStatusReport:
        return cast(
            BotStatusReport,
            self._dispatcher.dispatch(
                GetBotStatusReportQuery, GetBotStatusReportQuery()
            ),
        )


def _summary_key(day: str) -> str:
    return Alert.condition_key(
        AlertKind.DAILY_SUMMARY, AlertSubject.app(), f"daily-{day}"
    )
