"""`EPIC-025` PR 1.4a — contributions become a rendered surface.

The host next door is tested by placing widgets into it directly. This is the
other half: that what a module *contributed* actually reaches the place it
asked for, in the order the registry decided, with the factory called once and
no earlier than it has to be.

`onb` §12.5's "the skeleton walks": a host nothing renders into has proved
nothing, which is the same argument PR 0.5 made for `IMarketDataSync` with
N = 2 rather than a port with no caller.
"""

from __future__ import annotations

import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.contribution_descriptor import (
    ContributionDescriptor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.size_hint import SizeHint
from Sagittarius_Elite_Warrior.src.shell.contribution_registry import (
    ContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.shell.surface_building import build_surface
from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id


def _descriptor(
    place: Place,
    factory,
    *,
    contributor_id: str = "trading",
    surface_id: str = "trading",
    order: int = 10,
    title: str | None = None,
) -> ContributionDescriptor:
    return ContributionDescriptor(
        contributor_id=contributor_id,
        surface_id=surface_id,
        place=place,
        order=order,
        size_hint=SizeHint.REGULAR,
        factory=factory,
        title=title,
    )


@pytest.fixture
def registry() -> ContributionRegistry:
    return ContributionRegistry(dev_mode=True)


@pytest.fixture
def container() -> Mock:
    return Mock()


def test_an_empty_registry_builds_an_empty_surface(
    qapp, registry: ContributionRegistry, container: Mock
) -> None:
    host = build_surface(surfaces_by_id()["trading"], registry, container)

    assert host.surface_id == "trading"
    assert host.centralWidget() is None


def test_a_contributed_workspace_reaches_the_centre(
    qapp, registry: ContributionRegistry, container: Mock
) -> None:
    chart = QLabel("chart")
    registry.contribute(_descriptor(Place.WORKSPACE, lambda _c: chart))

    host = build_surface(surfaces_by_id()["trading"], registry, container)

    assert host.centralWidget() is chart


def test_a_contributed_panel_becomes_a_titled_dock(
    qapp, registry: ContributionRegistry, container: Mock
) -> None:
    registry.contribute(
        _descriptor(Place.RAIL, lambda _c: QLabel("positions"), title="Positions")
    )

    host = build_surface(surfaces_by_id()["trading"], registry, container)

    dock = host.findChild(QWidget, f"{host.objectName()}::rail::Positions")
    assert dock is not None
    assert dock.windowTitle() == "Positions"


def test_the_factory_gets_the_container_and_is_called_once(
    qapp, registry: ContributionRegistry, container: Mock
) -> None:
    """The descriptor's whole point: a module hands over a function, and the
    shell decides when to call it. Twice would build two widgets and show
    one."""
    calls: list[object] = []

    def factory(c):
        calls.append(c)
        return QLabel("panel")

    registry.contribute(_descriptor(Place.RAIL, factory, title="Positions"))

    build_surface(surfaces_by_id()["trading"], registry, container)

    assert calls == [container]


def test_nothing_is_built_for_a_place_the_surface_does_not_accept(
    qapp, registry: ContributionRegistry, container: Mock
) -> None:
    """`dev_probe` on `trading` cannot be contributed at all — the registry
    refuses it — so this checks the builder's own skip: `trading` accepts no
    `SETTINGS_SECTION`, and a contribution aimed at one must not be called for
    on this surface."""
    built = False

    def factory(_c):
        nonlocal built
        built = True
        return QLabel("section")

    registry.contribute(
        _descriptor(
            Place.SETTINGS_SECTION,
            factory,
            surface_id="settings",
            title="Exchange",
        )
    )

    build_surface(surfaces_by_id()["trading"], registry, container)

    assert built is False


def test_order_decides_which_dock_comes_first(
    qapp, registry: ContributionRegistry, container: Mock
) -> None:
    """`order` is the *initial* arrangement — after this the user's saved
    perspective wins (HLD §11.2), which is why nothing else in the surface
    reads it."""

    # Two *named* factories, because the registry keys a contribution's
    # identity partly by the factory's qualname — two lambdas from one module
    # in one place are indistinguishable and it refuses them, which is itself
    # correct and is why a real module contributes named functions.
    def open_orders_panel(_c):
        return QLabel("second")

    def positions_panel(_c):
        return QLabel("first")

    registry.contribute(
        _descriptor(Place.RAIL, open_orders_panel, order=20, title="Open orders")
    )
    registry.contribute(
        _descriptor(Place.RAIL, positions_panel, order=10, title="Positions")
    )

    host = build_surface(surfaces_by_id()["trading"], registry, container)

    docks = [
        dock.windowTitle()
        for dock in host.findChildren(QWidget)
        if dock.objectName().startswith(f"{host.objectName()}::rail::")
    ]
    assert docks == ["Positions", "Open orders"]


def test_the_workspace_exists_before_the_docks(
    qapp, registry: ContributionRegistry, container: Mock
) -> None:
    """Not cosmetic: Qt sizes the dock areas around the central widget, so a
    dock added first is laid out against an empty centre. The fill order is
    what guarantees it, and this is what would catch someone reordering it."""
    seen: list[str] = []
    registry.contribute(
        _descriptor(
            Place.RAIL,
            lambda _c: (seen.append("rail"), QLabel("rail"))[1],
            title="Positions",
        )
    )
    registry.contribute(
        _descriptor(
            Place.WORKSPACE, lambda _c: (seen.append("workspace"), QLabel("chart"))[1]
        )
    )

    build_surface(surfaces_by_id()["trading"], registry, container)

    assert seen == ["workspace", "rail"]


def test_a_console_contribution_reaches_the_bottom_dock(
    qapp, registry: ContributionRegistry, container: Mock
) -> None:
    registry.contribute(
        _descriptor(Place.CONSOLE, lambda _c: QLabel("log"), title="Log")
    )

    host = build_surface(surfaces_by_id()["trading"], registry, container)

    dock = host.findChild(QWidget, f"{host.objectName()}::console::Log")
    assert host.dockWidgetArea(dock) == Qt.DockWidgetArea.BottomDockWidgetArea


def test_a_modal_contribution_is_available_not_placed(
    qapp, registry: ContributionRegistry, container: Mock
) -> None:
    registry.contribute(
        _descriptor(Place.MODAL, lambda _c: QLabel("form"), title="Place order")
    )

    host = build_surface(surfaces_by_id()["trading"], registry, container)

    assert host.centralWidget() is None
    assert host.modal_titles() == ("Place order",)


def test_a_dev_probe_reaches_dev_board(
    qapp, registry: ContributionRegistry, container: Mock
) -> None:
    registry.contribute(
        _descriptor(
            Place.DEV_PROBE,
            lambda _c: QLabel("probe"),
            surface_id="dev_board",
            contributor_id="trading",
            title="Exchange API",
        )
    )

    host = build_surface(surfaces_by_id()["dev_board"], registry, container)

    assert (
        host.findChild(QWidget, f"{host.objectName()}::dev_probe::Exchange API")
        is not None
    )


def test_it_says_how_many_widgets_it_placed(
    qapp, registry: ContributionRegistry, container: Mock, caplog
) -> None:
    """`logging-rule.md` §2–§3: a boot step logs the decision, not just that it
    happened. "Built with 0 widgets" is the line that explains an empty
    workbench, and it is the normal case while the screens are still legacy."""
    registry.contribute(
        _descriptor(Place.RAIL, lambda _c: QLabel("a"), title="Positions")
    )

    with caplog.at_level(logging.INFO):
        build_surface(surfaces_by_id()["trading"], registry, container)

    assert any(
        "built with 1 contributed widget" in record.getMessage()
        for record in caplog.records
    )
