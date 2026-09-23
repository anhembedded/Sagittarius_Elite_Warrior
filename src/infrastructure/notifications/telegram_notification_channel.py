"""`TelegramNotificationChannel` — `BOT-018`'s headless-safe notification
channel: works from the CLI entry point exactly as it does from the GUI,
since it touches no Qt object.

@details
Opt-in by configuration alone (`ConfigKeys.NOTIFICATIONS_TELEGRAM_BOT_TOKEN`/
`NOTIFICATIONS_TELEGRAM_CHAT_ID`, both read fresh on every `send()` rather
than cached at construction, so toggling them in a running process takes
effect on the next notification): an empty bot token or chat id makes
`send()` a silent no-op, never a startup failure.

`urllib.request` (stdlib) rather than a new third-party HTTP client:
`requests`/`httpx` are not existing dependencies of this project, and
`commit-rule.md` §3 requires prior user confirmation to add one — a single
POST to one fixed endpoint does not need one.

Conforms to `INotificationChannel` structurally, without declaring it as a
base class — the same style `PythonBacktestChartHost` uses for
`IBacktestChartHost` — since that port is now a `Protocol`
(`i_notification_channel.py`'s own docstring says why).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_reader import (
    IConfigReader,
)
from sagittarius_engine.interfaces.i_logger import ILogger

#: The greppable subsystem tag `logging-rule.md` §8 requires.
_TAG = "[telegram-notify]"
_API_URL_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"
_REQUEST_TIMEOUT_SECONDS = 5.0


class TelegramNotificationChannel:
    """Posts `message` to one Telegram chat via the Bot API's `sendMessage`."""

    def __init__(self, config: IConfigReader, logger: ILogger) -> None:
        self._config = config
        self._logger = logger

    def send(self, message: str) -> None:
        bot_token = self._config.get(
            ConfigKeys.NOTIFICATIONS_TELEGRAM_BOT_TOKEN.value, ""
        )
        chat_id = self._config.get(ConfigKeys.NOTIFICATIONS_TELEGRAM_CHAT_ID.value, "")
        if not bot_token or not chat_id:
            return
        try:
            self._post(bot_token, chat_id, message)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            # Never logs `bot_token` — `create-bug-report-rule.md`/task risk
            # note both forbid a secret leaving `user_config.json`.
            self._logger.warning(f"{_TAG} delivery failed: {type(exc).__name__}: {exc}")

    def _post(self, bot_token: str, chat_id: str, message: str) -> None:
        payload = json.dumps({"chat_id": chat_id, "text": message}).encode("utf-8")
        # `_API_URL_TEMPLATE` is a fixed `https://` literal with only the bot
        # token interpolated — never a user-supplied URL or scheme, which is
        # the actual risk S310 audits for.
        request = urllib.request.Request(  # noqa: S310 - fixed https:// template, no user-controlled scheme
            _API_URL_TEMPLATE.format(token=bot_token),
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(  # noqa: S310 - same fixed https:// template as the Request above
            request, timeout=_REQUEST_TIMEOUT_SECONDS
        ):
            pass
