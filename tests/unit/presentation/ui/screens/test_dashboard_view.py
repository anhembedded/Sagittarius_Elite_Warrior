import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QScrollArea,
    QSplitter,
    QToolBar,
)
from Sagittarius_Elite_Warrior.src.core.contracts.contribution_descriptor import (
    ContributionDescriptor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_table import (
    IContributionTable,
)
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.size_hint import SizeHint
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view import (
    DEV_BOARD_SURFACE,
    EQUITY_DOCK,
    MONITOR_DOCK,
    OPEN_ORDERS_DOCK,
    POSITIONS_DOCK,
    DashboardView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view_model import (
    DashboardQmlViewModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dev_board_panel import (
    DATA_AND_STREAM_DOCK,
    INDICATORS_DOCK,
    LAST_SIGNAL_DOCK,
    MANUAL_ORDER_DIALOG,
    SESSION_DOCK,
    STRATEGY_DOCK,
    DevBoardPanel,
)


def _dock(view: DashboardView, title: str) -> QDockWidget | None:
    """The dock a panel was placed in, by the title the user sees — which is
    also the key `QMainWindow.saveState()` stores it under."""
    name = f"{view._surface.objectName()}::{_place_of(title)}::{title}"
    return view._surface.findChild(QDockWidget, name)


def _place_of(title: str) -> str:
    return "console" if title == MONITOR_DOCK else "rail"


def test_the_workbench_hosts_the_chart_column_and_every_panel_as_a_dock(qapp):
    """`EPIC-025` PR 1.4c-2 replaced the `PageShell` + one `QSplitter` this
    test used to describe. What it asserted then and asserts now: the chart
    column is a `QScrollArea` of QtWidgets `ChartCard`s (unchanged), and
    `DevBoardPanel` is built lazily at `set_view_model()` time, not eagerly in
    `__init__` the way the old `QQuickWidget` was.

    What is new is what replaced the splitter: the chart column is the
    workbench's central widget and every other piece is a `QDockWidget` the
    user can move, tab, float and hide — so the assertion is about docks by
    title, which is also what a saved perspective keys them by.
    """
    view = DashboardView()

    assert isinstance(view.scroll_area, QScrollArea)
    assert view.scroll_area.widgetResizable() is True
    assert view._surface.centralWidget() is view.scroll_area
    assert view._panel is None
    # Two fixed panes became docks: nothing is a `QSplitter` any more.
    assert view.findChildren(QSplitter) == []

    view.set_view_model(DashboardQmlViewModel())

    assert isinstance(view._panel, DevBoardPanel)
    assert _dock(view, MONITOR_DOCK) is not None
    # The log spans the window at the bottom, where the user can hide it.
    assert view._surface.dockWidgetArea(_dock(view, MONITOR_DOCK)) == (
        Qt.DockWidgetArea.BottomDockWidgetArea
    )


def test_the_view_renders_the_surface_the_shell_declares(qapp):
    """`DashboardView` declares its own `Surface` because a file under
    `presentation/` may not import `shell/`. That makes this test the thing
    standing between one declaration and two: if the shell's `dev_board` entry
    gains a place, or its gate changes, this fails instead of the screen
    quietly refusing a panel contributed to it."""
    from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id

    assert surfaces_by_id()["dev_board"] == DEV_BOARD_SURFACE


def test_the_screen_still_says_it_is_a_developer_testbed(qapp):
    """`BOT-014` — the Dev Board labels itself, distinct from an end-user
    dashboard. It used to be `PageShell`'s title band; a `QMainWindow` has no
    such band, so the text moved to the context bar, which is the part that
    says what the surface is pointed at."""
    view = DashboardView()
    view.resize(1200, 800)
    view.set_view_model(DashboardQmlViewModel())
    qapp.processEvents()

    identity = view.findChild(QLabel, "lblDevBoardIdentity")
    assert identity is not None
    assert "Developer Board (Live Testbed)" in identity.text()


def test_the_buttons_go_to_the_toolbar_and_the_readouts_to_the_status_bar(qapp):
    """HLD §11.2 splits them: a `QToolBar` carries what the user *does*, the
    `QStatusBar` what the app *reports*. Before the workbench both sat in one
    header row, so this is the wiring that could silently regress to it."""
    view = DashboardView()
    view.set_view_model(DashboardQmlViewModel())
    panel = view._panel

    toolbar = view._surface.findChild(QToolBar, f"{view._surface.objectName()}::header")
    assert toolbar is not None
    for button in panel.header_actions:
        assert toolbar.isAncestorOf(button)
    for tile in panel.status_tiles:
        assert view._surface.statusBar().isAncestorOf(tile)


def test_dashboard_view_apply_ui_mode_forwards_to_view_model(qapp):
    """apply_ui_mode is BasePresenter's FSM->UI duck-typed hook (this view
    has no `control_card`, so the fallback branch calls it directly) — it
    must reach the ViewModel's uiMode property, which DevBoardPanel.qml
    binds its enabled states to."""
    view = DashboardView()
    view_model = DashboardQmlViewModel()
    view.set_view_model(view_model)

    view.apply_ui_mode("LOCKED")

    assert view_model.uiMode == "LOCKED"


def test_dashboard_view_model_symbol_and_date_defaults(qapp):
    """BOT-033 Phase 2 — the ViewModel, not QML, owns the default Symbol/
    Start date/End date so DashboardPresenter can read the same default a
    freshly-opened Dev Board shows without depending on QML having rendered
    first."""
    from datetime import UTC, datetime

    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view_model import (
        DATETIME_FORMAT,
    )

    view_model = DashboardQmlViewModel()

    assert view_model.symbol == "ETHUSDT"
    start = datetime.strptime(view_model.startDate, DATETIME_FORMAT).replace(tzinfo=UTC)
    end = datetime.strptime(view_model.endDate, DATETIME_FORMAT).replace(tzinfo=UTC)
    assert start < end


def test_dashboard_view_model_symbol_and_dates_are_settable(qapp):
    """DevBoardPanel's Symbol button and the two date fields write through
    these properties, and `_sync_symbol`/`_sync_start_date` read them back."""
    view_model = DashboardQmlViewModel()

    view_model.symbol = "BTCUSDT"
    view_model.startDate = "2024-01-01 00:00"
    view_model.endDate = "2024-01-02 00:00"

    assert view_model.symbol == "BTCUSDT"
    assert view_model.startDate == "2024-01-01 00:00"
    assert view_model.endDate == "2024-01-02 00:00"


# ---------------------------------------------------------------------------
# `EPIC-023A` — the account-wide positions and open-orders tables. Docks of
# their own since PR 1.4c-2; see the test below for what that fixed.
# ---------------------------------------------------------------------------


def test_the_account_tables_are_docks_of_their_own(qapp):
    """They used to sit squeezed above the chart column, because the old rail
    was a fixed narrow strip and a many-column table did not fit it
    (`BOT-128`). As docks they are as wide as the user drags them, which is
    the placement HLD §11.2 assigns and the reason the workbench is worth
    having."""
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_orders_panel import (
        OpenOrdersPanel,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.positions_panel import (
        PositionsPanel,
    )

    view = DashboardView()

    assert isinstance(view._positions_panel, PositionsPanel)
    assert isinstance(view._open_orders_panel, OpenOrdersPanel)
    for title, panel in (
        (POSITIONS_DOCK, view._positions_panel),
        (OPEN_ORDERS_DOCK, view._open_orders_panel),
        (EQUITY_DOCK, view.equity_chart),
    ):
        dock = _dock(view, title)
        assert dock is not None, title
        assert dock.widget() is panel


def test_dashboard_view_set_positions_forwards_to_the_panel(qapp, monkeypatch):
    from unittest.mock import MagicMock

    view = DashboardView()
    spy = MagicMock()
    monkeypatch.setattr(view._positions_panel, "set_rows", spy)

    view.set_positions(["row"])

    spy.assert_called_once_with(["row"])


def test_dashboard_view_set_open_orders_forwards_to_the_panel(qapp, monkeypatch):
    from unittest.mock import MagicMock

    view = DashboardView()
    spy = MagicMock()
    monkeypatch.setattr(view._open_orders_panel, "set_rows", spy)

    view.set_open_orders(["row"])

    spy.assert_called_once_with(["row"])


# ---------------------------------------------------------------------------
# PR 1.4c-3 — the controls stopped being one scrolling column.
# ---------------------------------------------------------------------------


def test_every_control_card_is_a_dock_of_its_own(qapp):
    """One card per dock, so the user can hide the four they are not using
    and keep the one they are. As a single scrolling column, reaching the
    Session counters meant scrolling past Strategy and losing sight of it."""
    view = DashboardView()
    view.set_view_model(DashboardQmlViewModel())

    for title in (
        DATA_AND_STREAM_DOCK,
        STRATEGY_DOCK,
        LAST_SIGNAL_DOCK,
        SESSION_DOCK,
        INDICATORS_DOCK,
    ):
        dock = _dock(view, title)
        assert dock is not None, title
        assert dock.widget() is not None, title


def test_the_cards_are_tabbed_rather_than_stacked(qapp):
    """Eight panels stacked in one dock area leave none of them readable.
    The host tabifies them, and this is what would catch that changing."""
    view = DashboardView()
    view.set_view_model(DashboardQmlViewModel())

    first = _dock(view, POSITIONS_DOCK)
    assert view._surface.tabifiedDockWidgets(first)


def test_the_order_form_is_a_dialog_the_user_opens_not_a_panel_in_the_way(qapp):
    """`EPIC-024B`'s manual-order card used to sit in the scrolling column,
    permanently occupying the space of something done occasionally (HLD
    §11.3). It is a dialog now, and the same `QAction` that raises it carries
    `F9` — the key MetaTrader has used for "new order" for twenty years."""
    view = DashboardView()
    view.set_view_model(DashboardQmlViewModel())

    assert view._surface.modal_titles() == (MANUAL_ORDER_DIALOG,)
    assert _dock(view, MANUAL_ORDER_DIALOG) is None
    assert view._manual_order_action.shortcut() == QKeySequence("F9")

    dialog = view._surface.show_modal(MANUAL_ORDER_DIALOG)

    assert dialog.isAncestorOf(view._panel.manual_order_card)
    assert dialog.windowTitle() == MANUAL_ORDER_DIALOG


def test_the_action_opens_the_dialog_without_freezing_the_chart(qapp):
    """`show()`, not `exec()`: a user placing an order by hand is watching
    the ticks behind the dialog, and a modal event loop stops them."""
    view = DashboardView()
    view.set_view_model(DashboardQmlViewModel())

    view._manual_order_action.trigger()

    dialog = view._surface.show_modal(MANUAL_ORDER_DIALOG)
    assert dialog.isVisible() is True
    assert dialog.isModal() is False


# ---------------------------------------------------------------------------
# PR 1.4c-4 — a panel a *module* contributed, on a screen the shell carries.
# ---------------------------------------------------------------------------


class _OneProbeTable(IContributionTable):
    """A contribution table with one `DEV_PROBE`, and not the shell's registry.

    A hand-written table rather than a `Mock`: a `Mock` would answer every
    place with a `Mock` list and the builder would place nothing while this
    test still passed.
    """

    def __init__(self, factory) -> None:
        self._descriptor = ContributionDescriptor(
            contributor_id="trading",
            surface_id="dev_board",
            place=Place.DEV_PROBE,
            order=10,
            size_hint=SizeHint.REGULAR,
            factory=factory,
            title="Trading session",
        )

    def surface(self, surface_id: str) -> Surface:
        return DEV_BOARD_SURFACE

    def panels(self, surface_id: str, place: Place) -> tuple:
        if surface_id == "dev_board" and place is Place.DEV_PROBE:
            return (self._descriptor,)
        return ()


def test_a_contributed_probe_reaches_the_dev_board(qapp) -> None:
    """The whole mechanism, in one assertion: a module hands over a
    descriptor, the shell collects it, and the screen the shell still carries
    renders it as a dock the user can move."""
    built: list[object] = []

    def factory(container):
        built.append(container)
        return QLabel("probe")

    container = object()
    view = DashboardView(contributions=_OneProbeTable(factory), container=container)
    view.set_view_model(DashboardQmlViewModel())

    dock = view._surface.findChild(
        QDockWidget, f"{view._surface.objectName()}::dev_probe::Trading session"
    )
    assert dock is not None
    assert built == [container], "the factory is called once, with the container"


def test_the_contributed_panel_arrives_after_the_screens_own_workspace(qapp) -> None:
    """Order matters and is not cosmetic: Qt sizes the dock areas around the
    central widget, and a contributed panel must not be able to take the
    centre from the screen that owns it."""
    view = DashboardView(
        contributions=_OneProbeTable(lambda _c: QLabel("probe")), container=object()
    )
    view.set_view_model(DashboardQmlViewModel())

    assert view._surface.centralWidget() is view.scroll_area


def test_a_screen_with_nothing_contributed_renders_its_own_widgets(qapp) -> None:
    """The normal user run: `dev.mode` off means the registry dropped every
    Dev Board contribution at boot, so the screen gets `None` and must still
    be a working workbench."""
    view = DashboardView()
    view.set_view_model(DashboardQmlViewModel())

    assert view._surface.centralWidget() is view.scroll_area
    assert _dock(view, POSITIONS_DOCK) is not None
