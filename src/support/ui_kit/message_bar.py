"""The inline message bar: one background failure, in the mode it concerns (`BOT-169`).

A modal box would interrupt typing and stack up during an outage, so a failure the
app lives with (a read that failed, a connection that dropped) is told in a bar
at the top of the mode it affects, with Retry when there is something to retry
and Details… for the technical text. Stock widgets only: a framed panel, the
style's own warning icon, labels and push buttons.

`MessageBarHost` holds one bar per failure. The same cause told again updates its
bar in place. A cause whose technical text is the text a bar already shows
joins that bar (`failure_signature`: every way of saying "the exchange could not
answer" is one text, so one outage read four times is one bar, "and 3 more"); any other failure gets a bar of its own, never hidden
behind another's headline. A bar keeps every notice that joined it: Retry runs
each one's retry, and when the cause it shows recovers it shows the next. The
host takes no height while it holds no bar.
"""

from __future__ import annotations

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
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureNotice,
    failure_signature,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label


class MessageBar(QFrame):
    """One failure: icon, headline, and the buttons its notices offer."""

    #: The notices the bar holds: Retry runs each one's retry.
    retryRequested = Signal(object)
    #: The notice the bar shows: Details… opens its technical text.
    detailsRequested = Signal(object)
    #: The causes the bar held, when the user closed it.
    dismissed = Signal(object)

    def __init__(self, notice: FailureNotice, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        #: Every notice on this bar by cause; the first is the one shown.
        self.notices: dict[str, FailureNotice] = {notice.cause: notice}
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
        self._retry.clicked.connect(
            lambda: self.retryRequested.emit(tuple(self.notices.values()))
        )
        self._details.clicked.connect(lambda: self.detailsRequested.emit(self.shown))
        self._dismiss.clicked.connect(lambda: self.dismissed.emit(tuple(self.notices)))
        row = QHBoxLayout(self)
        row.addWidget(icon)
        row.addWidget(self._headline, 1)
        row.addWidget(self._retry)
        row.addWidget(self._details)
        row.addWidget(self._dismiss)
        self.refresh()

    @property
    def shown(self) -> FailureNotice:
        return next(iter(self.notices.values()))

    @property
    def headline(self) -> str:
        return self._headline.text()

    def refresh(self) -> None:
        """Draws the shown notice and how many others joined it."""
        shown = self.shown
        more = len(self.notices) - 1
        suffix = f" (and {more} more)" if more else ""
        self._headline.setText(f"{shown.headline}{suffix}")
        self._retry.setVisible(any(n.retry is not None for n in self.notices.values()))
        self._details.setVisible(bool(shown.detail))


class Shown(Enum):
    """What `MessageBarHost.show_notice` did with a notice."""

    OPENED = auto()
    UPDATED = auto()
    #: Its failure text is one a bar already shows: the cause joined that bar.
    MERGED = auto()


class MessageBarHost(QWidget):
    """The strip above a mode's content that holds its bars."""

    retryRequested = Signal(object)
    detailsRequested = Signal(object)
    dismissed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bars: list[MessageBar] = []
        #: Every active cause, to the bar that shows it.
        self._bar_of: dict[str, MessageBar] = {}
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self.setVisible(False)

    def causes(self) -> tuple[str, ...]:
        """Every cause showing, merged ones included."""
        return tuple(self._bar_of)

    def bar_count(self) -> int:
        return len(self._bars)

    def bar(self, cause: str) -> MessageBar | None:
        return self._bar_of.get(cause)

    def show_notice(self, notice: FailureNotice) -> Shown:
        bar = self._bar_of.get(notice.cause)
        if bar is not None:
            bar.notices[notice.cause] = notice
            bar.refresh()
            return Shown.UPDATED
        twin = self._bar_showing_text(notice.detail)
        if twin is not None:
            twin.notices[notice.cause] = notice
            self._bar_of[notice.cause] = twin
            twin.refresh()
            return Shown.MERGED
        bar = MessageBar(notice, self)
        bar.retryRequested.connect(self.retryRequested)
        bar.detailsRequested.connect(self.detailsRequested)
        bar.dismissed.connect(self._dismiss)
        self._bars.append(bar)
        self._bar_of[notice.cause] = bar
        self._column.addWidget(bar)
        self.setVisible(True)
        return Shown.OPENED

    def clear(self, cause: str) -> bool:
        """`cause` recovered; returns whether it was showing. Its bar goes when
        it was the last cause on it, and shows the next one otherwise."""
        bar = self._bar_of.pop(cause, None)
        if bar is None:
            return False
        del bar.notices[cause]
        if bar.notices:
            bar.refresh()
        else:
            self._remove(bar)
        return True

    def _dismiss(self, causes: tuple[str, ...]) -> None:
        """The user closed a bar, with every cause on it."""
        for cause in causes:
            bar = self._bar_of.pop(cause, None)
            if bar is not None and bar in self._bars:
                self._remove(bar)
        self.dismissed.emit(causes)

    def _bar_showing_text(self, detail: str) -> MessageBar | None:
        if not detail:
            return None
        signature = failure_signature(detail)
        return next(
            (b for b in self._bars if failure_signature(b.shown.detail) == signature),
            None,
        )

    def _remove(self, bar: MessageBar) -> None:
        self._bars.remove(bar)
        self._column.removeWidget(bar)
        bar.deleteLater()
        self.setVisible(bool(self._bars))
