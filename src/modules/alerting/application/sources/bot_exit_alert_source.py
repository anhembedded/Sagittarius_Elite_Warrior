"""A bot's exit that has closed its position becomes one alert (`BOT-190`, `PRO-015` §2.3).

An anti-corruption layer like `BotFillAlertSource`: it reads `bots/contracts` only — the
`BotExitClosedEvent` the bot publishes after it booked the exit's last closing slice, and the
one-bot `GetBotStatusReportQuery` for the bot's name and venue.

**Why an event and not the bot's state.** The bot is STOPPED before the closing market slices fill,
and each slice is booked later, so a status report taken at STOPPED holds the position and its
mark-to-market, and none of the exit's fill price or fee. Only the bot knows when the last slice is
booked, so the figure here is the one it carries.

**Which exits are told.** Those whose reason is in `EXIT_ON_STOP` (stop loss, take profit, range
exit): the exits that were told at once as `STOP_LOSS_HIT` and the like. A stop the owner asked for,
a halt that closed a position, a protective stop: no message, as before.

**One message per run.** The key is the kind, the bot and the run's id, so the hub keeps two runs'
results apart and a repeat of one event is one message. INFO, so silent by default.

**Thread.** Runs on the bot's worker thread (the bus is synchronous). Nothing here waits on a
channel: `IAlertPublisher.publish` only records.
"""

from __future__ import annotations

import logging
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_exit_words import (
    EXIT_ON_STOP,
    closed_detail,
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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusReport,
    GetBotStatusReportQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_exit_closed_event import (
    BotExitClosedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    RunEarnings,
)

logger = logging.getLogger("App.Alerting")


class BotExitAlertSource:
    def __init__(
        self,
        dispatcher: ICommandDispatcher,
        publisher: IAlertPublisher,
        clock: IAlertClock,
    ) -> None:
        self._dispatcher = dispatcher
        self._publisher = publisher
        self._clock = clock

    def on_exit_closed(self, event: BotExitClosedEvent) -> None:
        exit_kind = EXIT_ON_STOP.get(event.reason)
        if exit_kind is None:
            return
        report = cast(
            BotStatusReport,
            self._dispatcher.dispatch(
                GetBotStatusReportQuery, GetBotStatusReportQuery(event.bot_id)
            ),
        )
        subject = (
            subject_of(report.bots[0])
            if report.bots
            else AlertSubject.bot(event.bot_id, "", "", "", "")
        )
        name = subject.bot_name or subject.bot_id
        earnings = RunEarnings(
            grid_profit=event.grid_profit,
            completed_cycles=event.completed_cycles,
            total_pnl=event.total_pnl,
            judged=True,
            unpriced_fees=event.unpriced_fees,
        )
        self._publisher.publish(
            Alert.raised(
                AlertKind.EXIT_CLOSED,
                subject,
                f"{label_of(AlertKind.EXIT_CLOSED)}: {name}",
                closed_detail(exit_kind, earnings),
                self._clock.now(),
                event.run_id,
            )
        )
        logger.info(
            "[alert-source] bot %s: %s closed its position, result published",
            event.bot_id,
            event.reason,
        )
