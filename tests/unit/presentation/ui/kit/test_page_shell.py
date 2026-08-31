"""Tests for `kit.page_shell.PageShell` — the four-band screen scaffold
(header, optional context bar, workspace+rail, optional console)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QSplitter
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import PageShell


def test_header_shows_title_and_hides_subtitle_when_empty(qtbot):
    shell = PageShell()
    qtbot.addWidget(shell)
    shell.show()

    shell.set_header("Backtest Engine")

    assert shell._title_label.text() == "Backtest Engine"
    assert shell._subtitle_label.isVisible() is False


def test_header_shows_subtitle_when_given(qtbot):
    shell = PageShell()
    qtbot.addWidget(shell)
    shell.show()

    shell.set_header("Backtest Engine", "Chiến lược EMA Crossover")

    assert shell._subtitle_label.text() == "Chiến lược EMA Crossover"
    assert shell._subtitle_label.isVisible() is True


def test_header_actions_replace_on_each_call(qtbot):
    shell = PageShell()
    qtbot.addWidget(shell)
    shell.show()

    first = QPushButton("Run")
    shell.set_header("Backtest Engine", actions=first)
    assert shell._header_actions_row.count() == 1

    second = QPushButton("Save")
    shell.set_header("Backtest Engine", actions=second)

    assert shell._header_actions_row.count() == 1
    assert shell._header_actions_row.itemAt(0).widget() is second


def test_context_bar_is_hidden_until_set(qtbot):
    shell = PageShell()
    qtbot.addWidget(shell)
    shell.show()

    assert shell._context_bar_container.isVisible() is False

    shell.set_context_bar(QLabel("Symbol: ETHUSDT"))
    assert shell._context_bar_container.isVisible() is True

    shell.set_context_bar(None)
    assert shell._context_bar_container.isVisible() is False


def test_console_is_hidden_until_set(qtbot):
    shell = PageShell()
    qtbot.addWidget(shell)
    shell.show()

    assert shell._console_container.isVisible() is False

    shell.set_console(QLabel("log"))
    assert shell._console_container.isVisible() is True

    shell.set_console(None)
    assert shell._console_container.isVisible() is False


def test_workspace_with_no_rail_is_a_single_pane(qtbot):
    shell = PageShell()
    qtbot.addWidget(shell)
    shell.show()

    main = QLabel("main content")
    shell.set_workspace(main)

    splitter = shell._workspace_container.findChild(QSplitter)
    assert splitter is not None
    assert splitter.count() == 1
    assert splitter.widget(0) is main


def test_workspace_rail_always_lands_on_the_right(qtbot):
    """The one structural constraint this shell exists to enforce: there is
    no parameter that puts the rail anywhere but the second (right) pane of
    the splitter."""
    shell = PageShell()
    qtbot.addWidget(shell)
    shell.show()

    main = QLabel("main content")
    rail = QLabel("rail content")
    shell.set_workspace(main, rail=rail)

    splitter = shell._workspace_container.findChild(QSplitter)
    assert splitter.count() == 2
    assert splitter.widget(0) is main
    assert splitter.widget(1) is rail


def test_set_workspace_again_replaces_the_previous_pair(qtbot):
    shell = PageShell()
    qtbot.addWidget(shell)
    shell.show()

    shell.set_workspace(QLabel("first main"), rail=QLabel("first rail"))
    new_main = QLabel("second main")
    shell.set_workspace(new_main)

    splitter = shell._workspace_container.findChild(QSplitter)
    assert splitter.count() == 1
    assert splitter.widget(0) is new_main
