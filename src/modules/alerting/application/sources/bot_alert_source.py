"""Bots' facts become alerts at the module's edge (`EPIC-036G`; widened by `EPIC-036B`).

An anti-corruption layer: the source reads `bots/contracts` only — the
`BotChangedEvent` the bot store publishes after every write, the
`BotStopGaveUpEvent` a stop publishes when its retries are used up, and the
one-bot `GetBotStatusReportQuery` — and speaks the alerting vocabulary.

**An alert on the entry into a state, not on its being.** The source remembers
each bot's last state; a write that leaves the state as it was (a fill booked, a
reason edited) is not a second alert. At boot it seeds that memory from the
bots' report without alerting, so a restart does not re-alert a bot that an
earlier run already reported halted.

**The skeleton's table.** Three kinds: `HALTED` → `BOT_HALTED`, `ERROR` →
`BOT_ERROR`, a stop that gave up → `STOP_FAILED`. A return to `RUNNING` ends the
first two conditions and a bot reaching `STOPPED` ends the third, through
`condition_cleared`, so the hub sends one "Recovered" and the next halt is a new
alert. `EPIC-036B` grows the table to every (state, reason) pair with a test
that each reason is mapped or ignored on purpose.

**Thread.** Handlers run on whichever thread wrote the bot (the bus is
synchronous); one lock covers the read of the bot, the compare with its last
state and the alert, so two writers of one bot (its worker thread and the UI)
cannot leave an older read recorded over a newer state (review of PR #537). The
read is a local query of the bot store, which publishes only after it releases
its own lock, so holding this one over it cannot deadlock. Nothing here waits on
a channel: `IAlertPublisher.publish` only records.

**A stop that gives up twice is told twice.** Its key is the same, but the hub's
dedup window for a CRITICAL is one minute (`NoisePolicy`) and a round of stop
retries lasts longer than that (`STOP_RETRY_DELAYS`, about nine minutes), so the
second round's give-up is a new alert, not a count on the first.

@par Extension cases
  · another state worth an alert — one entry in `ALERT_ON_ENTRY`;
  · a new bot kind — nothing: the source reads the kind-neutral contract;
  · a source for another module (`StreamAlertSource`, `SystemAlertSource`,
    `EPIC-036B`) — a file beside this one, subscribed in `module.boot()`.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Mapping
from types import MappingProxyType
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_publisher import (
    IAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_catalog import (
    label_of,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
    BotStatusReport,
    GetBotStatusReportQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_stop_gave_up_event import (
    BotStopGaveUpEvent,
)

logger = logging.getLogger("App.Alerting")

#: A lifecycle state's value (as `BotStatusEntry.state` spells it) whose entry is
#: an alert of this kind.
ALERT_ON_ENTRY: Mapping[str, AlertKind] = MappingProxyType(
    {"HALTED": AlertKind.BOT_HALTED, "ERROR": AlertKind.BOT_ERROR}
)

#: A state whose entry ends these conditions.
CLEARED_ON_ENTRY: Mapping[str, tuple[AlertKind, ...]] = MappingProxyType(
    {
        "RUNNING": (AlertKind.BOT_HALTED, AlertKind.BOT_ERROR),
        "STOPPED": (AlertKind.STOP_FAILED,),
    }
)


class BotAlertSource:
    def __init__(
        self,
        dispatcher: ICommandDispatcher,
        publisher: IAlertPublisher,
        clock: IAlertClock,
    ) -> None:
        self._dispatcher = dispatcher
        self._publisher = publisher
        self._clock = clock
        self._lock = threading.Lock()
        self._states: dict[str, str] = {}

    def seed(self) -> None:
        """Remember every bot's state as it is now, without alerting. A state a
        handler already recorded is kept: it is newer than this read."""
        report = self._report(GetBotStatusReportQuery())
        with self._lock:
            for entry in report.bots:
                self._states.setdefault(entry.bot_id, entry.state)
            known = len(self._states)
        logger.info(
            "[alert-source] watching %d bot(s); an alert on entering %s and when a stop gives up",
            known,
            ", ".join(ALERT_ON_ENTRY),
        )

    def on_bot_changed(self, event: BotChangedEvent) -> None:
        if event.removed:
            with self._lock:
                self._states.pop(event.bot_id, None)
            return
        with self._lock:
            # The read is inside the lock: two writers of one bot (its worker and
            # the UI) must not let an older read overwrite a newer state.
            entry = self._entry(event.bot_id)
            if entry is None:
                return
            previous = self._states.get(entry.bot_id)
            self._states[entry.bot_id] = entry.state
            if previous == entry.state:
                return
            self._alert_on_entry(entry, previous)
            self._clear_on_entry(entry)

    def on_stop_gave_up(self, event: BotStopGaveUpEvent) -> None:
        entry = self._entry(event.bot_id)
        subject = (
            _subject_of(entry)
            if entry is not None
            else AlertSubject.bot(event.bot_id, "", "", "", "")
        )
        reason = entry.reason if entry is not None else ""
        detail = (
            f"The stop gave up after {event.retries} automatic retries and the bot "
            "is still STOPPING: orders it placed may still be open on the exchange. "
            f"Press Stop to try again.\n{_reason_line(reason)}"
        )
        self._publish(AlertKind.STOP_FAILED, subject, detail)

    def _alert_on_entry(self, entry: BotStatusEntry, previous: str | None) -> None:
        kind = ALERT_ON_ENTRY.get(entry.state)
        if kind is None:
            return
        detail = f"Was {previous or 'not yet seen'}.\n{_reason_line(entry.reason)}"
        self._publish(kind, _subject_of(entry), detail)

    def _clear_on_entry(self, entry: BotStatusEntry) -> None:
        subject = _subject_of(entry)
        now = self._clock.now()
        for kind in CLEARED_ON_ENTRY.get(entry.state, ()):
            self._publisher.condition_cleared(Alert.condition_key(kind, subject), now)

    def _publish(self, kind: AlertKind, subject: AlertSubject, detail: str) -> None:
        name = subject.bot_name or subject.bot_id
        alert = Alert.raised(
            kind, subject, f"{label_of(kind)}: {name}", detail, self._clock.now()
        )
        self._publisher.publish(alert)
        logger.info("[alert-source] bot %s: %s published", subject.bot_id, kind.name)

    def _entry(self, bot_id: str) -> BotStatusEntry | None:
        bots = self._report(GetBotStatusReportQuery(bot_id)).bots
        return bots[0] if bots else None

    def _report(self, query: GetBotStatusReportQuery) -> BotStatusReport:
        return cast(
            BotStatusReport, self._dispatcher.dispatch(GetBotStatusReportQuery, query)
        )


def _subject_of(entry: BotStatusEntry) -> AlertSubject:
    return AlertSubject.bot(
        entry.bot_id, entry.name, entry.kind, entry.venue, entry.symbol
    )


def _reason_line(reason: str) -> str:
    return f"Reason: {reason}" if reason else "No reason recorded."
