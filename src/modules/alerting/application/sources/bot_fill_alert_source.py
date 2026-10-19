"""A bot's filled orders become alerts at the module's edge (`BOT-189`, `PRO-015` phase 1).

An anti-corruption layer like `BotAlertSource`: it reads `bots/contracts` only — the
`BotOrderFilledEvent` the bot publishes after it counted a fill, and the one-bot
`GetBotStatusReportQuery` for the bot's name and venue — and speaks the alerting vocabulary.

**One message per order, nothing else decided here.** The event already is "this order filled
whole", so the source filters nothing and counts nothing; it words the message. The fill that closes
a grid cycle carries the cycle's net profit, the run's total and the number of cycles in the same
message. Who hears it, how loudly and whether the queue is full are the hub's (INFO, so silent by
default; a bot set to *Critical only* or *Off* sends none).

**The key is the order, with the bot.** `Alert.raised` keys by kind, subject and reason, and the reason
is the order's id: a repeat of one fill event inside the hub's window is one message, and two fills of
the same price are two. The hub's windows are in memory; what keeps a restart from sending a fill again
is that the bot counts a fill once, so it publishes it once (locked by the integration test).

**Thread.** Runs on the bot's worker thread (the bus is synchronous). Nothing here waits on a channel:
`IAlertPublisher.publish` only records.

@par Extension cases
  · another figure in the line (the fee, the fill's time) — a field on the event and one f-string here;
  · the same line for another kind of bot — nothing: the event is kind-neutral;
  · a digest of fills (a later proposal) — a second source beside this one, fed by the same event.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_order_filled_event import (
    BotOrderFilledEvent,
)

logger = logging.getLogger("App.Alerting")


class BotFillAlertSource:
    def __init__(
        self,
        dispatcher: ICommandDispatcher,
        publisher: IAlertPublisher,
        clock: IAlertClock,
    ) -> None:
        self._dispatcher = dispatcher
        self._publisher = publisher
        self._clock = clock

    def on_order_filled(self, event: BotOrderFilledEvent) -> None:
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
        alert = Alert.raised(
            AlertKind.ORDER_FILLED,
            subject,
            f"{label_of(AlertKind.ORDER_FILLED)}: {name}",
            fill_line(event, subject.symbol),
            self._clock.now(),
            event.order_id,
        )
        self._publisher.publish(alert)
        logger.debug(
            "[alert-source] bot %s: order %s filled, published",
            event.bot_id,
            event.order_id,
        )


def fill_line(event: BotOrderFilledEvent, symbol: str) -> str:
    """`ETHUSDT · BUY 0.019 @ 2,393.17 (level 7)`, and on the fill that closes a cycle
    `cycle +0.41 USDT · total +12.80 USDT · 31 cycles` on the next line."""
    line = (
        f"{symbol} · {event.side} {_plain(event.quantity)} @ {event.price:,} "
        f"(level {event.level})"
    )
    if event.cycle_profit is None:
        return line
    quote = event.quote_asset
    return (
        f"{line}\ncycle {_signed(event.cycle_profit)} {quote} · "
        f"total {_signed(event.realised_total)} {quote} · "
        f"{event.completed_cycles} {'cycle' if event.completed_cycles == 1 else 'cycles'}"
    )


def _plain(value: Decimal) -> str:
    """The number without a trailing zero or an exponent."""
    return format(value.normalize(), "f")


def _signed(value: Decimal) -> str:
    """Two decimals, four for a figure under a cent so a small profit does not read `+0.00`."""
    places = 2 if abs(value) >= Decimal("0.01") or value == 0 else 4
    return f"{value:+,.{places}f}"
