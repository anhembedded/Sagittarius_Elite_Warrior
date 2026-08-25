"""
@brief `AppLogPanel` — engine's `LogPanel`, wearing this app's clothes.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSize, Qt
from PySide6.QtWidgets import QStyledItemDelegate, QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from sagittarius_engine.extensions.pyside_mvc.widgets import LogPanel

#: Copy/Clear are English here because the buttons have always read that way
#: on screen — see `EPIC-007E`. Everything else user-facing in this app is
#: Vietnamese; these two are the exception the migration preserved rather
#: than quietly translated.
_COPY_TEXT = "Copy"
_CLEAR_TEXT = "Clear"

#: The badge reads "340 EVENTS", not "340". Engine's `LogPanel` cannot guess
#: the unit, so it takes the format.
_BADGE_FORMAT = "{count} EVENTS"

_ICON_SIZE = 12
#: One log line, matching `_LogDelegate`'s old `sizeHint`.
_ROW_HEIGHT = 20


class _LogDelegate(QStyledItemDelegate):
    """
    @brief Paints one log line as `[HH:MM:SS] message`, colouring the message
    by level.

    @details Moved here with the panel in `EPIC-007E`. Engine's `LogPanel`
    deliberately ships no delegate: a log *line*'s shape is this app's — the
    timestamp/level/message roles it reads are `LogListModel`'s vocabulary,
    not a framework's.

    Colours come from `Palette` now. They used to be `Qt.GlobalColor`
    constants (`gray`, `white`, `red`), which the colour guard never saw
    because they are enum members rather than hex literals — a real gap in
    what `EPIC-007D` could reach. The values are near-identical; the point is
    that changing the theme now changes this too.
    """

    def paint(self, painter, option, index) -> None:
        painter.save()
        model = index.model()
        timestamp = model.data(index, model.TimestampRole) or ""
        message = model.data(index, model.MessageRole) or ""
        level = model.data(index, model.LevelRole) or "info"

        rect = option.rect.adjusted(4, 2, -4, -2)
        painter.setPen(Palette.MUTED)
        timestamp_text = f"[{timestamp}]"
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft, timestamp_text)

        timestamp_width = painter.fontMetrics().horizontalAdvance(timestamp_text) + 8
        message_rect = rect.adjusted(timestamp_width, 0, 0, 0)
        painter.setPen(Palette.DANGER if level == "error" else Palette.TEXT_PRIMARY)
        painter.drawText(
            message_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
            str(message),
        )
        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), _ROW_HEIGHT)


class AppLogPanel(LogPanel):
    """
    @brief The log panel every screen in this app uses.

    @details
    Engine's `LogPanel` supplies the shape — a `Card` with a count badge and
    Copy/Clear over a list. This adds the three things that are this app's
    and not a framework's: the line delegate, the icons on the two buttons,
    and the `objectName`s the test suite drives the UI through.

    **It exists so that those three things are written once.** Before
    `EPIC-007E` the panel lived inside `screens/data_management/`, and the
    Backtest and Dev Board screens reached across screen boundaries to import
    it. Nobody decided that; it was just where the widget happened to be
    written first, and each reuse tightened a coupling that no filename
    admitted to. `tests/unit/presentation/ui/test_no_cross_screen_imports.py`
    now fails if it starts again.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(
            title,
            copy_text=_COPY_TEXT,
            clear_text=_CLEAR_TEXT,
            badge_format=_BADGE_FORMAT,
            parent=parent,
        )

        icons = get_icon_loader()
        self.copy_button.setObjectName("btnCopyLog")
        self.copy_button.setIcon(
            icons.get_icon("copy", Palette.TEXT_PRIMARY, _ICON_SIZE)
        )
        self.clear_button.setObjectName("btnClearLog")
        self.clear_button.setIcon(
            icons.get_icon("trash-2", Palette.TEXT_PRIMARY, _ICON_SIZE)
        )

        # The objectNames are not decoration: `test_sanity_ui_e2e` clicks
        # Clear through `findChild(object, "btnClearLog")`, and two more
        # tests find Copy the same way. Renaming them breaks the suite's
        # only handle on this panel.
        self.list_view.setObjectName("logList")
        self.list_view.setItemDelegate(_LogDelegate(self.list_view))

    def row_count(self) -> int:
        """@brief How many lines the bound model holds, or 0 when none is
        bound. Exists so a caller does not have to reach for `_model`."""
        model = self.list_view.model()
        return 0 if model is None else model.rowCount(QModelIndex())
