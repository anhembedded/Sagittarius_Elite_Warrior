"""`EPIC-025` PR 1.4a — the surface host renders every place onto a real
`QMainWindow` part, and refuses the shapes that would look fine and be wrong.

`IPlaceHost` had no implementation for four pull requests: the places were
declared and the descriptors validated, and nothing could show a contributed
widget. These tests are what that implementation is checked against, and the
ones worth reading are the refusals — a second WORKSPACE, an untitled dock, a
place the surface does not accept. Each would otherwise produce a layout that
renders without complaint and is not what anybody contributed.
"""

from __future__ import annotations

import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.errors import ContributionError
from Sagittarius_Elite_Warrior.src.core.contracts.i_place_host import IPlaceHost
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)


@pytest.fixture
def trading(qapp) -> WorkbenchSurface:
    """The real `trading` surface declaration, not a hand-made one: what a
    surface accepts is `surfaces.py`'s contract, and a test that invented its
    own `accepts` set would stop catching a change to it."""
    return WorkbenchSurface(surfaces_by_id()["trading"])


@pytest.fixture
def dev_board(qapp) -> WorkbenchSurface:
    return WorkbenchSurface(surfaces_by_id()["dev_board"])


class TestIdentity:
    def test_it_reports_the_surface_it_hosts(self, trading: WorkbenchSurface) -> None:
        assert trading.surface_id == "trading"
        assert Place.RAIL in trading.accepts()

    def test_it_nests_instead_of_drawing_its_own_window_frame(self, qapp) -> None:
        """A parent is not enough, and this is the measured part: `QMainWindow`
        sets the `Window` flag on itself, so with a parent and no
        `setWindowFlags(Qt.Widget)` it still reports `isWindow()` and draws a
        title bar inside the page. Asserting the flag with a bitmask does not
        work either — `Qt.WindowType.Widget` is `0`, so `flags & Widget` is
        always falsy; what the call does is *clear* the set, and `isWindow()`
        is how you see it."""
        page = QWidget()

        nested = WorkbenchSurface(surfaces_by_id()["trading"], page)

        assert nested.isWindow() is False
        assert nested.parent() is page

    def test_it_satisfies_the_place_host_port(self, trading: WorkbenchSurface) -> None:
        """`IPlaceHost` is a `Protocol` and this class inherits nothing from
        it — `architecture-rule.md` §2.1 reason (a): `ABCMeta` conflicts with
        Shiboken's metaclass, so `class WorkbenchSurface(QMainWindow,
        IPlaceHost)` raises `TypeError` on import. A structural contract with
        nothing checking it is documentation, so this is the check."""
        assert isinstance(trading, IPlaceHost)


class TestTheParts:
    def test_a_workspace_becomes_the_central_widget(
        self, trading: WorkbenchSurface
    ) -> None:
        chart = QLabel("chart")

        trading.place_widget(Place.WORKSPACE, chart)

        assert trading.centralWidget() is chart

    def test_a_second_workspace_is_refused(self, trading: WorkbenchSurface) -> None:
        """A surface has one subject. Two modules each believing they own the
        centre must hear so, not have one of them silently replaced."""
        trading.place_widget(Place.WORKSPACE, QLabel("chart"))

        with pytest.raises(ContributionError, match="already has a workspace"):
            trading.place_widget(Place.WORKSPACE, QLabel("second chart"))

    def test_the_header_and_the_context_bar_are_two_toolbars_on_two_rows(
        self, trading: WorkbenchSurface
    ) -> None:
        trading.place_widget(Place.HEADER, QLabel("actions"))
        trading.place_widget(Place.CONTEXT_BAR, QLabel("BTCUSDT 1m"))

        header = trading.findChild(QWidget, f"{trading.objectName()}::header")
        context = trading.findChild(QWidget, f"{trading.objectName()}::context_bar")
        assert header is not None and context is not None
        assert header is not context
        # Two rows, not two toolbars side by side: the context bar says what
        # the surface is pointed at, and HLD §11.2 separates them so it reads
        # under the mode's own controls rather than beside them.
        assert trading.toolBarBreak(context) is True

    def test_a_rail_panel_becomes_a_titled_dock_on_the_right(
        self, trading: WorkbenchSurface
    ) -> None:
        trading.place_widget(Place.RAIL, QLabel("positions"), title="Positions")

        dock = trading.findChild(QWidget, f"{trading.objectName()}::rail::Positions")
        assert dock is not None
        assert dock.windowTitle() == "Positions"

    def test_a_console_panel_goes_to_the_bottom_not_the_right(
        self, trading: WorkbenchSurface
    ) -> None:
        trading.place_widget(Place.RAIL, QLabel("positions"), title="Positions")
        trading.place_widget(Place.CONSOLE, QLabel("log"), title="Log")

        rail = trading.findChild(QWidget, f"{trading.objectName()}::rail::Positions")
        console = trading.findChild(QWidget, f"{trading.objectName()}::console::Log")
        assert trading.dockWidgetArea(rail) == Qt.DockWidgetArea.RightDockWidgetArea
        assert trading.dockWidgetArea(console) == Qt.DockWidgetArea.BottomDockWidgetArea

    def test_two_rail_panels_are_tabbed_not_stacked(
        self, trading: WorkbenchSurface
    ) -> None:
        """Three panels stacked in one dock area leave none of them readable.
        Tabbed, the user can still pull one out — which is the User Control
        principle, and the reason `order` is only the *initial* arrangement."""
        trading.place_widget(Place.RAIL, QLabel("positions"), title="Positions")
        trading.place_widget(Place.RAIL, QLabel("orders"), title="Open orders")

        first = trading.findChild(QWidget, f"{trading.objectName()}::rail::Positions")
        assert trading.tabifiedDockWidgets(first)

    def test_an_untitled_dock_is_refused(self, trading: WorkbenchSurface) -> None:
        """A dock the user can move, tab and close needs a name to find it
        again — and `saveState()` keys it by that name, so an untitled one
        would also vanish from every restored perspective."""
        with pytest.raises(ContributionError, match="has no\n? *title"):
            trading.place_widget(Place.RAIL, QLabel("positions"))

    def test_two_docks_with_one_title_are_refused(
        self, trading: WorkbenchSurface
    ) -> None:
        trading.place_widget(Place.RAIL, QLabel("a"), title="Positions")

        with pytest.raises(ContributionError, match="already has a panel"):
            trading.place_widget(Place.RAIL, QLabel("b"), title="Positions")

    def test_a_status_tile_reaches_the_status_bar(
        self, trading: WorkbenchSurface
    ) -> None:
        pill = QLabel("WS: LIVE")

        trading.place_widget(Place.STATUS_TILE, pill)

        assert pill.parent() is not None
        assert trading.statusBar().isAncestorOf(pill)


class TestWhatTheSurfaceRefuses:
    def test_a_place_the_surface_does_not_accept(
        self, trading: WorkbenchSurface
    ) -> None:
        """`dev_probe` is Dev Board's, and `surfaces.py` says so. The host
        enforces the same contract the registry does, because a widget can
        also reach a host directly in a test or a preview."""
        with pytest.raises(ContributionError, match="cannot render dev_probe"):
            trading.place_widget(Place.DEV_PROBE, QLabel("probe"), title="Probe")

    def test_dev_board_does_accept_a_probe(self, dev_board: WorkbenchSurface) -> None:
        dev_board.place_widget(Place.DEV_PROBE, QLabel("probe"), title="Exchange API")

        assert (
            dev_board.findChild(
                QWidget, f"{dev_board.objectName()}::dev_probe::Exchange API"
            )
            is not None
        )


class TestModals:
    def test_a_modal_is_kept_not_placed(self, trading: WorkbenchSurface) -> None:
        """A dialog is not part of a layout: it is how the user does something
        that needs confirmation. Placing it would put a form permanently in the
        way of something they do occasionally — the card shape this epic
        retired."""
        body = QLabel("order form")

        trading.place_widget(Place.MODAL, body, title="Place order")

        assert trading.centralWidget() is None
        assert trading.modal_titles() == ("Place order",)

    def test_the_kept_dialog_carries_the_title_and_the_body(
        self, trading: WorkbenchSurface
    ) -> None:
        body = QLabel("order form")
        trading.place_widget(Place.MODAL, body, title="Place order")

        dialog = trading.show_modal("Place order")

        assert dialog.windowTitle() == "Place order"
        assert dialog.isAncestorOf(body)

    def test_asking_for_a_dialog_nobody_contributed_says_what_there_is(
        self, trading: WorkbenchSurface
    ) -> None:
        trading.place_widget(Place.MODAL, QLabel("form"), title="Place order")

        with pytest.raises(ContributionError, match="Place order"):
            trading.show_modal("Arm strategy")

    def test_an_untitled_modal_is_refused(self, trading: WorkbenchSurface) -> None:
        with pytest.raises(ContributionError, match="has no\n? *title"):
            trading.place_widget(Place.MODAL, QLabel("form"))


class TestThePerspective:
    def test_a_saved_layout_comes_back(self, trading: WorkbenchSurface) -> None:
        trading.place_widget(Place.RAIL, QLabel("positions"), title="Positions")
        trading.place_widget(Place.CONSOLE, QLabel("log"), title="Log")
        dock = trading.findChild(QWidget, f"{trading.objectName()}::console::Log")
        dock.hide()
        blob = trading.save_perspective()
        dock.show()

        assert trading.restore_perspective(blob) is True
        assert dock.isHidden()

    def test_an_empty_perspective_is_reported_not_raised(
        self, trading: WorkbenchSurface
    ) -> None:
        assert trading.restore_perspective(b"") is False

    def test_a_corrupt_perspective_leaves_the_default_layout_standing(
        self, trading: WorkbenchSurface, caplog
    ) -> None:
        """The Robustness principle's own words: saved perspectives "migrate or
        reset, never crash". A blob from another version, or a truncated one,
        is the ordinary case after an update."""
        trading.place_widget(Place.RAIL, QLabel("positions"), title="Positions")
        dock = trading.findChild(QWidget, f"{trading.objectName()}::rail::Positions")

        with caplog.at_level(logging.INFO):
            assert trading.restore_perspective(b"not a QMainWindow state") is False

        assert not dock.isHidden()
        assert any("default layout" in record.message for record in caplog.records)
