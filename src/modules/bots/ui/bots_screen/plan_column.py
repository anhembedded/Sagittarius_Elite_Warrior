"""`BOT-218` — the one column a bot's plan is read and edited in, on the Live tab and on the
Backtest tab.

A bot's plan is the same thing in both places, so it is laid out the same way in both: a status
banner, what sits right under it, the figures, the kind's parameter editor, then what the kind says
about those parameters as a list of checks (`plan_checks_view.py`), and a foot. The column holds the
slots and the order; the Live plan (`bot_plan_panel.py`) and the Backtest sandbox
(`backtest_workbench_view.py`) fill them with what is theirs: the bot's name, venue and figures, or
the sandbox's source line and its question about discarding edits. The column names no kind: the
editor arrives from the presenter.

The column scrolls once, at itself (`ui-presentation-rule.md` §3): the editor and the checks stand
over 500 px, and without the scroll they set the whole mode's minimum height (the PR #361 review
measured 703 px). A scroll area asks its content's `heightForWidth`, so a wrapped label has the
height its text needs at the column's width and never overlaps the next one (`BUG-246`).
"""

from __future__ import annotations

from typing import override

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QLayout, QScrollArea, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_checks_view import (
    PlanChecksView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_status_banner import (
    PlanStatusBanner,
)

from .widget_slot import replace_in


class PlanColumn(QScrollArea):
    """@brief The slots of a bot's plan, top to bottom, in one scroll."""

    def __init__(
        self, object_name: str, banner_name: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        #: Where the bot stands, or what the sandbox is, in one sentence with the platform's icon.
        self.banner = PlanStatusBanner(banner_name)
        self.checks = PlanChecksView()
        #: Above the banner, under it, the figures, the kind's editor and the foot.
        self.head = QVBoxLayout()
        self.intro = QVBoxLayout()
        self.figures = QVBoxLayout()
        self.editor = QVBoxLayout()
        self.foot = QVBoxLayout()
        self._editor_first = False
        self._body = QWidget()
        self._column = QVBoxLayout(self._body)
        self._column.addLayout(self.head)
        self._column.addWidget(self.banner)
        self._column.addLayout(self.intro)
        self._column.addLayout(self.figures)
        self._column.addLayout(self.editor)
        self._column.addWidget(self.checks.body)
        self._column.addLayout(self.foot)
        self._column.addStretch(1)
        self.setWidget(self._body)

    @override
    def minimumSizeHint(self) -> QSize:
        """As wide as its content needs and no wider: the column never scrolls across, so a pane
        a splitter gives it less than that would cut the editor's right edge instead of showing
        it (`BUG-246`); the splitter and the window then keep the width the column asks for."""
        inner = self._body.minimumSizeHint()
        extra = self.frameWidth() * 2 + self.verticalScrollBar().sizeHint().width()
        return QSize(inner.width() + extra, super().minimumSizeHint().height())

    def set_editor(self, panel: QWidget | None) -> None:
        """The editor of the selected bot's kind: one built for this selection, deleted when the
        next is shown (`BUG-242`)."""
        if panel is not None:
            panel.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        replace_in(self.editor, panel)

    def put_editor_first(self, first: bool) -> None:
        """A bot at rest is being designed: its editor comes right after the banner, then the
        checks and the figures. A bot with a run is being watched: the figures come first, the
        editor is read-only below them, and the checks last (`EPIC-035N`, `BOT-209`)."""
        if first == self._editor_first:
            return
        self._editor_first = first
        self._column.removeItem(self.figures)
        self._column.removeItem(self.editor)
        self._column.removeWidget(self.checks.body)
        at = self._column.indexOf(self.intro) + 1
        if first:
            self._column.insertLayout(at, self.editor)
            self._column.insertWidget(at + 1, self.checks.body)
            self._column.insertLayout(at + 2, self.figures)
        else:
            self._column.insertLayout(at, self.figures)
            self._column.insertLayout(at + 1, self.editor)
            self._column.insertWidget(at + 2, self.checks.body)

    def index_of(self, part: QLayout | QWidget) -> int:
        """Where `part` sits in the column, top to bottom."""
        return self._column.indexOf(part)
