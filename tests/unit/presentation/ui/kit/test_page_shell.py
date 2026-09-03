"""Tests for `kit.page_shell.PageShell` — the five-band screen scaffold
(header, optional environment banner, optional context bar, workspace+rail,
optional console)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel, QPushButton, QScrollArea, QSplitter
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import PageShell


@pytest.fixture(autouse=True)
def _reset_environment_banner_factory():
    """`PageShell._environment_banner_factory` is process-wide class state
    (`EPIC-021K` — deliberately, so no screen can forget to wire it, see
    the classmethod's own docstring) — reset it around every test in this
    file so one test's factory can never leak into the next."""
    PageShell.set_environment_banner_factory(None)
    yield
    PageShell.set_environment_banner_factory(None)


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
    pane = splitter.widget(0)
    assert isinstance(pane, QScrollArea)
    assert pane.widget() is main


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
    left, right = splitter.widget(0), splitter.widget(1)
    assert isinstance(left, QScrollArea) and left.widget() is main
    assert isinstance(right, QScrollArea) and right.widget() is rail


def test_set_workspace_again_replaces_the_previous_pair(qtbot):
    shell = PageShell()
    qtbot.addWidget(shell)
    shell.show()

    shell.set_workspace(QLabel("first main"), rail=QLabel("first rail"))
    new_main = QLabel("second main")
    shell.set_workspace(new_main)

    splitter = shell._workspace_container.findChild(QSplitter)
    assert splitter.count() == 1
    pane = splitter.widget(0)
    assert isinstance(pane, QScrollArea)
    assert pane.widget() is new_main


def test_set_workspace_again_does_not_destroy_a_widget_the_caller_still_holds(qtbot):
    """`BUG-`-class regression: `set_workspace()` auto-wraps a raw `main`/
    `rail` in a `QScrollArea` it creates and owns. Calling it again must
    detach that wrapper's *content* first (`QScrollArea.takeWidget()`)
    before discarding the wrapper — an orphaned, unreferenced `QScrollArea`
    is garbage collected immediately, and Qt cascades that deletion to
    whatever widget was still parented inside it. A caller-supplied
    `QScrollArea` (Backtest/Settings/Dashboard's own) must never have its
    content pulled out this way — only a wrapper this method itself
    created."""
    shell = PageShell()
    qtbot.addWidget(shell)
    shell.show()

    kept_alive = QLabel("still needed by the caller")
    shell.set_workspace(kept_alive)
    shell.set_workspace(QLabel("second main"))

    # Would raise RuntimeError ("wrapped C/C++ object ... has been deleted")
    # if the first call's auto-wrapper had cascaded its deletion onto this
    # widget instead of detaching it cleanly.
    assert kept_alive.text() == "still needed by the caller"


def test_a_caller_supplied_scroll_area_is_never_double_wrapped(qtbot):
    shell = PageShell()
    qtbot.addWidget(shell)
    shell.show()

    own_scroll = QScrollArea()
    content = QLabel("backtest-style pre-wrapped content")
    own_scroll.setWidget(content)
    shell.set_workspace(own_scroll)

    splitter = shell._workspace_container.findChild(QSplitter)
    assert splitter.widget(0) is own_scroll
    assert own_scroll.widget() is content


# ---------------------------------------------------------------------------
# Environment banner (`EPIC-021K`) — no per-screen setter; a class-level
# factory registered once by the composition root, applied automatically by
# every `PageShell` built afterward.
# ---------------------------------------------------------------------------


def test_banner_band_is_hidden_when_no_factory_is_registered(qtbot):
    shell = PageShell()
    qtbot.addWidget(shell)
    shell.show()

    assert shell._banner_container.isVisible() is False


def test_banner_band_shows_the_registered_factorys_widget(qtbot):
    PageShell.set_environment_banner_factory(lambda: QLabel("⚠ testnet"))

    shell = PageShell()
    qtbot.addWidget(shell)
    shell.show()

    assert shell._banner_container.isVisible() is True
    label = shell._banner_container.findChild(QLabel)
    assert label is not None
    assert label.text() == "⚠ testnet"


def test_each_shell_gets_its_own_widget_instance_from_the_factory(qtbot):
    """A `QWidget` cannot have two parents — the factory must be called
    once per `PageShell`, not once total."""
    built = []

    def factory():
        widget = QLabel("banner")
        built.append(widget)
        return widget

    PageShell.set_environment_banner_factory(factory)

    first = PageShell()
    second = PageShell()
    qtbot.addWidget(first)
    qtbot.addWidget(second)

    assert len(built) == 2
    assert built[0] is not built[1]


def test_registering_none_stops_new_shells_from_showing_a_banner(qtbot):
    PageShell.set_environment_banner_factory(lambda: QLabel("banner"))
    PageShell.set_environment_banner_factory(None)

    shell = PageShell()
    qtbot.addWidget(shell)
    shell.show()

    assert shell._banner_container.isVisible() is False
