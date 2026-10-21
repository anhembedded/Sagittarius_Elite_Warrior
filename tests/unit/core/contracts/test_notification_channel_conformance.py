"""`BOT-018` — the real `INotificationChannel` implementation (the toast; Telegram became an
`IAlertChannel` in `EPIC-036C1`) conforms to the port structurally, without declaring inheritance (`architecture-rule.md`
§2.1 reason (a): `UiToastNotificationChannel` must be a `QObject`)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QMainWindow
from Sagittarius_Elite_Warrior.src.core.contracts.i_notification_channel import (
    INotificationChannel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.ui_toast_notification_channel import (
    UiToastNotificationChannel,
)


def test_ui_toast_channel_satisfies_the_port(qapp: QApplication) -> None:
    channel = UiToastNotificationChannel(QMainWindow())
    assert isinstance(channel, INotificationChannel)
