"""`BOT-209` — the Plan dock's status banner: one inline message at the top of the dock.

The kit's `NoticeBar` (a styled-panel frame, the platform's message icon, a wrapped label; no
colour of its own), given a `PlanStatus`. It takes no height while it says nothing. It has no
button: what a person can do about the state is a command of the Bots menu (Fix next item, Retry
venue account, the Log dock's View toggle), and a button here would repeat it
(`ui-presentation-rule.md` §6).
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_status import (
    PlanStatus,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.notice_bar import (
    NoticeBar,
    NoticeKind,
)


class PlanStatusBanner(NoticeBar):
    """@brief The one sentence that says where the selected bot stands."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(NoticeKind.INFORMATION, "bannerBotPlanStatus", parent=parent)
        self.setVisible(False)

    def show_status(self, status: PlanStatus) -> None:
        if status.kind is None:
            self.setVisible(False)
            return
        self.show_notice(status.kind, status.text)
        self.setToolTip(status.text)
        self.setVisible(True)
