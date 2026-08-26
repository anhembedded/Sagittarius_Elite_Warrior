"""Shared field/section/card builders for the Backtest modals, and the
two style constants they and the dialogs share.

Private to this package. Each helper has several callers across the
dialogs, which is the only reason none of them is inlined."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    SelectableCard,
)

_FIELD_STYLE = (
    f"background-color: {Palette.BG_CARD_HEADER}; border: 1px solid {Palette.STATE_NAV_BORDER}; border-radius: 4px; "
    f"color: {Palette.TEXT_PRIMARY}; padding: 0 6px;"
)

_ACCENT = Palette.ACCENT


def _field_row(label_text: str, field: QWidget) -> QVBoxLayout:
    column = QVBoxLayout()
    column.setSpacing(4)
    label = QLabel(label_text)
    label.setStyleSheet(f"color: {Palette.TEXT_PRIMARY}; font-size: 11px;")
    column.addWidget(label)
    field.setFixedHeight(32)
    field.setStyleSheet(_FIELD_STYLE)
    column.addWidget(field)
    return column


def _section_header(icon_text: str, text: str) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(6)
    label = QLabel(text.upper())
    label.setStyleSheet(
        f"color: {_ACCENT}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;"
    )
    row.addWidget(label)
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(
        f"background-color: {Palette.STATE_NAV_BORDER}; border: none; max-height: 1px;"
    )
    row.addWidget(line, 1)
    return row


def _selectable_list_card(
    object_name: str, text: str, subtitle: str, is_selected: bool
) -> SelectableCard:
    """One row of a single-select picker list (Strategy/TimeRange/Timezone)
    — a `SelectableCard` (engine, `pyside_mvc.widgets`) rather than a
    hand-styled `QPushButton`: this "click to choose, accent border when
    selected" shape repeats across 5 Backtest pickers (this list style plus
    the grid style `_selectable_grid_card()` below), enough real instances
    to promote past an app-local escape hatch."""
    card = SelectableCard()
    card.setObjectName(object_name)
    card.selected = is_selected
    card.body_layout.setContentsMargins(12, 6, 12, 6)
    card.body_layout.setSpacing(2)
    title_label = QLabel(text)
    title_label.setStyleSheet(
        f"color: {_ACCENT if is_selected else Palette.TEXT_PRIMARY}; font-size: 12px; "
        f"font-weight: {'bold' if is_selected else 'normal'}; border: none; background: transparent;"
    )
    card.body_layout.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 10px; border: none; background: transparent;"
        )
        card.body_layout.addWidget(subtitle_label)
    card.setMinimumHeight(46 if subtitle else 40)
    return card


def _selectable_grid_card(text: str, is_selected: bool) -> SelectableCard:
    """One cell of a grid picker (Timeframe/Symbol) — same `SelectableCard`
    as `_selectable_list_card()`, centered single-line content instead of
    a stacked title/subtitle."""
    card = SelectableCard()
    card.selected = is_selected
    card.setFixedHeight(38)
    card.body_layout.setContentsMargins(6, 4, 6, 4)
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        f"color: {_ACCENT if is_selected else Palette.TEXT_PRIMARY}; font-size: 12px; "
        f"font-weight: {'bold' if is_selected else 'normal'}; border: none; background: transparent;"
    )
    card.body_layout.addWidget(label)
    return card
