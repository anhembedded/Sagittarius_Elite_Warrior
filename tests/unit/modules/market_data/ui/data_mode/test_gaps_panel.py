"""The Gaps panel (`EPIC-033J`): what Check gaps found, as a table from its
specs, and the gap a repair acts on."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableView
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_widgets.gaps_panel import (
    GapsPanel,
    gap_report,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.configure_item_view import (
    CONFIGURED_PROPERTY,
)

_GAPS = [
    {
        "gap_id": 1,
        "start_time": "2026-10-01 00:00",
        "end_time": "2026-10-01 01:00",
        "fetch_start_time": "2026-09-30 23:59",
        "fetch_end_time": "",
        "duration_text": "1h",
        "missing_candles": 1200,
    },
    {
        "gap_id": 2,
        "start_time": "2026-10-02 00:00",
        "end_time": "2026-10-02 00:30",
        "duration_text": "30m",
        "missing_candles": 30,
    },
]


def test_a_report_says_how_much_is_missing_in_words(qapp):
    report = gap_report("BTCUSDT", "1m", 1230, 98.5, _GAPS)

    assert report.summary == (
        "BTCUSDT (1m): 2 gaps, 1,230 missing candles, 98.50% covered."
    )


def test_a_gap_repairs_its_fetch_range_or_else_the_gap_itself(qapp):
    first, second = gap_report("BTCUSDT", "1m", 0, 0.0, _GAPS).gaps

    assert (first.fetch_start, first.fetch_end) == (
        "2026-09-30 23:59",
        "2026-10-01 01:00",
    )
    assert (second.fetch_start, second.fetch_end) == (
        "2026-10-02 00:00",
        "2026-10-02 00:30",
    )


def test_the_table_is_built_from_its_specs_and_lists_every_gap(qapp):
    panel = GapsPanel()
    table = panel.findChild(QTableView, "tblGaps")

    panel.show_report(gap_report("BTCUSDT", "1m", 1230, 98.5, _GAPS))

    assert table is not None
    assert table.property(CONFIGURED_PROPERTY)
    assert panel.model.rowCount() == len(_GAPS)
    assert [
        panel.model.headerData(column, Qt.Orientation.Horizontal)
        for column in range(panel.model.columnCount())
    ] == ["#", "Start", "End", "Duration", "Missing candles"]


def test_selecting_a_gap_reports_it_and_a_new_report_clears_it(qapp):
    panel = GapsPanel()
    seen: list[object] = []
    panel.gapSelected.connect(seen.append)
    panel.show_report(gap_report("BTCUSDT", "1m", 0, 0.0, _GAPS))

    panel.select_row(1)
    selected = seen[-1]
    panel.show_report(gap_report("BTCUSDT", "1m", 0, 0.0, _GAPS[:1]))

    assert selected is not None
    assert selected.number == 2
    assert seen[-1] is None
