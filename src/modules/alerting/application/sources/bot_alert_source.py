"""Bots' facts become alerts at the module's edge (`EPIC-036G`; widened by `EPIC-036B2`).

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

**The table.** Three kinds on the state alone: `HALTED` → `BOT_HALTED`, `ERROR` →
`BOT_ERROR`, a stop that gave up → `STOP_FAILED`. The reason can say more
(`bot_reason_routes.py`, `EPIC-036B2`): a rate limit, a rejected key and a storage pause are kinds of
their own, and a wait stalled on a quiet price feed is `PRICE_FEED_STALE`. A return to `RUNNING` ends
the halt, the error and those conditions and a bot reaching `STOPPED` ends the stop that gave up,
through `condition_cleared`, so the hub sends one "Recovered" and the next halt is a new alert.

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
  · a reason that is its own condition — one row in `REASON_ROUTES`;
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
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_reason_routes import (
    own_route_on_entry,
    reason_line,
    stalled_route,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_subject import (
    subject_of,
    subject_or_bare,
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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_range_entered_event import (
    BotRangeEnteredEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_recovery_stalled_event import (
    BotRecoveryStalledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_stop_gave_up_event import (
    BotStopGaveUpEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.planned_bot_not_started_event import (
    PlannedBotNotStartedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    plain_price,
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
            AlertKind.RATE_LIMITED,
            AlertKind.KEY_REJECTED,
            AlertKind.STORAGE_FAILURE,
            AlertKind.PRICE_FEED_STALE,
        ),
        # A halted bot resumed flat with the price outside its range waits, holding nothing: its
        # halt, error and stalled-wait conditions are over (`EPIC-044B`). The conditions with a
        # route of their own (a quiet feed, a storage failure, the exchange's pause, a rejected
        # key) stay open until RUNNING: the wait places no order and reads no stream of its own,
        # so it proves none of them mended (`EPIC-044C`, review round 1).
        "AWAITING_RANGE": (
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
        subject = subject_or_bare(entry, event.bot_id)
        reason = entry.reason if entry is not None else ""
        detail = (
            f"The stop gave up after {event.retries} automatic retries and the bot "
            "is still STOPPING: orders it placed may still be open on the exchange. "
            f"Press Stop to try again.\n{reason_line(reason)}"
        )
        self._publish(AlertKind.STOP_FAILED, subject, detail)

    def on_recovery_stalled(self, event: BotRecoveryStalledEvent) -> None:
        """`EPIC-042` D11: a bot that waits to recover is silent on entry; this is its one alert."""
        entry = self._entry(event.bot_id)
        subject = subject_or_bare(entry, event.bot_id)
        minutes = event.waited_s // 60
        route = stalled_route(event.reason)
        if route is not None and route.kind is not None:
            # `EPIC-036B2`: a wait on a quiet price feed or an exchange pause is its own
            # condition, which the hub can group across bots and hide behind a venue outage.
            detail = f"{route.text} It has waited {minutes} minute(s).\n"
            self._publish(route.kind, subject, detail + reason_line(event.reason))
            return
        detail = (
            f"The bot has waited {minutes} minute(s) to recover and is still "
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
        subject = subject_or_bare(entry, event.bot_id)
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
        subject = subject_or_bare(entry, event.bot_id)
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

    def on_range_entered(self, event: BotRangeEnteredEvent) -> None:
        """`EPIC-044C` (ADR 044 D10): a bot that waited for its range has entered it and laid its
        ladder. Told once per entry; a bot that starts inside its range is not a wait that ended."""
        subject = subject_or_bare(self._entry(event.bot_id), event.bot_id)
        detail = (
            f"The price {plain_price(event.price)} entered the range "
            f"{plain_price(event.lower)}-{plain_price(event.upper)}"
            f"{_trigger_met(event)}. "
            f"The bot laid {event.orders} order(s) and is running."
        )
        self._publish(AlertKind.BOT_RANGE_ENTERED, subject, detail)

    def on_planned_bot_not_started(self, event: PlannedBotNotStartedEvent) -> None:
        """`EPIC-045F` (ADR 045 D7): the host skipped a planned mainnet bot it was not told to
        confirm, and runs the rest. Without this the bot would just sit DRAFT or STOPPED, silently."""
        subject = subject_or_bare(self._entry(event.bot_id), event.bot_id)
        detail = (
            f"{event.reason}\nThe other bots of the plan were started. Start this one with "
            f"`bot start {event.bot_id} --confirm-venue {event.venue}`."
        )
        self._publish(AlertKind.PLANNED_BOT_NOT_STARTED, subject, detail)

    def on_protective_stop(self, event: BotProtectiveStopEvent) -> None:
        """`BOT-189`: the stop standing on the exchange ran, so the position is closed."""
        if event.change is not ProtectiveStopChange.TRIGGERED:
            return
        subject = subject_or_bare(self._entry(event.bot_id), event.bot_id)
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
        own = own_route_on_entry(entry.state, entry.reason)
        if own is not None and own.kind is not None:
            # A reason that is its own condition: a fixed sentence, never the bot's detail, which
            # carries the failure text of a request or of the disk (`bot_reason_routes`).
            detail = f"{own.text}\n{reason_line(entry.reason)}"
            self._publish(own.kind, subject_of(entry), detail)
            return
        kind = ALERT_ON_ENTRY.get(entry.state)
        if kind is None:
            return
        detail = (
            f"Was {previous or 'not yet seen'}.\n"
            f"{reason_line(entry.reason, entry.reason_detail)}"
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


def _trigger_met(event: BotRangeEnteredEvent) -> str:
    """`EPIC-046B` (ADR 046 D5): the trigger price the entry met, when the plan has one."""
    if event.trigger is None:
        return ""
    side = "at or below" if event.trigger_at_or_below else "at or above"
    return f", {side} its trigger price {plain_price(event.trigger)}"
