"""`IAlertChannel` for one Telegram chat (`EPIC-036C1`, decision D1's second channel).

Replaces `TelegramNotificationChannel` (`BOT-018`), which read its token from the config file,
did not retry and swallowed a failure into a log line. This one reads the bot token and the
chat id by name from `ISecretStore` at each send and keeps no copy (N3): a systemd credential
on a headless host, the keyring on a desktop (decision D3). The body is `telegram_message.py`'s,
the meaning of the answer `telegram_answer.py`'s; this class only joins them and keeps the rule
of the port: it never raises.

**The token is in the URL path** (`/bot<token>/sendMessage`), so it never leaves this class in
words: the transport reduces its errors to their kind (`urllib_webhook_transport.py`), and no
log line, reason or exception here names it. Both values are checked against the shapes Telegram
issues before they go into a URL, so a stored value cannot redirect the request.
"""

from __future__ import annotations

import logging
import re

from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import ISecretStore
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.telegram_answer import (
    result_of,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.telegram_message import (
    telegram_payload,
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

#: The id the settings, the catalog and the lane name this channel by.
TELEGRAM_CHANNEL_ID = "telegram"

#: The secrets' names in every store: the systemd credentials' names in the unit file, the
#: keyring entries' names on a desktop.
TELEGRAM_TOKEN_SECRET = "alerting_telegram_bot_token"  # noqa: S105 - the name of a secret, not a secret
TELEGRAM_CHAT_SECRET = "alerting_telegram_chat_id"  # noqa: S105 - the name of a secret, not a secret

_SEND_URL = "https://api.telegram.org/bot{token}/sendMessage"

#: A bot token as @BotFather issues it: the bot's numeric id, a colon, a key.
_TOKEN = re.compile(r"[0-9]+:[A-Za-z0-9_-]+")

#: A chat id (a user, group or supergroup, negative for groups) or a public channel's @name.
_CHAT = re.compile(r"-?[0-9]+|@[A-Za-z][A-Za-z0-9_]{4,}")


def is_bot_token(value: str) -> bool:
    return _TOKEN.fullmatch(value) is not None


def is_chat_id(value: str) -> bool:
    return _CHAT.fullmatch(value) is not None


class TelegramChannel(IAlertChannel):
    def __init__(self, secrets: ISecretStore, transport: IWebhookTransport) -> None:
        self._secrets = secrets
        self._transport = transport

    def deliver(self, alert: Alert, loudness: Loudness) -> DeliveryResult:
        token = (self._secrets.read(TELEGRAM_TOKEN_SECRET) or "").strip()
        chat = (self._secrets.read(TELEGRAM_CHAT_SECRET) or "").strip()
        if not token or not chat:
            return DeliveryResult.refused(
                "no Telegram bot token and chat id are stored"
            )
        if not is_bot_token(token) or not is_chat_id(chat):
            return DeliveryResult.refused(
                "the stored Telegram bot token or chat id is not of the shape Telegram issues"
            )
        try:
            response = self._transport.post_json(
                _SEND_URL.format(token=token), telegram_payload(chat, alert, loudness)
            )
        except WebhookUnreachableError as error:
            return DeliveryResult.failed(f"Telegram did not answer ({error})")
        result = result_of(response)
        logger.debug(
            "[alert-telegram] %s -> %s",
            alert.dedup_key,
            "sent" if result.ok else result.reason,
        )
        return result
