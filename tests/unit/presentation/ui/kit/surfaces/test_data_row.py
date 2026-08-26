"""Tests for `widgets.surfaces.data_row.DataRow`."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Column,
    DataRow,
    RowAction,
    StyleRole,
    Surface,
    Tone,
)

_COLUMNS = (
    Column("Symbol", 22),
    Column("Interval", 10, Qt.AlignmentFlag.AlignCenter),
    Column("Total", 18, Qt.AlignmentFlag.AlignRight),
)


def test_has_one_cell_per_column(qtbot):
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)

    assert row.columns == _COLUMNS
    assert row.cell_texts() == ["", "", ""]


def test_is_not_a_surface(qtbot):
    """A row is content sitting on a table, not a surface of its own.

    It was a `Panel` first, which drew a card background, a border and a
    radius per row — forty stacked cards for one table. Wrapping a row in a
    `Panel` is available to a consumer that wants the frame; removing a
    `Panel`'s frame is not, which is what settles the direction.
    """
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)

    assert isinstance(row, QWidget)
    assert not isinstance(row, Surface)


def test_rejects_an_empty_column_spec(qtbot):
    with pytest.raises(ValueError, match="at least one column"):
        DataRow([])


def test_set_cells_fills_left_to_right(qtbot):
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)

    row.set_cells(["BTCUSDT", "1m", "1,204,551"])

    assert row.cell_texts() == ["BTCUSDT", "1m", "1,204,551"]


def test_set_cells_is_repeatable(qtbot):
    """The whole reason cells are filled rather than passed to the
    constructor: the consumer's gap row takes its data at construction and
    so cannot be refreshed, forcing its dialog to rebuild every row."""
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)

    row.set_cells(["BTCUSDT", "1m", "1"])
    row.set_cells(["ETHUSDT", "1h", "2"])

    assert row.cell_texts() == ["ETHUSDT", "1h", "2"]


@pytest.mark.parametrize("values", [["a"], ["a", "b", "c", "d"], []])
def test_wrong_value_count_is_refused(qtbot, values):
    """Padding or truncating would slide a record's columns out of line
    with the heading above them, and misaligned data still looks like
    data."""
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)

    with pytest.raises(ValueError, match="3 columns"):
        row.set_cells(values)


def test_alignment_comes_from_the_column_spec(qtbot):
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)

    assert row._cells[1].alignment() & Qt.AlignmentFlag.AlignCenter
    assert row._cells[2].alignment() & Qt.AlignmentFlag.AlignRight


def test_actions_emit_their_position(qtbot):
    row = DataRow(
        _COLUMNS,
        actions=[RowAction("KLines"), RowAction("Clear", StyleRole.DANGER_BUTTON)],
    )
    qtbot.addWidget(row)

    with qtbot.waitSignal(row.action_triggered, timeout=1000) as blocker:
        row.action_buttons[1].click()

    assert blocker.args == [1]


def test_actions_take_natural_width_by_default(qtbot):
    row = DataRow(_COLUMNS, actions=[RowAction("Open")])
    qtbot.addWidget(row)

    assert row.layout().stretch(row.layout().count() - 1) == 0


def test_actions_can_claim_a_share_of_the_width(qtbot):
    """A header that lists actions as a column of its own needs the strip to
    occupy that column's share — otherwise the cells expand into its slack
    and stop lining up with the headings that describe them."""
    row = DataRow(
        _COLUMNS, actions=[RowAction("Open"), RowAction("Clear")], action_stretch=26
    )
    qtbot.addWidget(row)

    last = row.layout().count() - 1
    assert row.layout().stretch(last) == 26
    assert row.layout().itemAt(last).layout() is not None
    assert len(row.action_buttons) == 2


def test_a_stretch_with_no_actions_adds_nothing(qtbot):
    row = DataRow(_COLUMNS, action_stretch=26)
    qtbot.addWidget(row)

    assert row.layout().count() == len(_COLUMNS)


def test_an_action_can_be_hidden_per_row(qtbot):
    """The consumer's status row hides its "gaps" button on healthy
    records rather than disabling it."""
    row = DataRow(_COLUMNS, actions=[RowAction("Gaps")])
    qtbot.addWidget(row)

    row.set_action_visible(0, False)

    assert row.action_buttons[0].isVisibleTo(row) is False


def test_a_destructive_action_renders_differently(qtbot, fake_theme_bridge):
    row = DataRow(
        _COLUMNS,
        actions=[RowAction("Sync"), RowAction("Clear", StyleRole.DANGER_BUTTON)],
    )
    qtbot.addWidget(row)

    assert row.action_buttons[0].styleSheet() != row.action_buttons[1].styleSheet()


def test_actions_default_to_the_outline_flavour(qtbot, fake_theme_bridge):
    """Not one row action measured in a real consumer is a filled button —
    repeated down a long table, filled reads as the loudest thing on the
    screen."""
    assert RowAction("Open").role is StyleRole.GHOST_BUTTON


def test_cells_start_as_table_text(qtbot, fake_theme_bridge):
    """Every consumer that left cells unstyled then set the same font size
    by hand; the role carries it instead."""
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)

    assert row.cell(0).styleSheet() != ""


def test_a_cell_tone_keeps_the_role_it_was_given(qtbot, fake_theme_bridge):
    """Whether a status reads as good or bad is decided per record, so it
    cannot be a role — but the size and weight the role gave the cell must
    survive the recolour.

    The rule is appended after the role's closing brace and scoped. A bare
    `color:` written after a block is discarded by Qt outright, which is
    exactly how `BUG-009` broke `StatCard`'s badge.
    """
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)
    row.set_cell_role(2, StyleRole.TABLE_CELL_STRONG)
    before = row.cell(2).styleSheet()

    row.set_cell_tone(2, Tone.NEGATIVE)
    after = row.cell(2).styleSheet()

    assert after.startswith(before)
    assert after.rstrip().endswith("}")


def test_a_cell_colour_names_a_token_not_a_literal(qtbot, fake_theme_bridge):
    """The last resort under `set_cell_tone`: a gap row's duration is accent
    purely to mark it as the notable field, which is not a judgement about
    the value and so not a `Tone`."""
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)
    before = row.cell(0).styleSheet()

    row.set_cell_colour(0, "accent")
    after = row.cell(0).styleSheet()

    assert after.startswith(before)
    assert after.rstrip().endswith("}")


def test_an_unknown_cell_colour_fails_fast(qtbot):
    """Deliberately not on `fake_theme_bridge`, which answers every name.

    Against the real bridge a missing key used to come back as the *string*
    `"None"`, so a typo rendered `color: None;` — a declaration Qt drops in
    silence, leaving the cell uncoloured and nothing reported anywhere.
    """
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)

    with pytest.raises(KeyError):
        row.set_cell_colour(0, "notAToken")


def test_an_action_tone_keeps_the_role_it_was_given(qtbot, fake_theme_bridge):
    row = DataRow(_COLUMNS, actions=[RowAction("Sync")])
    qtbot.addWidget(row)
    before = row.action_buttons[0].styleSheet()

    row.set_action_tone(0, Tone.POSITIVE)
    after = row.action_buttons[0].styleSheet()

    assert after.startswith(before)
    assert after.rstrip().endswith("}")


def test_a_cell_is_reachable_for_what_a_role_cannot_carry(qtbot):
    """A column of figures wants a monospace font — a widget API call, not
    a styling decision, and the reason `cell()` is public at all."""
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)

    font = row.cell(1).font()
    font.setFamily("monospace")
    row.cell(1).setFont(font)

    assert row.cell(1).font().family() == "monospace"


def test_a_cell_can_be_restyled(qtbot, fake_theme_bridge):
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)
    before = row._cells[1].styleSheet()

    row.set_cell_role(1, StyleRole.BADGE)

    assert row._cells[1].styleSheet() != before
