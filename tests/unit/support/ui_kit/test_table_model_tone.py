"""`EPIC-043C`: a table says what a cell means with `RowTableModel._tone`, and the
colour is the meaning table's own on the application's palette, never the model's."""

from __future__ import annotations

from typing import ClassVar

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from Sagittarius_Elite_Warrior.src.support.ui_kit import meaning_colours
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    sign_tone,
    tone_colour,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

_FOREGROUND = Qt.ItemDataRole.ForegroundRole


class _PnlTable(RowTableModel[float]):
    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("name", "Name", ColumnKind.TEXT),
        ColumnSpec("pnl", "PnL", ColumnKind.MONEY),
    )

    def _value(self, row: float, column: int) -> DisplayValue:
        return ("row", row)[column]

    def _tone(self, row: float, column: int) -> Tone:
        return sign_tone(row) if column == 1 else Tone.NEUTRAL


class _PlainTable(RowTableModel[float]):
    """A table that never says what a cell means, and answers its own colour."""

    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("name", "Name", ColumnKind.TEXT),
    )

    def _value(self, row: float, column: int) -> DisplayValue:
        return "row"

    def _role_data(self, row: float, column: int, role: int) -> object:
        return QColor("hotpink") if role == _FOREGROUND else None


def _on(base: str, monkeypatch: pytest.MonkeyPatch) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Base, QColor(base))
    monkeypatch.setattr(QGuiApplication, "palette", staticmethod(lambda: palette))
    return palette


def _colours(model: RowTableModel[float], column: int) -> list[object]:
    return [model.data(model.index(r, column), _FOREGROUND) for r in range(3)]


@pytest.mark.parametrize("base", ["white", "black"])
def test_a_cell_takes_the_meaning_tables_colour_on_the_palette(
    qapp, base: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    palette = _on(base, monkeypatch)
    table = _PnlTable()
    table.set_rows([3.0, -2.0, 0.0])

    assert _colours(table, 1) == [
        tone_colour(Tone.POSITIVE, palette),
        tone_colour(Tone.NEGATIVE, palette),
        None,
    ]
    assert _colours(table, 0) == [None, None, None]


def test_the_colour_follows_a_change_of_scheme_without_the_rows_changing(
    qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    table = _PnlTable()
    table.set_rows([3.0])
    light = _on("white", monkeypatch)
    on_light = table.data(table.index(0, 1), _FOREGROUND)
    dark = _on("black", monkeypatch)
    on_dark = table.data(table.index(0, 1), _FOREGROUND)

    assert on_light == tone_colour(Tone.POSITIVE, light)
    assert on_dark == tone_colour(Tone.POSITIVE, dark)
    assert on_light != on_dark


def test_in_high_contrast_the_platform_keeps_every_colour(
    qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    _on("white", monkeypatch)
    monkeypatch.setattr(meaning_colours, "is_high_contrast", lambda: True)
    table = _PnlTable()
    table.set_rows([3.0, -2.0])

    assert _colours(table, 1)[:2] == [None, None]


def test_a_table_that_names_no_tone_keeps_its_own_colour(qapp) -> None:
    table = _PlainTable()
    table.set_rows([1.0])

    assert table.data(table.index(0, 0), _FOREGROUND) == QColor("hotpink")


def test_the_text_is_untouched_by_the_tone(qapp) -> None:
    table = _PnlTable()
    table.set_rows([3.0])

    assert table.data(table.index(0, 1), Qt.ItemDataRole.DisplayRole) == 3.0
