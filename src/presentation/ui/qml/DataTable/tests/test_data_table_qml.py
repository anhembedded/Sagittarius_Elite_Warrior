"""Render tests for the shared `DataTable.qml` skeleton (`BOT-124`).

`DataTable` has no opinion on what a row looks like — `rowDelegate` is a
`Component`, which cannot be constructed from Python via `setProperty()`,
so row-rendering coverage loads `_DataTablePreview.qml` (the same file
`preview.py` uses), which wires a real `rowDelegate` in QML. Header and
empty-state coverage loads `DataTable.qml` directly, passing `columns`/
`isEmpty`/`emptyText`/etc. as `initial_properties` — set before the widget
is ever shown, so the first (and only) layout pass already sees the right
values, rather than setting them post-show and waiting an unpredictable
number of extra event-loop turns for `RowLayout`'s polish to catch up
(measured while writing this file: anywhere from one to two turns,
depending what else was pending — exactly the non-deterministic-wait trap
`testing-rule.md` warns against).

Column-width assertions read resulting `width`/`x` geometry rather than the
`Layout.preferredWidth`/`Layout.fillWidth` attached properties directly —
PySide6's generic `QQuickItem.property()` cannot resolve an attached
property by its dotted name (confirmed empirically: it returns `None` for
both), while the actual post-layout geometry those properties produce is a
regular `Item.width`/`Item.x`, which `.property()` reads normally.
"""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101, PLR2004

from __future__ import annotations


def test_header_renders_one_cell_per_column_with_the_right_label(load_qml, qml_item):
    quick, root = load_qml(
        "DataTable.qml",
        initial_properties={
            "columns": [
                {"key": "symbol", "label": "SYMBOL", "width": 120},
                {"key": "side", "label": "SIDE", "width": 90, "align": "right"},
            ]
        },
    )

    symbol_cell = qml_item(root, "dataTableHeaderCell_symbol")
    side_cell = qml_item(root, "dataTableHeaderCell_side")
    assert symbol_cell is not None
    assert symbol_cell.property("text") == "SYMBOL"
    assert side_cell.property("text") == "SIDE"
    quick.close()
    quick.deleteLater()


def test_a_fixed_width_column_gets_exactly_its_declared_width(load_qml, qml_item):
    quick, root = load_qml(
        "DataTable.qml",
        initial_properties={
            "columns": [
                {"key": "symbol", "label": "SYMBOL", "width": 123},
                {"key": "filler", "label": "FILLER", "fillWidth": True},
            ]
        },
    )

    cell = qml_item(root, "dataTableHeaderCell_symbol")
    assert cell.property("width") == 123
    quick.close()
    quick.deleteLater()


def test_a_fillwidth_column_takes_the_remaining_space(load_qml, qml_item):
    quick, root = load_qml(
        "DataTable.qml",
        initial_properties={
            "columns": [
                {"key": "symbol", "label": "SYMBOL", "width": 100},
                {"key": "filler", "label": "FILLER", "fillWidth": True},
            ]
        },
    )

    fixed = qml_item(root, "dataTableHeaderCell_symbol")
    filled = qml_item(root, "dataTableHeaderCell_filler")
    # `filled` starts right after `fixed` ends (with the header `RowLayout`'s
    # own 8px `spacing` between them) and stretches to occupy the rest of
    # the header row's width — the exact behaviour a `fillWidth` column is
    # for.
    header_spacing = 8
    assert (
        filled.property("x")
        == fixed.property("x") + fixed.property("width") + header_spacing
    )
    assert filled.property("width") > fixed.property("width")
    quick.close()
    quick.deleteLater()


def test_two_columns_render_in_the_declared_left_to_right_order(load_qml, qml_item):
    quick, root = load_qml(
        "DataTable.qml",
        initial_properties={
            "columns": [
                {"key": "first", "label": "FIRST", "width": 80},
                {"key": "second", "label": "SECOND", "width": 80},
            ]
        },
    )

    first = qml_item(root, "dataTableHeaderCell_first")
    second = qml_item(root, "dataTableHeaderCell_second")
    assert first.property("x") < second.property("x")
    quick.close()
    quick.deleteLater()


def test_empty_label_hidden_by_default(load_qml, qml_item):
    quick, root = load_qml("DataTable.qml")

    label = qml_item(root, "dataTableEmpty")
    assert label.property("visible") is False
    quick.close()
    quick.deleteLater()


def test_empty_label_shows_the_configured_text_when_isEmpty_is_true(load_qml, qml_item):
    quick, root = load_qml(
        "DataTable.qml",
        initial_properties={"isEmpty": True, "emptyText": "Không có dữ liệu"},
    )

    label = qml_item(root, "dataTableEmpty")
    assert label.property("visible") is True
    assert label.property("text") == "Không có dữ liệu"
    quick.close()
    quick.deleteLater()


def test_list_and_empty_objectnames_are_settable_per_caller(load_qml, qml_item):
    """Each migrated table keeps its own pre-extraction `objectName` —
    nothing currently asserts on either name directly, but a silent rename
    is still an avoidable behavior change."""
    quick, root = load_qml(
        "DataTable.qml",
        initial_properties={
            "listObjectName": "myCustomRows",
            "emptyObjectName": "myCustomEmpty",
        },
    )

    assert qml_item(root, "myCustomRows") is not None
    assert qml_item(root, "myCustomEmpty") is not None
    quick.close()
    quick.deleteLater()


def test_reuse_items_and_row_spacing_reach_the_internal_listview(load_qml, qml_item):
    quick, root = load_qml(
        "DataTable.qml",
        initial_properties={"reuseItems": True, "rowSpacing": 4},
    )

    rows_view = qml_item(root, "dataTableRows")
    assert rows_view.property("reuseItems") is True
    assert rows_view.property("spacing") == 4
    quick.close()
    quick.deleteLater()


def test_preview_wires_a_real_delegate_and_renders_one_item_per_row(load_qml, qml_item):
    """Loads `_DataTablePreview.qml` — the same fixture `preview.py` uses —
    to prove `rowDelegate`/`rowsModel` actually drive the internal
    `ListView`, which a bare `DataTable.qml` load with a Python-set
    `Component` property cannot exercise (`Component` values cannot be
    constructed from Python)."""
    quick, root = load_qml("_DataTablePreview.qml")

    rows_view = qml_item(root, "dataTablePreviewRows")
    assert rows_view.property("count") == 2
    quick.close()
    quick.deleteLater()
