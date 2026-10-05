"""The Data mode's two questions about a shard (`EPIC-033J`): Data → Sync
history… and Data → Import data….

A shard is one symbol at one timeframe. Before the Data mode each question
was a rail of always-visible controls — a symbol picker, a timeframe picker,
a hand-styled date range card — that every command read from. A command that
needs more input asks for it, in a dialog named after the command, and ends
with "…" in its menu (`ui-presentation-rule.md` §4, §7). The answers go to
the view model's existing fields (`selectedSymbol`, `selectedInterval`, the
custom range), which the sync and import coordinators already read.

Stock controls only: an editable combo box for the symbol (typing a symbol
the store has never seen is how a first sync starts), a combo box for the
timeframe, `QDateTimeEdit`s in UTC for the range, and a `QDialogButtonBox`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from PySide6.QtCore import QDateTime, QTimeZone
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import DATETIME_FORMAT

#: `DATETIME_FORMAT` (strptime) as Qt writes it.
_QT_FORMAT = "yyyy-MM-dd HH:mm"
#: What the range opens on when the user has not set one: the last week.
_DEFAULT_RANGE = timedelta(days=7)


@dataclass(frozen=True)
class ShardChoice:
    """A symbol at a timeframe."""

    symbol: str
    interval: str


@dataclass(frozen=True)
class SyncChoice:
    """What Sync history… was asked to fetch; no range means "from where the
    store ends" (SPEC-001). Times are `DATETIME_FORMAT` text in UTC, the
    shape the sync coordinator parses."""

    shard: ShardChoice
    start: str | None
    end: str | None


class ShardFields(QWidget):
    """Symbol and timeframe, as two rows of a form."""

    def __init__(
        self,
        symbols: Sequence[str],
        intervals: Sequence[str],
        current: ShardChoice,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.symbol = QComboBox()
        self.symbol.setObjectName("cboShardSymbol")
        self.symbol.setEditable(True)
        self.symbol.addItems(list(symbols))
        self.symbol.setCurrentText(current.symbol)
        self.interval = QComboBox()
        self.interval.setObjectName("cboShardInterval")
        self.interval.addItems(list(intervals))
        self.interval.setCurrentText(current.interval)
        self.form = QFormLayout(self)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.addRow("&Symbol:", self.symbol)
        self.form.addRow("&Timeframe:", self.interval)

    def choice(self) -> ShardChoice:
        return ShardChoice(
            self.symbol.currentText().strip().upper(),
            self.interval.currentText().strip(),
        )


def _utc_edit(moment: datetime) -> QDateTimeEdit:
    edit = QDateTimeEdit(
        QDateTime.fromSecsSinceEpoch(int(moment.timestamp()), QTimeZone.utc())
    )
    edit.setTimeZone(QTimeZone.utc())
    edit.setDisplayFormat(_QT_FORMAT)
    edit.setCalendarPopup(True)
    return edit


def _text_of(edit: QDateTimeEdit) -> str:
    moment = datetime.fromtimestamp(edit.dateTime().toSecsSinceEpoch(), UTC)
    return moment.strftime(DATETIME_FORMAT)


class SyncHistoryDialog(QDialog):
    """Data → Sync history…: which shard, and optionally which range."""

    def __init__(
        self,
        symbols: Sequence[str],
        intervals: Sequence[str],
        current: ShardChoice,
        parent: QWidget | None = None,
        *,
        now: datetime | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dlgSyncHistory")
        self.setWindowTitle("Sync History")
        end = now or datetime.now(UTC)
        self.fields = ShardFields(symbols, intervals, current)
        self.only_range = QCheckBox("Only this &range (UTC)")
        self.only_range.setObjectName("chkSyncRange")
        self.start = _utc_edit(end - _DEFAULT_RANGE)
        self.start.setObjectName("dteSyncFrom")
        self.end = _utc_edit(end)
        self.end.setObjectName("dteSyncTo")
        self.fields.form.addRow(self.only_range)
        self.fields.form.addRow("&From:", self.start)
        self.fields.form.addRow("T&o:", self.end)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("&Sync")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.fields)
        layout.addWidget(self.buttons)
        self.only_range.toggled.connect(self._follow_range)
        self.start.dateTimeChanged.connect(lambda _moment: self._follow_range())
        self.end.dateTimeChanged.connect(lambda _moment: self._follow_range())
        self._follow_range()

    def choice(self) -> SyncChoice:
        if not self.only_range.isChecked():
            return SyncChoice(self.fields.choice(), None, None)
        return SyncChoice(
            self.fields.choice(), _text_of(self.start), _text_of(self.end)
        )

    def _follow_range(self) -> None:
        """The range applies only when checked, and a range that ends before
        it starts cannot be sent (the coordinator would refuse it)."""
        ranged = self.only_range.isChecked()
        self.start.setEnabled(ranged)
        self.end.setEnabled(ranged)
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setEnabled(not ranged or self.start.dateTime() < self.end.dateTime())


class ImportDataDialog(QDialog):
    """Data → Import data…: which shard the file's candles belong to; the
    file is asked next, by the platform's open dialog."""

    def __init__(
        self,
        symbols: Sequence[str],
        intervals: Sequence[str],
        current: ShardChoice,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dlgImportData")
        self.setWindowTitle("Import Data")
        self.fields = ShardFields(symbols, intervals, current)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("&Choose file…")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.fields)
        layout.addWidget(self.buttons)

    def choice(self) -> ShardChoice:
        return self.fields.choice()
