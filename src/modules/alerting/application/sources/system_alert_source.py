"""The app's own failures become one `APP_FAILURE` alert (`EPIC-036B`).

Replaces `NotificationEventHandler`'s Telegram path (`BOT-018`). The shell hears the failure
(a background task that died, a failed bulk sync, a UI slot that raised), normalises its text
once in `system_error_report.py` and calls `report_failure`; this source turns it into the
alerting vocabulary.

**One condition per source.** The dedup key is kind + the app + the source's name, so a task
that fails in a loop is one record with a counter (the hub's own dedup), not the old handler's
"drop an identical repeat of the very last message". A second task failing at the same time is
a separate condition and is told.

**Never breaks the publisher.** The caller is a worker thread's failure path or a UI slot's;
a publish that raises (a locked outbox) is logged and swallowed.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_publisher import (
    IAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_system_failure_reporter import (
    ISystemFailureReporter,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_catalog import (
    label_of,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)

logger = logging.getLogger("App.Alerting")


class SystemAlertSource(ISystemFailureReporter):
    def __init__(self, publisher: IAlertPublisher, clock: IAlertClock) -> None:
        self._publisher = publisher
        self._clock = clock

    def report_failure(self, source: str, summary: str) -> None:
        try:
            self._publisher.publish(
                Alert.raised(
                    AlertKind.APP_FAILURE,
                    AlertSubject.app(),
                    f"{label_of(AlertKind.APP_FAILURE)}: {source}",
                    summary,
                    self._clock.now(),
                    reason=source,
                )
            )
        except Exception:
            logger.warning(
                "[alert-source] APP_FAILURE from %s was not published",
                source,
                exc_info=True,
            )
            return
        logger.info("[alert-source] app failure from %s: APP_FAILURE published", source)
