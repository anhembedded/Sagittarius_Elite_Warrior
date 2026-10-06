"""Probes for the workbench conformance checks (`EPIC-033B`/`033C`, `BOT-155`):
each check, run on a hand-built window, sees the fault it exists to catch.
Split from `test_workbench_conformance.py`, which boots the app and holds
the ratchet, so neither file passes the 400-line ceiling.

Retire when: the checks they probe are retired with the conformance suite.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QMenu,
    QPushButton,
    QStackedWidget,
    QToolBar,
    QToolButton,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_commands import (
    MENU_EQUIVALENT,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_layout_checks import (
    fit_problems,
    object_name_problems,
    rearrange,
    reset_layout_problems,
    restart_problems,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_widget_checks import (
    LONE_AMPERSAND,
    access_key_problems,
    control_height_problems,
    duplicate_button_problems,
    separator_problems,
    style_sheet_problems,
    toolbar_in_menu_problems,
    toolbar_problems,
    view_menu_problems,
)


def test_a_lone_ampersand_is_a_mnemonic_and_a_doubled_one_is_not() -> None:
    assert LONE_AMPERSAND.search("Data & stream")
    assert not LONE_AMPERSAND.search("Data && stream")
    assert not LONE_AMPERSAND.search("&File")


def test_a_shared_or_missing_access_key_is_seen(qtbot) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)
    menu = QMenu("&File", window)
    window.menuBar().addMenu(menu)
    for text in ("&Open", "&Options", "Save", "&Print", "Pop"):
        menu.addAction(text)
    recent = QMenu("&Recent", menu)
    menu.addMenu(recent)
    recent.addAction("Clear")

    assert access_key_problems(window, window) == [
        "File: ['Open', 'Options'] share the access key 'o'",
        "File → 'Save' has no access key",
        "File → Recent → 'Clear' has no access key",
    ]


def test_a_separator_at_an_end_or_doubled_is_seen(qtbot) -> None:
    """`BOT-157`: a separator only ever divides two groups."""
    window = QMainWindow()
    qtbot.addWidget(window)
    menu = QMenu("&View", window)
    window.menuBar().addMenu(menu)
    menu.addSeparator()
    menu.addAction("&Spot market")
    menu.addSeparator()
    menu.addSeparator()
    menu.addAction("Load &older candles")
    chart = QMenu("C&hart", menu)
    menu.addMenu(chart)
    chart.addAction("&Go live")
    chart.addSeparator()
    menu.addSeparator()

    assert separator_problems(window, window) == [
        "View: starts with a separator",
        "View: ends with a separator",
        "View: two separators together",
        "View → Chart: ends with a separator",
    ]


def test_one_separator_between_two_groups_is_not_a_finding(qtbot) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)
    menu = QMenu("&View", window)
    window.menuBar().addMenu(menu)
    menu.addAction("&Spot market")
    menu.addSeparator()
    menu.addAction("Load &older candles")

    assert separator_problems(window, window) == []


def test_a_styled_oversized_button_in_a_toolbar_is_seen(qtbot) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)
    bar = QToolBar("Top", window)
    window.addToolBar(bar)
    button = QPushButton("Reload")
    button.setStyleSheet("background: yellow")
    button.setFixedHeight(60)
    bar.addWidget(button)
    window.show()
    assert toolbar_problems(window, window)
    assert style_sheet_problems(window, window)
    assert control_height_problems(window, window)


def test_an_overflowing_toolbar_s_own_extension_button_is_not_a_finding(qtbot) -> None:
    """Qt stretches its overflow button to the bar's height (`BOT-155`); an
    app control made too tall beside it is still seen."""
    window = QMainWindow()
    qtbot.addWidget(window)
    bar = QToolBar("Chart", window)
    window.addToolBar(bar)
    for n in range(30):
        bar.addAction(f"Layer {n}")
    window.resize(200, 200)
    window.show()
    qtbot.waitUntil(
        lambda: any(
            b.isVisible()
            for b in bar.findChildren(QToolButton, "qt_toolbar_ext_button")
        )
    )
    assert control_height_problems(window, window) == []

    tall = QPushButton("Tall")
    tall.setFixedHeight(60)
    bar.insertWidget(bar.actions()[0], tall)  # first, so it is not overflowed
    qtbot.waitUntil(lambda: control_height_problems(window, window) != [])


def test_a_toolbar_action_in_no_menu_is_seen(qtbot) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)
    menu = QMenu("&View", window)
    window.menuBar().addMenu(menu)
    shared = QAction("&Zoom in", window)
    menu.addAction(shared)
    menu.addAction(QAction("Re&set zoom", window))
    menu.addAction(QAction("&More timeframes…", window))
    bar = QToolBar("Chart", window)
    bar.setObjectName("chart")
    window.addToolBar(bar)
    bar.addAction(shared)
    bar.addAction("Reset zoom")
    bar.addSeparator()
    bar.addWidget(QPushButton("Widget"))
    bar.addAction("Crosshair")
    # A favourite reached through a chooser, and one whose chooser is not
    # in a menu (`BOT-156`).
    bar.addAction("1h").setProperty(MENU_EQUIVALENT, "More timeframes…")
    bar.addAction("4h").setProperty(MENU_EQUIVALENT, "More symbols…")

    assert toolbar_in_menu_problems(window, window) == [
        "'Crosshair' on toolbar 'chart' is in no menu",
        "'4h' on toolbar 'chart' is in no menu",
    ]


def test_a_button_named_like_a_contributed_command_is_seen(qtbot) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)
    for text, name in (
        ("&Run backtest", "action::backtesting.backtest.run"),
        ("&Options", "action::workbench.options"),
    ):
        live = QAction(text, window)
        live.setObjectName(name)
        window.addAction(live)
    QAction("S&top", window).setObjectName("action::other.mode.stop")
    page = QWidget(window)
    QPushButton("Stop", page)
    QPushButton("Run backtest", page)
    QPushButton("Options", page)
    QPushButton("Pick dates", page)

    assert duplicate_button_problems(window, page) == [
        "button 'Run backtest' duplicates the command of the same name"
    ]


def test_a_nameless_dock_and_two_toolbars_sharing_a_name_are_seen(qtbot) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)
    window.setObjectName("host")
    window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, QDockWidget("Orders"))
    for title in ("Top", "Chart"):
        bar = QToolBar(title)
        bar.setObjectName("bar")
        window.addToolBar(bar)
    named = QDockWidget("Fills")
    named.setObjectName("fills")
    # A toolbar inside a panel is the panel's content, not the window's.
    named.setWidget(QToolBar("Inside"))
    window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, named)

    assert object_name_problems(window, window) == [
        "QDockWidget 'Orders' in 'host' has no object name",
        "'bar' names 2 bars in 'host'",
    ]


def _window_with_reset_layout(qtbot) -> tuple[QMainWindow, QAction]:
    """A dock, a toolbar, and a Window → Reset layout that does nothing yet."""
    window = QMainWindow()
    qtbot.addWidget(window)
    window.setCentralWidget(QWidget())
    dock = QDockWidget("Orders")
    dock.setObjectName("orders")
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
    bar = QToolBar("Top")
    bar.setObjectName("top")
    window.addToolBar(bar)
    window.show()
    menu = QMenu("&Window", window)
    window.menuBar().addMenu(menu)
    reset = QAction("&Reset layout", window)
    menu.addAction(reset)
    return window, reset


def test_a_reset_layout_that_restores_nothing_is_seen(qtbot) -> None:
    good, reset = _window_with_reset_layout(qtbot)
    default = good.saveState()
    reset.triggered.connect(lambda: good.restoreState(default))
    broken, _ = _window_with_reset_layout(qtbot)
    bare = QMainWindow()
    qtbot.addWidget(bare)

    assert reset_layout_problems(good, good) == []
    found = reset_layout_problems(broken, broken)
    assert any(line.startswith("/orders is ") for line in found), found
    assert any(line.startswith("/top is ") for line in found), found
    assert reset_layout_problems(bare, bare) == ["no Window → Reset layout command"]


def test_a_host_that_does_not_restore_after_a_restart_is_seen(qtbot) -> None:
    """The probe for `restart_problems`, which `test_main_window_state.py`
    runs on the booted app: a second window that restores the first one's
    saved state passes; one that restores nothing is named, bar by bar."""
    closing, _ = _window_with_reset_layout(qtbot)
    closed_with = rearrange(closing)
    saved = closing.saveState()
    restoring, _ = _window_with_reset_layout(qtbot)
    forgetting, _ = _window_with_reset_layout(qtbot)

    assert restoring.restoreState(saved)
    assert restart_problems(closed_with, restoring) == []
    found = restart_problems(closed_with, forgetting)
    assert any(line.startswith("/orders is ") for line in found), found
    assert any(line.startswith("/top is ") for line in found), found


def test_a_mode_wider_than_the_window_is_seen(qtbot) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)
    page = QWidget()
    window.setCentralWidget(page)
    assert fit_problems(window, page, QSize(1024, 700)) == []

    page.setMinimumWidth(1100)

    assert fit_problems(window, page, QSize(1024, 700))
    assert fit_problems(window, page, QSize(1366, 768)) == []


def test_a_dock_with_no_view_toggle_is_seen_on_the_surface_that_shows(qtbot) -> None:
    """`EPIC-033I`: a mode with a surface per venue shows one; a dock of the
    hidden one is measured when it shows, a dock of the shown one now, and
    a dock the person closed is still measured."""
    window = QMainWindow()
    qtbot.addWidget(window)
    window.menuBar().addMenu(QMenu("&View", window))
    stack = QStackedWidget()
    window.setCentralWidget(stack)
    shown, hidden = QMainWindow(), QMainWindow()
    for surface, title in ((shown, "Orders"), (hidden, "Assets")):
        surface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, QDockWidget(title))
        stack.addWidget(surface)
    closed = QDockWidget("Fills")
    shown.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, closed)
    window.show()
    closed.hide()

    assert view_menu_problems(window, stack) == [
        "dock 'Orders' has no toggle in View",
        "dock 'Fills' has no toggle in View",
    ]

    stack.setCurrentWidget(hidden)

    assert view_menu_problems(window, stack) == ["dock 'Assets' has no toggle in View"]
