"""The inline message bar: one background failure, in the mode it concerns (`BOT-169`).

A modal box would interrupt typing and stack up during an outage, so a failure the
app lives with (a read that failed, a connection that dropped) is told in a bar
at the top of the mode it affects, with Retry when there is something to retry
and Details… for the technical text. Stock widgets only: a framed panel, the
style's own warning icon, labels and push buttons.

`MessageBarHost` holds one bar per failure: the same cause told again updates its
bar in place, and a cause with the same technical text as a bar joins it, so one
outage read four times is one bar; a recovered cause leaves it; the host takes
no height while it holds none.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from enum import Enum, auto

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureNotice
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

#: A failure told within this many seconds of the last one a bar took joins
#: that bar: one outage fails every read at once, with a different sentence
#: each, and is one message.
BURST_WINDOW_S = 3.0


class MessageBar(QFrame):
    """One failure: icon, headline, and the buttons its notice offers."""

    retryRequested = Signal(str)
    detailsRequested = Signal(str)
    dismissed = Signal(str)

    def __init__(self, notice: FailureNotice, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cause = notice.cause
        #: Every cause this bar shows: the one that opened it and those that joined.
        self.causes: set[str] = {notice.cause}
        self.detail = notice.detail
        #: How many failures besides its own the bar took in (a burst).
        self.absorbed = 0
        self.last_at = 0.0
        self._base_headline = notice.headline
        self.setObjectName(f"message_bar::{notice.cause}")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        icon = plain_label(parent=self)
        icon.setPixmap(
            self.style()
            .standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
            .pixmap(self.fontMetrics().height())
        )
        self._headline = plain_label(parent=self)
        self._headline.setWordWrap(True)
        self._retry = QPushButton("Retry", self)
        self._details = QPushButton("Details…", self)
        self._dismiss = QPushButton("Dismiss", self)
        self._retry.clicked.connect(lambda: self.retryRequested.emit(self.cause))
        self._details.clicked.connect(lambda: self.detailsRequested.emit(self.cause))
        self._dismiss.clicked.connect(lambda: self.dismissed.emit(self.cause))
        row = QHBoxLayout(self)
        row.addWidget(icon)
        row.addWidget(self._headline, 1)
        row.addWidget(self._retry)
        row.addWidget(self._details)
        row.addWidget(self._dismiss)
        self.update_notice(notice)

    @property
    def headline(self) -> str:
        return self._headline.text()

    def absorb(self) -> None:
        """Takes in one more failure of the same burst."""
        self.absorbed += 1
        self._show_headline()

    def _show_headline(self) -> None:
        more = f" (and {self.absorbed} more)" if self.absorbed else ""
        self._headline.setText(f"{self._base_headline}{more}")

    def update_notice(self, notice: FailureNotice) -> None:
        """Shows `notice` in place of what the bar showed for the same cause."""
        self.detail = notice.detail
        self._base_headline = notice.headline
        self._show_headline()
        self._retry.setVisible(notice.retry is not None)
        self._details.setVisible(bool(notice.detail))


class Shown(Enum):
    """What `MessageBarHost.show_notice` did with a notice."""

    OPENED = auto()
    UPDATED = auto()
    #: Its failure text is one a bar already shows: the cause joined that bar.
    MERGED = auto()


class MessageBarHost(QWidget):
    """The strip above a mode's content that holds its bars.

    A bar is one failure. The same cause told again updates its bar in place.
    A different cause joins a bar instead of opening another when its technical
    text is the bar's, or when it arrives within `BURST_WINDOW_S` of the last
    failure the bar took: one outage fails every read at once, so it is one
    message. A bar goes when every cause that joined it has recovered.
    """

    retryRequested = Signal(str)
    detailsRequested = Signal(str)
    dismissed = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(parent)
        self._clock = clock
        #: Bars by the cause that opened them.
        self._bars: dict[str, MessageBar] = {}
        #: Every active cause, to the cause of the bar that shows it.
        self._bar_of: dict[str, str] = {}
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self.setVisible(False)

    def causes(self) -> tuple[str, ...]:
        """Every cause showing, merged ones included."""
        return tuple(self._bar_of)

    def bar_count(self) -> int:
        return len(self._bars)

    def bar(self, cause: str) -> MessageBar | None:
        primary = self._bar_of.get(cause)
        return None if primary is None else self._bars[primary]

    def show_notice(self, notice: FailureNotice) -> Shown:
        now = self._clock()
        primary = self._bar_of.get(notice.cause)
        if primary is not None:
            if primary == notice.cause:
                self._bars[primary].update_notice(notice)
            return Shown.UPDATED
        host_bar = self._bar_showing_text(notice.detail) or self._bar_in_burst(now)
        if host_bar is not None:
            self._bar_of[notice.cause] = host_bar.cause
            host_bar.causes.add(notice.cause)
            host_bar.last_at = now
            host_bar.absorb()
            return Shown.MERGED
        bar = MessageBar(notice, self)
        bar.last_at = now
        bar.retryRequested.connect(self.retryRequested)
        bar.detailsRequested.connect(self.detailsRequested)
        bar.dismissed.connect(self.dismiss)
        self._bars[notice.cause] = bar
        self._bar_of[notice.cause] = notice.cause
        self._column.addWidget(bar)
        self.setVisible(True)
        return Shown.OPENED

    def clear(self, cause: str) -> bool:
        """`cause` recovered; returns whether it was showing. Its bar goes
        when it was the last cause on it."""
        primary = self._bar_of.pop(cause, None)
        if primary is None:
            return False
        bar = self._bars[primary]
        bar.causes.discard(cause)
        if not bar.causes:
            self._remove(primary)
        return True

    def dismiss(self, primary: str) -> None:
        """The user closed the bar opened by `primary`, with every cause on it."""
        bar = self._bars.get(primary)
        if bar is None:
            return
        for cause in tuple(bar.causes):
            self._bar_of.pop(cause, None)
        self._remove(primary)
        self.dismissed.emit(primary)

    def _bar_in_burst(self, now: float) -> MessageBar | None:
        """The bar that took a failure within `BURST_WINDOW_S` of `now`."""
        recent = [b for b in self._bars.values() if now - b.last_at <= BURST_WINDOW_S]
        return max(recent, key=lambda b: b.last_at, default=None)

    def _bar_showing_text(self, detail: str) -> MessageBar | None:
        if not detail:
            return None
        return next((b for b in self._bars.values() if b.detail == detail), None)

    def _remove(self, primary: str) -> None:
        bar = self._bars.pop(primary)
        self._column.removeWidget(bar)
        bar.deleteLater()
        self.setVisible(bool(self._bars))
