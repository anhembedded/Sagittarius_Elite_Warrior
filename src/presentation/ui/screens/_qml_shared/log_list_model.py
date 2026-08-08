from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal, Slot

#: Log level -> the Lucide icon name LogPanel.qml renders beside the line.
#: Unknown levels fall back to "info", mirroring MonitorCard's old behavior.
LEVEL_ICONS = {
    "info": "info",
    "error": "triangle-alert",
    "success": "circle-check-big",
}
_DEFAULT_LEVEL = "info"

#: Keeps memory bounded during long live-stream sessions. The QtWidgets
#: MonitorCard had no cap because QTextEdit silently absorbed it; a model
#: backing a ListView should not grow without limit.
MAX_ENTRIES = 500


@dataclass(frozen=True)
class LogEntry:
    timestamp: str
    message: str
    level: str

    @property
    def icon(self) -> str:
        return LEVEL_ICONS.get(self.level, LEVEL_ICONS[_DEFAULT_LEVEL])


class LogListModel(QAbstractListModel):
    """
    @brief Backs LogPanel.qml — a timestamped, leveled message list shared by
    every screen that shows a log (Database sync log, Dev Board monitor).

    @details
    Replaces MonitorCard's QTextEdit-with-inline-base64-PNG approach: the
    icon is now just a name the QML delegate resolves through the
    `image://icons/...` provider, so no HTML string building and no
    per-line image encoding.
    """

    MessageRole = Qt.ItemDataRole.UserRole + 1
    TimestampRole = Qt.ItemDataRole.UserRole + 2
    LevelRole = Qt.ItemDataRole.UserRole + 3
    IconRole = Qt.ItemDataRole.UserRole + 4

    _ROLE_NAMES = {
        MessageRole: b"message",
        TimestampRole: b"timestamp",
        LevelRole: b"level",
        IconRole: b"icon",
    }

    countChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._entries: list[LogEntry] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._entries)

    def roleNames(self) -> dict:
        return dict(self._ROLE_NAMES)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._entries):
            return None

        entry = self._entries[index.row()]
        if role == self.MessageRole:
            return entry.message
        if role == self.TimestampRole:
            return entry.timestamp
        if role == self.LevelRole:
            return entry.level
        if role == self.IconRole:
            return entry.icon
        return None

    def append(self, message: str, level: str = _DEFAULT_LEVEL) -> None:
        """Appends one line, trimming the oldest once MAX_ENTRIES is reached."""
        if len(self._entries) >= MAX_ENTRIES:
            self.beginRemoveRows(QModelIndex(), 0, 0)
            self._entries.pop(0)
            self.endRemoveRows()

        position = len(self._entries)
        self.beginInsertRows(QModelIndex(), position, position)
        self._entries.append(
            LogEntry(
                timestamp=datetime.now().strftime("%H:%M:%S"),
                message=message,
                level=level,
            )
        )
        self.endInsertRows()
        self.countChanged.emit()

    @Slot()
    def clear(self) -> None:
        """Callable from QML — the panel's own Clear button needs no
        Presenter round-trip, matching how MonitorCard wired its clear
        button directly in the View."""
        self.beginResetModel()
        self._entries.clear()
        self.endResetModel()
        self.countChanged.emit()

    @property
    def entries(self) -> list[LogEntry]:
        return list(self._entries)
