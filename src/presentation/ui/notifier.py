"""`NotifierPresenter` — the one `INotifier`: it picks the surface for a message (`BOT-169`).

@details
A command that failed is a modal message box (`QMessageBox`, technical text
behind its own Details), because the user must decide something. A background
failure is an inline message bar in the mode it concerns, with Retry and
Details…, because the app keeps working and a dialog would interrupt typing
and stack up during an outage. An event told while the user looks elsewhere is
a toast: the system notification when the platform offers one, the status bar
for ten seconds when it does not. Routine state is the status bar's, not this
presenter's (`ui-presentation-rule.md` §10).

**One cause is one message.** A box is open per cause at most: the same
failure told while its box is open is dropped (logged at DEBUG). A bar is one
per cause per mode and is updated in place. This is what turns one outage read
four times in 50 ms into one message.

**Any thread may tell it.** The methods emit a signal whose delivery is queued
to the UI thread (the presenter lives there), as `UiToastNotificationChannel`
does (`BUG-031`).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QSystemTrayIcon,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.application_identity import (
    APPLICATION_NAME,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.message_bar import (
    MessageBarHost,
    Shown,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.mode_host import ModeHost
from sagittarius_engine.interfaces.i_container import IContainer

logger = logging.getLogger("App.Shell.Notifier")

#: How long a toast that falls back to the status bar stays.
_TOAST_MS = 10_000
#: Makes the message box of a failed command; replaceable so a test can look at
#: it without a dialog opening.
BoxFactory = Callable[[FailureNotice, QWidget | None], QMessageBox]


def _command_failed_box(notice: FailureNotice, parent: QWidget | None) -> QMessageBox:
    box = QMessageBox(
        QMessageBox.Icon.Critical,
        APPLICATION_NAME,
        notice.headline,
        QMessageBox.StandardButton.Ok,
        parent,
    )
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    if notice.detail:
        box.setDetailedText(notice.detail)
    return box


class MainWindowLike(Protocol):
    """What `adopt` reads of the main window, so a test needs no engine."""

    hosts: Mapping[str, ModeHost]
    navigation: Any
    current_mode: str | None


class NotifierPresenter(QObject):
    """Tells the user about failures and events, on the surface that fits."""

    _failure = Signal(object)
    _cleared = Signal(str)
    _event = Signal(str, str)

    def __init__(self, box_factory: BoxFactory = _command_failed_box) -> None:
        super().__init__()
        self._early: list[FailureNotice] = []
        self._box_factory = box_factory
        self._window: QMainWindow | None = None
        self._tray: QSystemTrayIcon | None = None
        self._hosts: dict[str, MessageBarHost] = {}
        self._shown_scope = ""
        self._boxes: dict[str, QMessageBox] = {}
        self._failure.connect(self._show_failure)
        self._cleared.connect(self._clear)
        self._event.connect(self._show_event)

    # -- the shell wires it -------------------------------------------- #

    def adopt(self, window: MainWindowLike) -> None:
        """Takes `window` as the parent of boxes and the owner of toasts, and
        its modes' message bars as the places a background failure is shown;
        what was told before any bar existed is shown now."""
        self._window = window
        for scope, host in window.hosts.items():
            self.register_scope(scope, host.message_bars)
        window.navigation.mode_changed.connect(self.show_unscoped_in)
        if window.current_mode is not None:
            self.show_unscoped_in(window.current_mode)
        early, self._early = self._early, []
        for notice in early:
            self._show_failure(notice)

    def attach_window(self, window: QMainWindow) -> None:
        """The window boxes are modal to and toasts are shown by."""
        self._window = window

    def show_unscoped_in(self, scope: str) -> None:
        """A failure that names no mode is shown in the mode showing now."""
        self._shown_scope = scope

    def register_scope(self, scope: str, host: MessageBarHost) -> None:
        """Makes `host` the bar strip of the mode `scope`."""
        self._hosts[scope] = host
        host.retryRequested.connect(self._retry)
        host.detailsRequested.connect(self._show_details)

    # -- INotifier ----------------------------------------------------- #

    def report_failure(self, notice: FailureNotice) -> None:
        self._failure.emit(notice)

    def clear_failure(self, cause: str) -> None:
        self._cleared.emit(cause)

    def notify(self, headline: str, detail: str = "") -> None:
        self._event.emit(headline, detail)

    # -- on the UI thread ---------------------------------------------- #

    def _show_failure(self, notice: FailureNotice) -> None:
        if notice.kind is FailureKind.COMMAND:
            self._show_box(notice)
        else:
            self._show_bar(notice)

    def _show_box(self, notice: FailureNotice) -> None:
        if notice.cause in self._boxes:
            logger.debug(
                "Failure %s is already on screen: not shown again [notice-deduplicated]",
                notice.cause,
            )
            return
        logger.warning(
            "Command failed, shown in a message box: %s [notice-command]", notice.cause
        )
        box = self._box_factory(notice, self._window)
        self._boxes[notice.cause] = box
        box.finished.connect(lambda _result: self._boxes.pop(notice.cause, None))
        box.open()

    def _show_bar(self, notice: FailureNotice) -> None:
        if not self._hosts:
            self._early.append(notice)
            return
        host = self._hosts.get(notice.scope) or self._hosts.get(self._shown_scope)
        if host is None:
            logger.warning(
                "Background failure with no message bar to show it: %s [notice-unhosted]",
                notice.cause,
            )
            return
        shown = host.show_notice(notice)
        if shown is Shown.OPENED:
            logger.warning(
                "Background failure, shown in the %r message bar: %s [notice-bar]",
                notice.scope,
                notice.cause,
            )
        else:
            logger.debug(
                "Failure %s is already in a bar (%s): not opened again [notice-deduplicated]",
                notice.cause,
                shown.name.lower(),
            )

    def _clear(self, cause: str) -> None:
        for host in self._hosts.values():
            if host.clear(cause):
                logger.info("Failure %s cleared [notice-cleared]", cause)

    def _retry(self, notices: tuple[FailureNotice, ...]) -> None:
        """The bar's Retry: every notice on it that can be retried, once."""
        for notice in notices:
            if notice.retry is not None:
                logger.info(
                    "Retrying %s from its message bar [notice-retry]", notice.cause
                )
                notice.retry()

    def _show_details(self, notice: FailureNotice) -> None:
        if not notice.detail:
            return
        box = QMessageBox(
            QMessageBox.Icon.Information,
            APPLICATION_NAME,
            notice.headline,
            QMessageBox.StandardButton.Close,
            self._window,
        )
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setDetailedText(notice.detail)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.open()

    def _show_event(self, headline: str, detail: str) -> None:
        logger.info("Notice: %s [notice-event]", headline)
        window = self._window
        if window is None:
            return
        if (
            QSystemTrayIcon.isSystemTrayAvailable()
            and QSystemTrayIcon.supportsMessages()
        ):
            self._tray_icon(window).showMessage(
                APPLICATION_NAME,
                headline,
                QSystemTrayIcon.MessageIcon.Information,
                _TOAST_MS,
            )
        else:
            window.statusBar().showMessage(headline, _TOAST_MS)

    def _tray_icon(self, window: QMainWindow) -> QSystemTrayIcon:
        if self._tray is None:
            self._tray = QSystemTrayIcon(window.windowIcon(), self)
            self._tray.show()
        return self._tray


def install_notifier(container: IContainer) -> NotifierPresenter:
    """Binds the Qt presenter as the app's `INotifier`, before any screen is
    built: a presenter resolves the port as it is constructed."""
    notifier = NotifierPresenter()
    container.singleton(INotifier, notifier)
    return notifier
