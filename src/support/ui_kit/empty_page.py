"""The page a panel shows in place of its content while it has none.

A filled panel is a `QTableView`, a `QScrollArea` or a chart: stock widgets
that carry a sunken `StyledPanel` frame and paint the theme's `Base` colour.
An empty panel was a bare `QLabel`, which has neither, so on a style that
draws the dock flat (Windows 11) an empty Bots mode read as one undivided
area (`BUG-165`). Every empty page is made here, so it wears what the filled
view wears: the same frame shape and shadow, and the `Base` palette *role* —
never a colour of its own (`ui-presentation-rule.md` §1).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QFrame, QLabel, QStackedWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label


def frame_like_a_view[TLabel: QLabel](label: TLabel) -> TLabel:
    """`label` with the frame and background of a stock item view."""
    label.setFrameShape(QFrame.Shape.StyledPanel)
    label.setFrameShadow(QFrame.Shadow.Sunken)
    label.setBackgroundRole(QPalette.ColorRole.Base)
    label.setAutoFillBackground(True)
    return label


def empty_page(text: str, object_name: str) -> QLabel:
    """A centred, wrapping instruction that fills its panel like a view."""
    label = plain_label(text)
    label.setObjectName(object_name)
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return frame_like_a_view(label)


def frame_instruction_page(stack: QStackedWidget) -> None:
    """Frames the instruction page of an Engine `EmptyStateStack`.

    The Engine builds that page itself and keeps it as page 0 of the stack.
    """
    page = stack.widget(0)
    if not isinstance(page, QLabel):
        raise TypeError("the stack's first page is not the instruction label")
    frame_like_a_view(page)
