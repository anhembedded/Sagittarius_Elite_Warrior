"""`IAlertChannel` — one place an alert can be sent to (`EPIC-036A`, N1).

The `INotificationChannel` seam of `BOT-018` extended, not paralleled: a typed
alert instead of a string, and a result instead of silence. `ABC`, not
`Protocol` (`architecture-rule.md` §2.1): the implementers are plain adapters.

**Never raises.** Every failure is a `DeliveryResult`; a channel that raises
anyway is contained by the worker and recorded as a failed try, but that is a
net, not a licence.

**Formats its own message.** An embed coloured by severity, Markdown, plain
text: the channel decides, from the typed `Alert`.

**Reads its secret by name when it sends** (`ISecretStore`), keeps none.

@par Extension cases
  · Discord webhook, Telegram (`EPIC-036C`) - one adapter file and one line in
    `composition/channel_bindings.py`; hub, worker and outbox are untouched;
  · email, SMS, a push service - the same;
  · the in-app toast channel (`EPIC-036B` decides its path) - the same.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness


class IAlertChannel(ABC):
    @abstractmethod
    def deliver(self, alert: Alert, loudness: Loudness) -> DeliveryResult:
        """Try once to send `alert`, silently when `loudness` is `SILENT`.

        `loudness` is never `OFF` here: an off cell sends nothing. It travels
        beside the alert, not inside it, because it is a property of the route
        (group x channel), not of the event.
        """
