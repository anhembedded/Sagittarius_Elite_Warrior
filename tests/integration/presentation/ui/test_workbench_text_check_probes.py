"""Probes for the conformance suite's text checks (`EPIC-033N`): each check,
run on a hand-built window, sees the fault it exists to catch, and passes
the same window once the fault is gone.

Retire when: the checks they probe are retired with the conformance suite.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QMainWindow,
    QMenu,
    QTableView,
    QTabWidget,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_text_checks import (
    column_problems,
    combo_problems,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_widget_checks import (
    toolbar_text_problems,
)


def _table(qtbot, width: int) -> tuple[QWidget, QTableView]:
    page = QWidget()
    qtbot.addWidget(page)
    view = QTableView(page)
    view.setObjectName("tblProbe")
    model = QStandardItemModel(1, 3, view)
    model.setHorizontalHeaderLabels(["Symbol", "Last price", "Volume"])
    view.setModel(model)
    view.resizeColumnsToContents()
    QVBoxLayout(page).addWidget(view)
    page.resize(width, 200)
    page.show()
    return page, view


def test_a_column_cut_short_or_past_the_edge_is_seen(qtbot) -> None:
    page, view = _table(qtbot, 600)
    assert column_problems(page, page) == []

    header = view.horizontalHeader()
    header.resizeSection(0, header.minimumSectionSize())
    squeezed = header.minimumSectionSize()
    content = header.sectionSizeHint(0)
    expected = f"QTableView 'tblProbe': column 'Symbol' is {squeezed} px, its content"
    assert column_problems(page, page) == [f"{expected} {content} px"]

    narrow, cut = _table(qtbot, 120)
    cut.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    assert any(
        "runs past the view's edge" in p for p in column_problems(narrow, narrow)
    )


def test_a_column_the_view_scrolls_to_is_not_past_the_edge(qtbot) -> None:
    """`BUG-245`, `ui-presentation-rule.md` §9: a table narrower than its columns scrolls."""
    narrow, _ = _table(qtbot, 120)

    assert column_problems(narrow, narrow) == []


def test_a_table_tabbed_behind_another_is_not_measured(qtbot) -> None:
    """Qt keeps a hidden tab page "visible" at its minimum width; it is measured in front."""
    page = QWidget()
    qtbot.addWidget(page)
    tabs = QTabWidget(page)
    front, behind = QWidget(), QTableView()
    behind.setObjectName("tblBehind")
    model = QStandardItemModel(1, 3, behind)
    model.setHorizontalHeaderLabels(["Symbol", "Last price", "Volume"])
    behind.setModel(model)
    behind.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    tabs.addTab(front, "Front")
    tabs.addTab(behind, "Behind")
    tabs.resize(120, 200)
    page.resize(120, 200)
    page.show()
    behind.horizontalHeader().resizeSection(2, 400)

    assert column_problems(page, page) == []

    tabs.setCurrentWidget(behind)
    assert any("runs past the view's edge" in p for p in column_problems(page, page))


def test_a_wrapping_tree_may_have_a_column_narrower_than_one_line(qtbot) -> None:
    """The Plan's checks wrap a long finding over lines instead of eliding it (`BUG-245`); a
    table's `wordWrap()` is on by default and says nothing."""
    page = QWidget()
    qtbot.addWidget(page)
    tree = QTreeView(page)
    tree.setObjectName("tvProbe")
    model = QStandardItemModel(1, 2, tree)
    model.setHorizontalHeaderLabels(["Check", "Finding of some length"])
    tree.setModel(model)
    QVBoxLayout(page).addWidget(tree)
    page.resize(600, 200)
    page.show()
    tree.header().resizeSection(0, tree.header().minimumSectionSize())
    assert column_problems(page, page) != []

    tree.setWordWrap(True)

    assert column_problems(page, page) == []


def test_a_combo_too_narrow_for_its_choice_is_seen(qtbot) -> None:
    page = QWidget()
    qtbot.addWidget(page)
    combo = QComboBox(page)
    combo.setObjectName("comboProbe")
    combo.addItem("UTC (Coordinated Universal Time)")
    combo.adjustSize()
    page.show()
    assert combo_problems(page, page) == []

    combo.resize(60, combo.height())

    found = combo_problems(page, page)
    assert len(found) == 1
    assert found[0].startswith("QComboBox 'comboProbe' shows ")


def test_a_toolbar_action_worded_unlike_its_menu_item_is_seen(qtbot) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)
    menu = QMenu("&View", window)
    window.menuBar().addMenu(menu)
    menu.addAction(QAction("&Equity curve", window))
    menu.addAction(QAction("&Volume", window))
    menu.addAction(QAction("&More timeframes…", window))
    bar = QToolBar("Chart", window)
    bar.setObjectName("chart")
    window.addToolBar(bar)
    bar.addAction("Equity Curve")
    bar.addAction("Volume")
    bar.addAction("More timeframes")
    bar.addAction("Crosshair")  # in no menu: `toolbar_actions_in_a_menu`'s

    assert toolbar_text_problems(window, window) == [
        "'Equity Curve' on toolbar 'chart' reads 'Equity curve' in its menu"
    ]
