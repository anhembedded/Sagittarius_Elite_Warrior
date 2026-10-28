"""`EPIC-047E` (charter O5) — the honest line above the VPS tab: host, keys, connected or not, how old the data is.

@details A `NoticeBar` (`ui-presentation-rule.md` §10: a message with a severity icon above a panel's content) that asks its
provider once a second and draws the answer, so an age that grows is drawn without an event. The words are the shell's
(`HostLine`); this widget decides only the icon: information while the link is up and the facts are current, a warning
otherwise. The Bots tab shows none (the bar is hidden until a backend gives it a provider).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_line import HostLine
from Sagittarius_Elite_Warrior.src.support.ui_kit.notice_bar import (
    NoticeBar,
    NoticeKind,
)

#: How often the line is asked for again; fine enough that "updated N s ago" never looks stuck.
REFRESH_MS = 1000


class HostLineBar(NoticeBar):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(NoticeKind.INFORMATION, "barHostLine", parent=parent)
        self._provider: Callable[[], HostLine] | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self.draw_line)
        self.hide()

    def show_line_of(self, provider: Callable[[], HostLine]) -> None:
        """Shows the bar and draws `provider`'s line now and every second after."""
        self._provider = provider
        self.draw_line()
        self.show()
        self._timer.start()

    def draw_line(self) -> None:
        if self._provider is None:
            return
        line = self._provider()
        kind = NoticeKind.INFORMATION if line.ok else NoticeKind.WARNING
        self.show_notice(kind, line.text)
