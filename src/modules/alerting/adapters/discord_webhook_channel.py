"""`IAlertChannel` for one Discord webhook (`EPIC-036G`, decision D1).

Reads the webhook by name from `ISecretStore` at each send and keeps no copy
(N3): on a headless host the name is a systemd credential, on a desktop a
keyring entry (decision D3, `support/secrets`). The body is
`discord_message.py`'s, the meaning of the answer `discord_answer.py`'s; this
class only joins them and keeps the rule of the port: it never raises.

**The webhook never leaves this class in words.** No log line, no reason and no
exception names it: a reason says which step failed ("no webhook is stored",
"Discord did not answer (timed out)", "Discord refused ... (404)").
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import ISecretStore
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_answer import (
    result_of,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_message import (
    discord_payload,
    is_discord_webhook_url,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel import (
    IAlertChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    IWebhookTransport,
    WebhookUnreachableError,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness

logger = logging.getLogger("App.Alerting")

#: The secret's name in every store: the systemd credential's name in the unit
#: file, the keyring entry's name on a desktop.
DISCORD_WEBHOOK_SECRET = "alerting_discord_webhook"  # noqa: S105 - the name of a secret, not a secret


class DiscordWebhookChannel(IAlertChannel):
    def __init__(self, secrets: ISecretStore, transport: IWebhookTransport) -> None:
        self._secrets = secrets
        self._transport = transport

    def deliver(self, alert: Alert, loudness: Loudness) -> DeliveryResult:
        webhook = (self._secrets.read(DISCORD_WEBHOOK_SECRET) or "").strip()
        if not webhook:
            return DeliveryResult.refused("no Discord webhook is stored")
        if not is_discord_webhook_url(webhook):
            return DeliveryResult.refused(
                "the stored Discord webhook is not a Discord webhook URL"
            )
        try:
            response = self._transport.post_json(
                webhook, discord_payload(alert, loudness)
            )
        except WebhookUnreachableError as error:
            return DeliveryResult.failed(f"Discord did not answer ({error})")
        result = result_of(response)
        logger.debug(
            "[alert-discord] %s -> %s",
            alert.dedup_key,
            "sent" if result.ok else result.reason,
        )
        return result
