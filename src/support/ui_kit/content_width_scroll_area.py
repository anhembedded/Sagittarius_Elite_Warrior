"""A page's one scroll area: as wide as its content needs, scrolling down and never across.

A `QScrollArea` reports a tiny minimum size, so a splitter or a dialog could squeeze it narrower than
its content and cut the content's right edge instead of showing it (`BUG-246`: the Bots plan column).
This one asks for the content's width (and the vertical bar's) and leaves the height free: a wrapped
sentence that needs more height than the page has scrolls whole, because a scroll area asks its
content's `heightForWidth` (`BOT-225`: the Options dialog's refused-key sentence).

Capability: Scroll a page down only, keeping the width its content needs
    Also: scroll area, page scroll, wrapped text cut, minimum width, heightForWidth, splitter squeeze
    Use: ContentWidthScrollArea
    User: src/modules/bots/ui/bots_screen/plan_column.py
    Status: stable
"""

from __future__ import annotations

from typing import override

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QScrollArea, QWidget


class ContentWidthScrollArea(QScrollArea):
    """@brief A resizable scroll area with no horizontal bar that never gets narrower than its content."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    @override
    def minimumSizeHint(self) -> QSize:
        """As wide as the content needs and no wider: a pane that is given less would cut the
        content's right edge instead of showing it."""
        content = self.widget()
        base = super().minimumSizeHint()
        if content is None:
            return base
        extra = self.frameWidth() * 2 + self.verticalScrollBar().sizeHint().width()
        return QSize(content.minimumSizeHint().width() + extra, base.height())
