"""A Futures bot's approach to liquidation becomes one warning (`EPIC-036B1`).

Reads `bots/contracts` only: `BotRiskChangedEvent`, published once per change of the guard's level
(`grid_risk_watch.py`, hysteresis included), `BotChangedEvent` to learn that a bot stopped or was
removed, and the one-bot `GetBotStatusReportQuery` for the bot's name.

  · `WARN` raises `LIQUIDATION_RISK` (WARNING) once, with the figures the exchange reported;
  · `SAFE` ends it, so the hub sends one "Recovered" - unless the warning is younger than the
    cool-down, when it stays open rather than leave a "Recovered" that a re-cross would make false;
    a still-open warning is told again by the next `WARN` after the cool-down;
  · the bot reaching `STOPPED` (its position closed) ends it with "Recovered"; a bot leaving the
    states the guard judges (halted, in error, awaiting recovery) or being removed ends it quietly,
    because the guard resets to SAFE without an event there;
  · `CRITICAL` raises nothing of its own: the bot halts at that distance and the halt is the alert
    (`BotAlertSource`); `UNKNOWN` raises nothing: the bot halts if it stays blind too long.

A `WarningLatch` (`defer_clear`) keeps a mark price that crosses the line again from sending a pair
each time (`EarlyWarningPolicy.liquidation_cooldown`). The distances are the bot's (`FuturesGridThresholds`);
this source holds no threshold of its own. Nothing in the alert is a key or a secret: the figures
are the mark and liquidation prices and their distance.

**Thread.** Risk events come from the bot's worker thread, `BotChangedEvent` from whichever thread
wrote the bot; one lock covers the latch and the hand-over to the hub, and the bot store is read
outside it. A write while no warning is open (every booked fill) reads nothing.

@par Extension cases
  · another early warning of a bot (margin low, once a reader exists) — a sibling handler here, with
    its own `WarningLatch`.
"""

from __future__ import annotations

import logging
import threading
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_subject import (
    subject_of,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.warning_latch import (
    WarningLatch,
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
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    DEFAULT_EARLY_WARNINGS,
    EarlyWarningPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusReport,
    GetBotStatusReportQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_risk_changed_event import (
    BotRiskChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.risk_state import RiskLevel

logger = logging.getLogger("App.Alerting")

#: `BotStatusEntry.state` of a bot whose position is closed and whose guard has ended.
_STOPPED = "STOPPED"
#: The states the liquidation guard judges (`PRICE_STALENESS_HALTS`, spelled as the report does).
_JUDGED = frozenset({"STARTING", "RUNNING", "PAUSED", "RECOVERING"})


class LiquidationAlertSource:
    def __init__(
        self,
        dispatcher: ICommandDispatcher,
        publisher: IAlertPublisher,
        clock: IAlertClock,
        policy: EarlyWarningPolicy = DEFAULT_EARLY_WARNINGS,
    ) -> None:
        self._dispatcher = dispatcher
        self._publisher = publisher
        self._clock = clock
        self._lock = threading.Lock()
        self._warnings = WarningLatch(policy.liquidation_cooldown, defer_clear=True)

    def on_risk_changed(self, event: BotRiskChangedEvent) -> None:
        if event.level is RiskLevel.SAFE:
            self._end(event.bot_id)
            return
        if event.level is not RiskLevel.WARN:
            return
        subject = self._subject(event.bot_id)
        # The lock covers the latch and the hand-over, so a raise and a clear from two threads
        # reach the hub in the order the latch decided (`publish` only records).
        with self._lock:
            now = self._clock.now()
            if not self._warnings.raise_(event.bot_id, now):
                logger.info(
                    "[alert-source] bot %s: liquidation warning held back (inside the cool-down)",
                    event.bot_id,
                )
                return
            self._publisher.publish(
                Alert.raised(
                    AlertKind.LIQUIDATION_RISK,
                    subject,
                    f"{label_of(AlertKind.LIQUIDATION_RISK)}: {subject.bot_name or subject.bot_id}",
                    _detail(event),
                    now,
                )
            )
        logger.info("[alert-source] bot %s: LIQUIDATION_RISK published", event.bot_id)

    def on_bot_changed(self, event: BotChangedEvent) -> None:
        """The guard judges a bot only in `_JUDGED`; it drops back to SAFE without a word in any
        other state, so a warning left open would hold back every later one. A stopped bot has no
        position and its warning ends with "Recovered"; a halted or paused-out bot's ends quietly
        (the halt is its own CRITICAL message)."""
        with self._lock:
            if not event.removed and not self._warnings.is_open(event.bot_id):
                return  # the usual write (a fill): no store read
        state = None if event.removed else self._state_of(event.bot_id)
        if state in _JUDGED:
            return
        if event.removed or state == _STOPPED:
            self._end(event.bot_id)
        with self._lock:
            self._warnings.forget(event.bot_id)

    def _end(self, bot_id: str) -> None:
        subject = self._subject(bot_id)
        with self._lock:
            now = self._clock.now()
            if not self._warnings.clear(bot_id, now):
                return
            self._publisher.condition_cleared(
                Alert.condition_key(AlertKind.LIQUIDATION_RISK, subject), now
            )

    def _subject(self, bot_id: str) -> AlertSubject:
        bots = self._report(bot_id).bots
        if bots:
            return subject_of(bots[0])
        return AlertSubject.bot(bot_id, "", "", "", "")

    def _state_of(self, bot_id: str) -> str | None:
        bots = self._report(bot_id).bots
        return bots[0].state if bots else None

    def _report(self, bot_id: str) -> BotStatusReport:
        query = GetBotStatusReportQuery(bot_id)
        return cast(
            BotStatusReport, self._dispatcher.dispatch(GetBotStatusReportQuery, query)
        )


def _detail(event: BotRiskChangedEvent) -> str:
    """The figures the exchange reported, the guard's own sentence, then what the owner can do."""
    figures = []
    if event.mark_price is not None:
        figures.append(f"mark price {event.mark_price}")
    if event.liquidation_price is not None:
        figures.append(f"liquidation price {event.liquidation_price}")
    if event.distance is not None:
        figures.append(f"distance {event.distance:.2%}")
    line = f"{event.symbol}: {', '.join(figures)}.\n" if figures else ""
    return (
        f"{line}{event.reason}.\n"
        "The bot keeps running and halts if the position gets closer. Add margin, "
        "reduce the position or stop the bot."
    )
