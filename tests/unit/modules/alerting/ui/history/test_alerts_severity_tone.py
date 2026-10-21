"""`EPIC-036D5` — the severity cell of the Alerts table reads by tone as well as by its word.
The word is always there (colour is never the only signal, `ui-presentation-rule.md` §1)."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.alert_history_report import (
    AlertHistoryRow,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history.history_table_model import (
    AlertHistoryTableModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone

_AT = datetime(2026, 10, 21, tzinfo=UTC)


def _row(severity: Severity) -> AlertHistoryRow:
    return AlertHistoryRow(
        1, _AT, AlertKind.BOT_HALTED, severity, "bot", "title", 1, ()
    )


@pytest.mark.parametrize(
    ("severity", "tone"),
    [
        (Severity.CRITICAL, Tone.NEGATIVE),
        (Severity.WARNING, Tone.CAUTION),
        (Severity.INFO, Tone.NEUTRAL),
    ],
)
def test_the_severity_cell_has_the_tone_of_its_severity(
    qapp, severity: Severity, tone: Tone
) -> None:
    model = AlertHistoryTableModel()

    assert model._tone(_row(severity), model.column("severity")) is tone


def test_no_other_cell_is_toned(qapp) -> None:
    model = AlertHistoryTableModel()
    row = _row(Severity.CRITICAL)

    assert {
        model._tone(row, model.column(k))
        for k in ("at", "subject", "alert", "delivery")
    } == {Tone.NEUTRAL}


def test_a_critical_alert_still_says_critical_in_words(qapp) -> None:
    model = AlertHistoryTableModel()
    model.take_alerts_read([_row(Severity.CRITICAL)])

    index = model.index(0, model.column("severity"))

    assert model.data(index, Qt.ItemDataRole.DisplayRole) == "Critical"
