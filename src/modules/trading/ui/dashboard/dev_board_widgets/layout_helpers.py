"""`BOT-144` — the handful of layout primitives every Dev Board card shares
(a section heading row, a labelled field row, the field/action button
QSS). Split out of `dev_board_panel.py` alongside the cards themselves so
neither `dev_board_panel.py` (which still builds the header and the
Indicators checklist directly) nor any card needs to import the other just
for these.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets import Palette
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import SectionLabel


def field_style() -> str:
    return (
        f"background-color: {Palette.STATE_IDLE_BG}; color: {Palette.TEXT_PRIMARY}; "
        f"border: 1px solid {Palette.STATE_NAV_BORDER}; border-radius: 6px; padding: 0 10px;"
    )


def section_row(title_text: str) -> QHBoxLayout:
    """A section heading in a row of its own — see `SectionLabel`'s own
    docstring for why the heading is a widget, not a hand-drawn tick +
    label pair."""
    row = QHBoxLayout()
    row.setSpacing(6)
    row.addWidget(SectionLabel(title_text, tick=True))
    row.addStretch(1)
    return row


def field_row(label_text: str, field: QWidget) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    label = QLabel(label_text)
    label.setFixedWidth(60)
    label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px; font-weight: bold;")
    layout.addWidget(label)
    layout.addWidget(field, 1)
    return row


def field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
    return label


def action_button_style(accent: str) -> str:
    return (
        f"QPushButton {{ background-color: {Palette.STATE_IDLE_BG}; color: {Palette.TEXT_PRIMARY}; "
        f"border: 1px solid {accent}; border-radius: 6px; min-height: 32px; "
        f"font-size: 12px; }} "
        f"QPushButton:disabled {{ color: {Palette.MUTED}; border-color: {Palette.STATE_NAV_BORDER}; }}"
    )
