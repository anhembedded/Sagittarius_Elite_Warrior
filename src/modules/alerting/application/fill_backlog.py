"""`BOT-189` — the bound on fill messages waiting for a channel.

A grid fills often and a channel can stop for a while (Discord's `retry_after`, a dropped network);
a day of queued fills must not be what a CRITICAL waits behind, nor what the owner reads when the
channel returns. After each fill message is stored, the oldest ones past `DeliveryPolicy.fill_backlog`
on that channel are dropped (recorded as `DROPPED`, never lost silently), and the housekeeping tick
turns what was dropped into **one** line, "N fill messages skipped".

The worker already tries a CRITICAL before any queued alert (`IOutbox.due`), so this bound is only
about what the owner reads; the order is `ChannelDelivery`'s and is locked by its own test.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_outbox import IOutbox
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.outbox_records import (
    DeliveryTarget,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    DeliveryPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)

logger = logging.getLogger("App.Alerting")


class FillBacklog:
    """Keeps the newest fill messages of each channel and counts the rest."""

    def __init__(self, outbox: IOutbox, policy: DeliveryPolicy) -> None:
        self._outbox = outbox
        self._keep = policy.fill_backlog
        self._skipped: dict[str, int] = {}

    def trim(self, alert: Alert, targets: Iterable[DeliveryTarget]) -> None:
        """After `alert` was stored for `targets`: drop the fill messages that no longer fit."""
        if alert.kind is not AlertKind.ORDER_FILLED:
            return
        for target in targets:
            if target.state is not DeliveryState.PENDING:
                continue
            dropped = self._outbox.shed_surplus(
                target.channel_id, AlertKind.ORDER_FILLED, self._keep
            )
            if dropped:
                self._skipped[target.channel_id] = (
                    self._skipped.get(target.channel_id, 0) + dropped
                )
                logger.warning(
                    "[alert-fills] %s: %d queued fill message(s) dropped; the queue holds %d [fill-backlog]",
                    target.channel_id,
                    dropped,
                    self._keep,
                )

    def take_summary(self, now: datetime) -> Alert | None:
        """The one line for what was dropped since the last call, or `None`. Counted by the
        channel that dropped most: a fill dropped on two channels is one skipped message."""
        if not self._skipped:
            return None
        count = max(self._skipped.values())
        self._skipped = {}
        return Alert.raised(
            AlertKind.FILLS_SKIPPED,
            AlertSubject.app(),
            f"{count} fill messages skipped",
            "A channel could not take them as fast as the bots filled, so the oldest "
            "waiting ones were dropped. Every fill is in the bots' own record.",
            now,
            now.isoformat(),
        )
