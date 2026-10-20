"""The Telegram path is paused until `EPIC-036C`, and a host that set it up is told (`EPIC-036B`).

`EPIC-036B` removed the direct Telegram wiring: system failures go to the alerting module's
channels (Discord) and `TelegramNotificationChannel` has no caller until `EPIC-036C` moves it into
`alerting`. An owner whose config still holds a Telegram token and chat id would otherwise get
silence from a channel they set up, so the start says it once. The values are never logged.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_reader import IConfigReader
from sagittarius_engine.interfaces.i_logger import ILogger


def warn_when_telegram_is_configured(config: IConfigReader, logger: ILogger) -> None:
    token = config.get(ConfigKeys.NOTIFICATIONS_TELEGRAM_BOT_TOKEN.value, "")
    chat_id = config.get(ConfigKeys.NOTIFICATIONS_TELEGRAM_CHAT_ID.value, "")
    if token or chat_id:
        logger.warning(
            "[notification] Telegram is configured but paused until EPIC-036C: "
            "system failures go to the alerting channels (Discord) only"
        )
