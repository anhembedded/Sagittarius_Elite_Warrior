"""`BOT-018` — `TelegramNotificationChannel`.

The HTTP call is mocked at `urllib.request.urlopen` (the one seam this
channel owns) rather than hit for real — this is a unit test, and Telegram's
Bot API is a real external boundary no test here should reach.
"""

from __future__ import annotations

import json
import urllib.error
from typing import Any
from unittest.mock import MagicMock, patch

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_reader import (
    IConfigReader,
)
from Sagittarius_Elite_Warrior.src.infrastructure.notifications.telegram_notification_channel import (
    TelegramNotificationChannel,
)
from sagittarius_engine.interfaces.i_logger import ILogger

_MODULE = (
    "Sagittarius_Elite_Warrior.src.infrastructure.notifications."
    "telegram_notification_channel"
)


class _FakeConfigReader(IConfigReader):
    """Derived from the real port (`testing-rule.md` §2), not a `Mock`
    shaped from this file's own calls."""

    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)


class _RecordingLogger(ILogger):
    def __init__(self) -> None:
        self.lines: dict[str, list[str]] = {}

    def _record(self, level: str, message: str) -> None:
        self.lines.setdefault(level, []).append(message)

    def info(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._record("info", message)

    def warning(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._record("warning", message)

    def error(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._record("error", message)

    def debug(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._record("debug", message)

    def critical(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._record("critical", message)

    def trace(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._record("trace", message)


def _configured_reader(
    token: str = "123:ABC",  # noqa: S107 - test fixture value, not a real credential
    chat_id: str = "42",
) -> _FakeConfigReader:
    return _FakeConfigReader(
        {
            ConfigKeys.NOTIFICATIONS_TELEGRAM_BOT_TOKEN.value: token,
            ConfigKeys.NOTIFICATIONS_TELEGRAM_CHAT_ID.value: chat_id,
        }
    )


def test_send_does_nothing_when_unconfigured():
    channel = TelegramNotificationChannel(_FakeConfigReader({}), _RecordingLogger())

    with patch(f"{_MODULE}.urllib.request.urlopen") as mock_urlopen:
        channel.send("hello")

    mock_urlopen.assert_not_called()


def test_send_does_nothing_when_only_the_token_is_set():
    channel = TelegramNotificationChannel(
        _FakeConfigReader({ConfigKeys.NOTIFICATIONS_TELEGRAM_BOT_TOKEN.value: "x"}),
        _RecordingLogger(),
    )

    with patch(f"{_MODULE}.urllib.request.urlopen") as mock_urlopen:
        channel.send("hello")

    mock_urlopen.assert_not_called()


def test_send_posts_the_message_to_the_configured_chat():
    reader = _configured_reader(token="123:ABC", chat_id="42")
    channel = TelegramNotificationChannel(reader, _RecordingLogger())

    with patch(f"{_MODULE}.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__ = MagicMock()
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        channel.send("Data sync failed — ETHUSDT")

    assert mock_urlopen.call_count == 1
    request = mock_urlopen.call_args[0][0]
    assert request.full_url == "https://api.telegram.org/bot123:ABC/sendMessage"
    body = json.loads(request.data.decode("utf-8"))
    assert body == {"chat_id": "42", "text": "Data sync failed — ETHUSDT"}


def test_send_logs_a_warning_on_delivery_failure_without_leaking_the_token():
    channel = TelegramNotificationChannel(
        _configured_reader(token="secret-token"), (logger := _RecordingLogger())
    )

    with patch(f"{_MODULE}.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError("network unreachable")
        channel.send("hello")

    warnings = logger.lines.get("warning", [])
    assert len(warnings) == 1
    assert "secret-token" not in warnings[0]
    assert "network unreachable" in warnings[0]
