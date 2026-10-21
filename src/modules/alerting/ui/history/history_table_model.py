"""The Alerts screen's table: one row per stored alert, newest first (`EPIC-036D2`)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.alert_history_report import (
    AlertHistoryRow,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history import history_words
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

_SEVERITY_TONES = {
    Severity.INFO: Tone.NEUTRAL,
    Severity.WARNING: Tone.CAUTION,
    Severity.CRITICAL: Tone.NEGATIVE,
}


class AlertHistoryTableModel(RowTableModel[AlertHistoryRow]):
    """@brief The alerts at or above a severity. Every row read is kept, so changing the
    filter needs no second read."""

    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("at", "Time", ColumnKind.TIMESTAMP),
        ColumnSpec("severity", "Severity", ColumnKind.TEXT),
        ColumnSpec("subject", "About", ColumnKind.TEXT),
        ColumnSpec("alert", "Alert", ColumnKind.TEXT, stretch=True),
        ColumnSpec("delivery", "Delivery", ColumnKind.TEXT),
    )

    def __init__(self) -> None:
        super().__init__()
        self._read: tuple[AlertHistoryRow, ...] = ()
        self._minimum: Severity | None = None

    @property
    def read_count(self) -> int:
        """How many alerts were read, whatever the filter shows."""
        return len(self._read)

    def take_alerts_read(self, rows: Sequence[AlertHistoryRow]) -> None:
        self._read = tuple(rows)
        self._apply_filter()

    def filter_by(self, minimum: Severity | None) -> None:
        self._minimum = minimum
        self._apply_filter()

    def _apply_filter(self) -> None:
        minimum = self._minimum
        self.set_rows(
            [row for row in self._read if minimum is None or row.severity >= minimum]
        )

    def _value(self, row: AlertHistoryRow, column: int) -> DisplayValue:
        values: tuple[DisplayValue, ...] = (
            row.at,
            history_words.SEVERITY_WORDS[row.severity],
            row.subject,
            history_words.alert_text(row.title, row.count),
            history_words.delivery_text(row.outcomes),
        )
        return values[column]

    def _tone(self, row: AlertHistoryRow, column: int) -> Tone:
        """The severity cell reads by tone as well as by its word (Critical, Warning, Info):
        a critical alert is a loss-coloured word, a warning a cautious one."""
        if column != self.column("severity"):
            return Tone.NEUTRAL
        return _SEVERITY_TONES[row.severity]
