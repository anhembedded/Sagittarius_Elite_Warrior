"""Bots' facts become alerts at the module's edge (`EPIC-036G`; widened by `EPIC-036B`).

An anti-corruption layer: the source reads `bots/contracts` only — the
`BotChangedEvent` the bot store publishes after every write, the
`BotStopGaveUpEvent` a stop publishes when its retries are used up, the
`BotRecoveryStalledEvent` a bot waiting to recover publishes once, the
`BotAutoRecoveredEvent` of each automatic recovery (`EPIC-042`), and the
one-bot `GetBotStatusReportQuery` — and speaks the alerting vocabulary.

**An alert on the entry into a state, not on its being.** The source remembers
each bot's last state; a write that leaves the state as it was (a fill booked, a
reason edited) is not a second alert. At boot it seeds that memory from the
bots' report without alerting, so a restart does not re-alert a bot that an
earlier run already reported halted.

**A wait is silent on entry.** `AWAITING_RECOVERY` is not in `ALERT_ON_ENTRY`: most waits end
by themselves within minutes. The one alert is the stalled one, after the rule's `stalled_after`,
and it ends when the bot leaves the state.

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
from dataclasses import replace
from types import MappingProxyType
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_exit_words import (
    EXIT_ON_STOP,
    EXIT_SENTENCES,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_subject import (
    subject_of,
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
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
    BotStatusReport,
    GetBotStatusReportQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.account_loss_cap_tripped_event import (
    AccountLossCapTrippedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_auto_recovered_event import (
    BotAutoRecoveredEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_protective_stop_event import (
    BotProtectiveStopEvent,
    ProtectiveStopChange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_range_changed_event import (
    BotRangeChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_recovery_stalled_event import (
    BotRecoveryStalledEvent,
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

#: `RangePosition.value`s, as the range event spells them (alerting reads contracts, not `bots.domain`).
_INSIDE = "INSIDE"
_BELOW = "BELOW"

#: A state whose entry ends these conditions.
CLEARED_ON_ENTRY: Mapping[str, tuple[AlertKind, ...]] = MappingProxyType(
    {
        "RUNNING": (
            AlertKind.BOT_HALTED,
            AlertKind.BOT_ERROR,
            AlertKind.BOT_RECOVERY_STALLED,
        ),
        "HALTED": (AlertKind.BOT_RECOVERY_STALLED,),
        "ERROR": (AlertKind.BOT_RECOVERY_STALLED,),
        "STOPPED": (AlertKind.STOP_FAILED, AlertKind.BOT_RECOVERY_STALLED),
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
            self._alert_on_exit(entry)
            self._clear_on_entry(entry)

    def on_stop_gave_up(self, event: BotStopGaveUpEvent) -> None:
        entry = self._entry(event.bot_id)
        subject = (
            subject_of(entry)
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

    def on_account_loss_cap_tripped(self, event: AccountLossCapTrippedEvent) -> None:
        """`EPIC-026L`: the account-level loss cap tripped; the owner must hear it at once.

        About the whole host, not a bot, so its subject is the app. It has no recovery message: the
        owner's acknowledgement is the end of it, and a cap that trips again is a new alert.
        """
        figure = f" (cap {event.figure})" if event.figure else ""
        detail = (
            f"The account-level loss cap tripped{figure}: {event.detail}.\n"
            f"{event.bots_stopped} bot(s) are being stopped. No bot starts or resumes until you "
            "acknowledge it with `main.py bot loss-cap-ack` on the running host. A Spot bot keeps "
            "the coin it holds; a Futures bot's position is closed at market."
        )
        self._publisher.publish(
            Alert.raised(
                AlertKind.ACCOUNT_LOSS_CAP_TRIPPED,
                AlertSubject.app(),
                label_of(AlertKind.ACCOUNT_LOSS_CAP_TRIPPED),
                detail,
                self._clock.now(),
                reason=event.reason,
            )
        )
        logger.info(
            "[alert-source] account loss cap tripped (%s): alert published",
            event.reason,
        )

    def on_recovery_stalled(self, event: BotRecoveryStalledEvent) -> None:
        """`EPIC-042` D11: a bot that waits to recover is silent on entry; this is its one alert."""
        entry = self._entry(event.bot_id)
        subject = (
            subject_of(entry)
            if entry is not None
            else AlertSubject.bot(event.bot_id, "", "", "", "")
        )
        detail = (
            f"The bot has waited {event.waited_s // 60} minute(s) to recover and is still "
            "waiting, with its ladder off the exchange; it resumes by itself if the cause "
            "clears. Its stop loss and take profit are watched only while ticks arrive.\n"
            f"Reason: {event.reason}"
        )
        self._publish(AlertKind.BOT_RECOVERY_STALLED, subject, detail)

    def on_auto_recovered(self, event: BotAutoRecoveredEvent) -> None:
        """`EPIC-042` D1: each automatic recovery is told, with the budget it leaves.

        Keyed by the attempt, so a second recovery inside the dedup window is its own alert and
        not a count on the first.
        """
        entry = self._entry(event.bot_id)
        subject = (
            subject_of(entry)
            if entry is not None
            else AlertSubject.bot(event.bot_id, "", "", "", "")
        )
        left = max(event.max_attempts - event.attempt, 0)
        detail = (
            f"The bot was halted by a transient cause and resumed itself: attempt "
            f"{event.attempt} of {event.max_attempts} in the rolling window, {left} left. "
            "A fresh ladder was laid.\n"
            f"Reason: {event.reason}"
        )
        self._publish(
            AlertKind.BOT_AUTO_RECOVERED,
            subject,
            detail,
            reason=f"attempt-{event.attempt}",
        )

    def on_range_changed(self, event: BotRangeChangedEvent) -> None:
        """`BOT-189`: the price left the range of a bot that holds its orders (a bot that closes
        there is told by its stop, `EPIC-036B`'s `RANGE_EXIT`); its return is not told."""
        entry = self._entry(event.bot_id)
        subject = _subject_or_bare(entry, event.bot_id)
        if event.position.value == _INSIDE:
            # No "Recovered": a price that oscillates around a bound would send a pair for each
            # crossing, unbounded. The hub's window (15 min for a WARNING) keeps it to one message
            # per side in that time (locked by `test_a_price_that_flaps_at_the_edge_...`).
            return
        if event.closes:
            return
        word = "below" if event.position.value == _BELOW else "above"
        detail = (
            f"The price {event.price} is {word} the range {event.lower}-{event.upper}. "
            "The bot keeps its orders and waits; it trades again if the price returns."
        )
        self._publish(
            AlertKind.RANGE_EXIT, subject, detail, reason=event.position.value
        )

    def on_protective_stop(self, event: BotProtectiveStopEvent) -> None:
        """`BOT-189`: the stop standing on the exchange ran, so the position is closed."""
        if event.change is not ProtectiveStopChange.TRIGGERED:
            return
        subject = _subject_or_bare(self._entry(event.bot_id), event.bot_id)
        detail = (
            "The stop standing on the exchange ran and closed the position; "
            f"the bot stops.\n{event.detail}"
        )
        self._publish(AlertKind.STOP_LOSS_HIT, subject, detail, reason="exchange")

    def _alert_on_exit(self, entry: BotStatusEntry) -> None:
        kind = EXIT_ON_STOP.get(entry.reason) if entry.state == "STOPPING" else None
        if kind is None:
            return
        detail = (
            f"{EXIT_SENTENCES[kind]} ({entry.reason_detail or 'no detail recorded'}). "
            "The bot is closing its position at market and stopping."
        )
        alert = self._alert(kind, subject_of(entry), detail)
        if kind is AlertKind.RANGE_EXIT:
            # A bot closing its position is an exit the owner must hear (`PRO-015`); one that only
            # holds keeps the catalog's WARNING, which the owner may route loud.
            alert = replace(alert, severity=Severity.CRITICAL)
        self._send(alert)

    def _alert_on_entry(self, entry: BotStatusEntry, previous: str | None) -> None:
        kind = ALERT_ON_ENTRY.get(entry.state)
        if kind is None:
            return
        detail = (
            f"Was {previous or 'not yet seen'}.\n"
            f"{_reason_line(entry.reason, entry.reason_detail)}"
        )
        self._publish(kind, subject_of(entry), detail)

    def _clear_on_entry(self, entry: BotStatusEntry) -> None:
        subject = subject_of(entry)
        now = self._clock.now()
        for kind in CLEARED_ON_ENTRY.get(entry.state, ()):
            self._publisher.condition_cleared(Alert.condition_key(kind, subject), now)

    def _publish(
        self, kind: AlertKind, subject: AlertSubject, detail: str, reason: str = ""
    ) -> None:
        self._send(self._alert(kind, subject, detail, reason))

    def _alert(
        self, kind: AlertKind, subject: AlertSubject, detail: str, reason: str = ""
    ) -> Alert:
        name = subject.bot_name or subject.bot_id
        return Alert.raised(
            kind,
            subject,
            f"{label_of(kind)}: {name}",
            detail,
            self._clock.now(),
            reason,
        )

    def _send(self, alert: Alert) -> None:
        self._publisher.publish(alert)
        logger.info(
            "[alert-source] bot %s: %s published", alert.subject.bot_id, alert.kind.name
        )

    def _entry(self, bot_id: str) -> BotStatusEntry | None:
        bots = self._report(GetBotStatusReportQuery(bot_id)).bots
        return bots[0] if bots else None

    def _report(self, query: GetBotStatusReportQuery) -> BotStatusReport:
        return cast(
            BotStatusReport, self._dispatcher.dispatch(GetBotStatusReportQuery, query)
        )


def _subject_or_bare(entry: BotStatusEntry | None, bot_id: str) -> AlertSubject:
    """The bot's subject, or a bare one when the report no longer lists the bot."""
    if entry is not None:
        return subject_of(entry)
    return AlertSubject.bot(bot_id, "", "", "", "")


def _reason_line(reason: str, detail: str = "") -> str:
    """The `Reason:` line; the detail follows it when the bot wrote one (`EPIC-042D`: the
    sentence that says the automatic recoveries are used up lives only there)."""
    if not reason:
        return "No reason recorded."
    detail = detail.lstrip("; ")
    return f"Reason: {reason} ({detail})" if detail else f"Reason: {reason}"
