"""`BOT-018` — `UiToastNotificationChannel` shows a message in the standard
`QMainWindow.statusBar()` rather than a hand-drawn overlay
(`ui-presentation-rule.md` §1)."""

from __future__ import annotations

import threading

from PySide6.QtWidgets import QApplication, QMainWindow
from Sagittarius_Elite_Warrior.src.presentation.ui.ui_toast_notification_channel import (
    UiToastNotificationChannel,
)


class _RecordingChannel(UiToastNotificationChannel):
    """Records which thread `_display()` actually ran on, without changing
    what it does — used to prove `send()` hops to the main thread rather
    than trusting that the widget mutation "just worked" (`PR #259` review
    finding: it must not run on whatever thread called `send()`)."""

    def __init__(self, window: QMainWindow) -> None:
        self.display_thread_ids: list[int] = []
        super().__init__(window)

    def _display(self, message: str) -> None:
        self.display_thread_ids.append(threading.get_ident())
        super()._display(message)


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


def test_send_from_a_background_thread_still_displays_on_the_main_thread(
    qapp: QApplication,
) -> None:
    """`PR #259` review finding: `NotificationEventHandler` calls `send()`
    off the main thread by design (`TaskFailed` is always published from a
    background worker). A regression back to calling
    `self._window.statusBar().showMessage(...)` directly inside `send()`
    would make `_display()` run on the worker thread instead of this
    channel's own (main) thread — this test fails in exactly that case."""
    window = QMainWindow()
    channel = _RecordingChannel(window)
    main_thread_id = threading.get_ident()

    worker = threading.Thread(target=channel.send, args=("from a worker thread",))
    worker.start()
    worker.join()
    qapp.processEvents()

    assert channel.display_thread_ids == [main_thread_id], (
        f"_display() ran on thread(s) {channel.display_thread_ids}, not the "
        f"channel's own main thread ({main_thread_id}) — the queued-signal "
        "hop is not actually happening"
    )
    assert window.statusBar().currentMessage() == "from a worker thread"

    window.deleteLater()
