"""`BOT-206` — the Plan dock's property table as a widget: its groups, rows, values, columns,
row heights, visibility and copy, on the table alone.

The words are the screen's own, so a test reads what the table shows through its own delegate,
formatter and all. The panel's use of the table is `test_plan_panel_property_table.py`.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication
from PySide6.QtWidgets import QAbstractScrollArea, QStyleOptionViewItem, QTreeView
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    TOTAL_PNL_BASIS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_property_grid import (
    COPY_SEPARATOR,
    PlanPropertyGrid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_property_rows import (
    PROPERTY_GROUPS,
)


def _grid(qtbot) -> PlanPropertyGrid:
    grid = PlanPropertyGrid(PROPERTY_GROUPS)
    qtbot.addWidget(grid.view)
    grid.view.resize(420, 600)
    grid.view.show()
    return grid


def _select(grid: PlanPropertyGrid, *keys: str) -> None:
    selection = grid.view.selectionModel()
    selection.clearSelection()
    for key in keys:
        selection.select(
            grid._proxy_index(key, 0),
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows,
        )


def test_the_table_lists_four_groups_each_with_its_rows(qtbot) -> None:
    grid = _grid(qtbot)

    headings = [grid.model.item(row, 0).text() for row in range(grid.model.rowCount())]

    assert headings == ["Readiness", "Plan", "Results", "Holdings"]
    plan = {group.key: [row.key for row in group.rows] for group in PROPERTY_GROUPS}
    assert plan["readiness"] == ["step_connect", "step_design", "step_run"]
    assert {"venue", "symbol", "capital", "stop_loss", "take_profit"} <= set(
        plan["plan"]
    )
    assert {"grid_profit", "total_pnl", "unrealised", "hodl", "commissions"} <= set(
        plan["results"]
    )
    assert plan["holdings"] == ["inventory", "earlier_runs", "last_price"]


def test_every_figure_the_dock_had_is_still_on_it_with_its_old_title(qtbot) -> None:
    grid = _grid(qtbot)

    assert grid.shown_title("total_pnl") == f"Total PnL ({TOTAL_PNL_BASIS})"
    assert grid.shown_title("cycle_average") == "Average per cycle (net of fees)"
    assert grid.shown_title("funding") == "Funding (earned +, paid −)"
    # `BUG-261`: the figure may come from a design not saved yet, so its title no longer says "Saved".
    assert grid.shown_title("grid_step") == "Grid step, top to bottom"


def test_a_row_the_table_does_not_have_is_refused(qtbot) -> None:
    grid = _grid(qtbot)

    with pytest.raises(KeyError, match="margin_mode"):
        grid.set_values({"margin_mode": "Isolated"})


def _painted(grid: PlanPropertyGrid, key: str, column: int) -> QStyleOptionViewItem:
    """The cell as the view's own delegate paints it: its text, alignment and font."""
    option = QStyleOptionViewItem()
    index = grid._proxy_index(key, column)
    grid.view.itemDelegateForIndex(index).initStyleOption(option, index)
    return option


def _side(option: QStyleOptionViewItem) -> Qt.AlignmentFlag:
    return Qt.AlignmentFlag(int(option.displayAlignment)) & (  # type: ignore[attr-defined]
        Qt.AlignmentFlag.AlignHorizontal_Mask
    )


def test_a_text_row_reads_left_and_a_number_row_right_each_in_its_kinds_font(
    qtbot,
) -> None:
    """The owner (2026-10-20): "căn như đề xuất": a symbol and a venue left, a capital, a price,
    a PnL right. The row's kind decides, not the column's."""
    grid = _grid(qtbot)
    grid.set_values({"symbol": "BTCUSDT", "capital": "500", "last_price": "64,500.00"})
    fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()

    symbol, capital = _painted(grid, "symbol", 1), _painted(grid, "capital", 1)

    assert symbol.text == "BTCUSDT" and capital.text == "500"  # type: ignore[attr-defined]
    assert _side(symbol) & Qt.AlignmentFlag.AlignLeft
    assert _side(capital) & Qt.AlignmentFlag.AlignRight
    assert QFont(capital.font).family() == fixed  # type: ignore[attr-defined]
    assert QFont(symbol.font).family() != fixed  # type: ignore[attr-defined]
    assert _side(_painted(grid, "last_price", 1)) & Qt.AlignmentFlag.AlignRight
    assert _side(_painted(grid, "venue", 1)) & Qt.AlignmentFlag.AlignLeft
    assert _side(_painted(grid, "step_design", 1)) & Qt.AlignmentFlag.AlignLeft


def test_property_titles_read_left(qtbot) -> None:
    grid = _grid(qtbot)

    assert _side(_painted(grid, "capital", 0)) & Qt.AlignmentFlag.AlignLeft
    assert _side(_painted(grid, "total_pnl", 0)) & Qt.AlignmentFlag.AlignLeft


def test_a_long_title_wraps_to_the_lines_it_needs_and_a_short_one_does_not(
    qtbot,
) -> None:
    grid = _grid(qtbot)
    view = grid.view

    total = view.visualRect(grid._proxy_index("total_pnl", 0)).height()
    venue = view.visualRect(grid._proxy_index("venue", 0)).height()

    assert total > 2 * venue


def test_the_table_has_no_scroll_bar_of_its_own_and_is_as_tall_as_its_rows(
    qtbot,
) -> None:
    """The panel scrolls once (`ui-presentation-rule.md` §3): `test_bots_view` exempts the table
    from the nested-scroll check on these three properties."""
    grid = _grid(qtbot)
    view = grid.view
    off = Qt.ScrollBarPolicy.ScrollBarAlwaysOff

    assert view.verticalScrollBarPolicy() is off
    assert view.horizontalScrollBarPolicy() is off
    assert (
        view.sizeAdjustPolicy() is QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents
    )
    expanded = view.sizeHint().height()
    view.collapseAll()
    assert view.sizeHint().height() < expanded


def test_a_group_with_no_row_to_show_is_not_shown_and_comes_back_with_a_row(
    qtbot,
) -> None:
    grid = _grid(qtbot)
    holdings = [row.key for row in PROPERTY_GROUPS[3].rows]

    grid.set_rows_shown(holdings, False)
    assert not grid.group_is_shown("holdings")

    grid.set_rows_shown(holdings[:1], True)
    assert grid.group_is_shown("holdings")
    assert grid.row_is_shown(holdings[0]) and not grid.row_is_shown(holdings[1])


def test_rows_are_selectable_several_at_once_and_copy_as_property_tab_value(
    qtbot,
) -> None:
    grid = _grid(qtbot)
    grid.set_values({"symbol": "BTCUSDT", "venue": "Spot Testnet"})
    _select(grid, "venue", "symbol")

    assert grid.copy_text() == (
        f"Venue{COPY_SEPARATOR}Spot Testnet\nSymbol{COPY_SEPARATOR}BTCUSDT"
    )


def test_a_selected_heading_copies_with_its_visible_rows(qtbot) -> None:
    grid = _grid(qtbot)
    grid.set_values({"hodl": "83.33"})
    grid.set_rows_shown(("commissions", "funding"), False)
    selection = grid.view.selectionModel()
    selection.select(
        grid._group_index("results"),
        QItemSelectionModel.SelectionFlag.Select
        | QItemSelectionModel.SelectionFlag.Rows,
    )

    lines = grid.copy_text().splitlines()

    assert lines[0] == "Results"
    assert f"HODL benchmark{COPY_SEPARATOR}83.33" in lines
    assert not any(line.startswith("Commissions") for line in lines)


def test_ctrl_c_on_the_table_puts_the_selected_rows_on_the_clipboard(qtbot) -> None:
    grid = _grid(qtbot)
    grid.set_values({"symbol": "BTCUSDT"})
    _select(grid, "symbol")
    QGuiApplication.clipboard().clear()
    grid.view.setFocus()
    qtbot.waitUntil(grid.view.hasFocus)

    qtbot.keyClick(grid.view, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)

    assert QGuiApplication.clipboard().text() == f"Symbol{COPY_SEPARATOR}BTCUSDT"


def test_the_table_is_a_stock_tree_view_that_does_not_sort(qtbot) -> None:
    grid = _grid(qtbot)

    assert type(grid.view) is QTreeView
    assert not grid.view.isSortingEnabled()
    assert grid.view.rootIsDecorated()


def test_the_plan_heading_says_when_its_figures_are_not_saved(qtbot) -> None:
    grid = _grid(qtbot)

    assert grid.shown_group_title("plan") == "Plan"
    grid.set_group_title("plan", "Plan (not saved)")
    assert grid.shown_group_title("plan") == "Plan (not saved)"
