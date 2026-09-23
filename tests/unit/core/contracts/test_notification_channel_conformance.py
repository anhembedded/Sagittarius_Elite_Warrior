"""`BOT-018` — both real `INotificationChannel` implementations conform to
the port structurally, without declaring inheritance (`architecture-rule.md`
§2.1 reason (a): `UiToastNotificationChannel` must be a `QObject`)."""

from __future__ import annotations

from unittest.mock import Mock

from PySide6.QtWidgets import QApplication, QMainWindow
from Sagittarius_Elite_Warrior.src.core.contracts.i_notification_channel import (
    INotificationChannel,
)
from Sagittarius_Elite_Warrior.src.infrastructure.notifications.telegram_notification_channel import (
    TelegramNotificationChannel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.ui_toast_notification_channel import (
    UiToastNotificationChannel,
)


def test_telegram_channel_satisfies_the_port() -> None:
    channel = TelegramNotificationChannel(Mock(), Mock())
    assert isinstance(channel, INotificationChannel)


def test_ui_toast_channel_satisfies_the_port(qapp: QApplication) -> None:
    channel = UiToastNotificationChannel(QMainWindow())
    assert isinstance(channel, INotificationChannel)
