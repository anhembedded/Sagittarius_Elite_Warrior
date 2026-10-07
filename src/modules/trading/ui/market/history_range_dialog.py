"""View → Load range… (`EPIC-033S`): the UTC span a Market chart shows.

A command that needs more input asks for it in a dialog named after the
command (`ui-presentation-rule.md` §4, §7). The fields mirror the Data
mode's Sync history… range (`shard_dialogs.py`): `QDateTimeEdit`s in UTC with
a calendar, and a `QDialogButtonBox` whose OK, named after the action, is
off while the span ends before it starts. A module's UI does not import
another module's, so the two small helpers are this file's own.
"""

from __future__ import annotations

from datetime import UTC, datetime

from PySide6.QtCore import QDateTime, QTimeZone
from PySide6.QtWidgets import (
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

from .chart_history import HistoryRange

#: `QDateTimeEdit`'s display format, minutes as the smallest timeframe.
_QT_FORMAT = "yyyy-MM-dd HH:mm"


def _utc_edit(moment: datetime) -> QDateTimeEdit:
    edit = QDateTimeEdit(
        QDateTime.fromSecsSinceEpoch(int(moment.timestamp()), QTimeZone.utc())
    )
    edit.setTimeZone(QTimeZone.utc())
    edit.setDisplayFormat(_QT_FORMAT)
    edit.setCalendarPopup(True)
    return edit


def _moment_of(edit: QDateTimeEdit) -> datetime:
    return datetime.fromtimestamp(edit.dateTime().toSecsSinceEpoch(), UTC)


class HistoryRangeDialog(QDialog):
    """@brief Which UTC span of `symbol` the chart in front shows."""

    def __init__(
        self, symbol: str, proposed: HistoryRange, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dlgLoadRange")
        self.setWindowTitle("Load Range")
        what = plain_label(f"The stored {symbol} candles that open in this span (UTC):")
        what.setWordWrap(True)
        self.start = _utc_edit(proposed.start)
        self.start.setObjectName("dteRangeFrom")
        self.end = _utc_edit(proposed.end)
        self.end.setObjectName("dteRangeTo")
        form = QFormLayout()
        form.addRow("&From:", self.start)
        form.addRow("T&o:", self.end)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("&Load")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(what)
        layout.addLayout(form)
        layout.addWidget(self.buttons)
        self.start.dateTimeChanged.connect(lambda _moment: self._follow_span())
        self.end.dateTimeChanged.connect(lambda _moment: self._follow_span())
        self._follow_span()

    def choice(self) -> HistoryRange:
        """The span asked for; valid whenever OK could be pressed."""
        return HistoryRange(_moment_of(self.start), _moment_of(self.end))

    def _follow_span(self) -> None:
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setEnabled(self.start.dateTime() < self.end.dateTime())
