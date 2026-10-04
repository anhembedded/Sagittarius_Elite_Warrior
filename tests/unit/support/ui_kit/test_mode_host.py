"""`EPIC-033C` — a mode of the workbench window holds one of today's screens.

The shell's View menu and Window → Reset layout read the mode's host. A
screen that draws its panels on a surface of its own must answer through that
surface, or View lists nothing and Reset layout resets an empty window.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QDockWidget, QLabel, QVBoxLayout, QWidget
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
        self._surface = WorkbenchSurface(surfaces_by_id()["dev_board"])
        self._surface.place_widget(Place.WORKSPACE, QLabel("chart"))
        self._surface.place_widget(Place.RAIL, QLabel("orders"), title="Orders")
        QVBoxLayout(self).addWidget(self._surface)

    @property
    def surface(self) -> WorkbenchSurface:
        return self._surface


@pytest.fixture
def plain(qapp) -> ModeHost:
    return ModeHost("watchlist", QLabel("a page"))


@pytest.fixture
def with_surface(qapp) -> tuple[ModeHost, _ViewWithSurface]:
    view = _ViewWithSurface()
    return ModeHost("bots", view), view


def test_the_view_is_the_central_widget_and_the_host_is_named_for_the_mode(
    plain: ModeHost,
) -> None:
    assert plain.centralWidget() is plain.view
    assert plain.surface_id == "mode::watchlist"
    assert plain.objectName() == "workbench::mode::watchlist"


def test_a_view_without_a_surface_lists_no_panels(plain: ModeHost) -> None:
    assert plain.dock_toggle_actions() == ()
    assert plain.toolbar_toggle_actions() == ()


def test_a_surface_nested_inside_a_panel_is_not_the_screens(qapp) -> None:
    """Only a direct child is the screen's surface; one deeper belongs to
    whatever panel holds it."""
    view = QWidget()
    panel = QWidget(view)
    QVBoxLayout(panel).addWidget(WorkbenchSurface(surfaces_by_id()["dev_board"]))

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


def test_a_saved_layout_round_trips_through_the_inner_surface(
    with_surface: tuple[ModeHost, _ViewWithSurface],
) -> None:
    host, view = with_surface
    host.show()
    dock = view.surface.findChild(QDockWidget)
    assert dock is not None
    dock.close()
    saved = host.save_perspective()
    assert saved == view.surface.save_perspective()
    dock.show()

    assert host.restore_perspective(saved) is True

    assert dock.isHidden()
    assert host.layout_version == view.surface.layout_version


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
