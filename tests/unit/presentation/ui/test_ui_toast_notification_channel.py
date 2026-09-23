"""`BOT-018` — `UiToastNotificationChannel` shows a message in the standard
`QMainWindow.statusBar()` rather than a hand-drawn overlay
(`ui-presentation-rule.md` §1)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QMainWindow
from Sagittarius_Elite_Warrior.src.presentation.ui.ui_toast_notification_channel import (
    UiToastNotificationChannel,
)


def test_send_shows_the_message_in_the_status_bar(qapp: QApplication) -> None:
    window = QMainWindow()
    channel = UiToastNotificationChannel(window)

    channel.send("Data sync failed — ETHUSDT")

    assert window.statusBar().currentMessage() == "Data sync failed — ETHUSDT"

    window.deleteLater()


def test_send_replaces_a_still_visible_earlier_message(qapp: QApplication) -> None:
    window = QMainWindow()
    channel = UiToastNotificationChannel(window)

    channel.send("first failure")
    channel.send("second failure")

    assert window.statusBar().currentMessage() == "second failure"

    window.deleteLater()
