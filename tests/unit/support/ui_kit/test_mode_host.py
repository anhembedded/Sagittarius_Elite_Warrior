"""`EPIC-033C` — a mode of the workbench window holds one of today's screens.

The shell's View menu and Window → Reset layout read the mode's host. A
screen that draws its panels on a surface of its own must answer through that
surface, or View lists nothing and Reset layout resets an empty window.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDockWidget, QLabel, QToolBar, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id
from Sagittarius_Elite_Warrior.src.support.ui_kit.mode_host import ModeHost
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)


class _ViewWithSurface(QWidget):
    """A view shaped like the Bots tab: its panels on a surface that is its
    direct child."""

    def __init__(self) -> None:
        super().__init__()
        self._surface = WorkbenchSurface(surfaces_by_id()["bots"])
        self._surface.place_widget(Place.WORKSPACE, QLabel("chart"))
        self._surface.place_widget(Place.RAIL, QLabel("orders"), title="Orders")
        QVBoxLayout(self).addWidget(self._surface)

    @property
    def surface(self) -> WorkbenchSurface:
        return self._surface


@pytest.fixture
def plain(qapp) -> ModeHost:
    return ModeHost("market", QLabel("a page"))


@pytest.fixture
def with_surface(qapp) -> tuple[ModeHost, _ViewWithSurface]:
    view = _ViewWithSurface()
    return ModeHost("bots", view), view


def test_the_view_sits_in_the_central_frame_and_the_host_is_named_for_the_mode(
    plain: ModeHost,
) -> None:
    # `BOT-169`: the frame holds the mode's message bars above the screen.
    assert plain.view.parentWidget() is plain.centralWidget()
    assert plain.message_bars.parentWidget() is plain.centralWidget()
    assert plain.surface_id == "mode::market"
    assert plain.objectName() == "workbench::mode::market"


def test_a_view_without_a_surface_lists_no_panels(plain: ModeHost) -> None:
    assert plain.dock_toggle_actions() == ()
    assert plain.toolbar_toggle_actions() == ()


def test_a_surface_nested_inside_a_panel_is_not_the_screens(qapp) -> None:
    """Only a direct child is the screen's surface; one deeper belongs to
    whatever panel holds it."""
    view = QWidget()
    panel = QWidget(view)
    QVBoxLayout(panel).addWidget(WorkbenchSurface(surfaces_by_id()["bots"]))

    host = ModeHost("x", view)

    assert host.dock_toggle_actions() == ()


def test_the_view_menu_lists_the_inner_surfaces_panels(
    with_surface: tuple[ModeHost, _ViewWithSurface],
) -> None:
    host, view = with_surface
    assert host.dock_toggle_actions() == view.surface.dock_toggle_actions()
    assert [action.text() for action in host.dock_toggle_actions()] == ["Orders"]


def test_reset_layout_brings_back_the_inner_surfaces_closed_panel(
    with_surface: tuple[ModeHost, _ViewWithSurface],
) -> None:
    host, view = with_surface
    host.show()
    host.capture_default_perspective()
    dock = view.surface.findChild(QDockWidget)
    assert dock is not None
    dock.close()
    assert dock.isHidden()

    assert host.reset_perspective() is True

    assert not dock.isHidden()


def test_reset_layout_brings_back_the_hidden_commands_toolbar_beside_a_surface(
    with_surface: tuple[ModeHost, _ViewWithSurface],
) -> None:
    """The commands toolbar is the host's own, not the surface's: Reset
    layout resets both (the conformance suite found it left hidden)."""
    host, _ = with_surface
    host.add_command(QAction("Run", host))
    host.show()
    host.capture_default_perspective()
    bar = host.findChild(QToolBar, options=Qt.FindChildOption.FindDirectChildrenOnly)
    assert bar is not None
    bar.hide()

    assert host.reset_perspective() is True

    assert not bar.isHidden()


def test_the_commands_toolbar_and_the_panels_are_each_remembered_by_their_host(
    with_surface: tuple[ModeHost, _ViewWithSurface],
) -> None:
    """The window saves one layout per remembered host: the surface's for
    the panels, and this host's own for the commands toolbar, which a
    restart used to bring back shown wherever the user had hidden it."""
    host, view = with_surface
    host.add_command(QAction("Run", host))
    host.show()
    dock = view.surface.findChild(QDockWidget)
    bar = host.findChild(QToolBar, options=Qt.FindChildOption.FindDirectChildrenOnly)
    assert dock is not None and bar is not None
    dock.close()
    bar.hide()

    assert host.remembered_hosts() == (host, view.surface)
    saved = [(each, each.save_perspective()) for each in host.remembered_hosts()]
    dock.show()
    bar.show()

    assert all(each.restore_perspective(blob) for each, blob in saved)
    assert dock.isHidden()
    assert bar.isHidden()


def test_a_plain_view_remembers_its_host_alone(plain: ModeHost) -> None:
    assert plain.remembered_hosts() == (plain,)


def test_a_plain_view_resets_its_own_layout(plain: ModeHost) -> None:
    assert plain.reset_perspective() is False
    plain.capture_default_perspective()
    assert plain.reset_perspective() is True


class _ViewWithAnotherKindOfSurface(QWidget):
    """Settings' shape: a surface of its own that is not a workbench host."""

    def __init__(self) -> None:
        super().__init__()
        QVBoxLayout(self).addWidget(QWidget())


def test_a_surface_that_is_not_a_workbench_host_is_ignored(qapp) -> None:
    host = ModeHost("settings", _ViewWithAnotherKindOfSurface())

    assert host.dock_toggle_actions() == ()
    host.capture_default_perspective()
    assert host.reset_perspective() is True
