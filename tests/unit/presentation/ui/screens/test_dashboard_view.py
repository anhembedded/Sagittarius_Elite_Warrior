import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QLabel, QScrollArea, QSplitter
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view import (
    DashboardView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view_model import (
    DashboardQmlViewModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dev_board_panel import (
    DevBoardPanel,
)


def test_dashboard_view_hybrid_layout_hosts_chart_scroll_area_and_dev_board_panel(
    qapp,
):
    """
    Regression test for the BOT-030 Phase 4 hybrid layout (QtWidgets since
    EPIC-006D): the chart column stays a QScrollArea of QtWidgets
    ChartCards (unchanged), and System Controls/Indicators/Monitor move
    into a single DevBoardPanel — both living inside a QSplitter so the
    user can resize either side. The panel builds lazily, at
    set_view_model() time (it needs a real ViewModel to construct against),
    not eagerly in __init__ the way the old QQuickWidget did.

    `EPIC-023A` put the Vị thế/Lệnh chờ khớp tables above the chart column
    inside a new `view._workspace` wrapper widget — since that wrapper is a
    plain `QWidget`, not a `QScrollArea` itself, `PageShell.set_workspace()`
    now auto-wraps it (`page_shell.py`'s `_scrollable()`), so `view.
    scroll_area` is no longer a direct splitter pane; it is nested one level
    deeper, still doing its own independent scrolling for the dynamic chart
    list.
    """
    view = DashboardView()

    assert isinstance(view.scroll_area, QScrollArea)
    assert view.scroll_area.widgetResizable() is True
    assert view._panel is None

    view.set_view_model(DashboardQmlViewModel())

    assert isinstance(view._panel, DevBoardPanel)
    splitters = view.findChildren(QSplitter)
    assert len(splitters) == 1
    splitter = splitters[0]
    panes = [splitter.widget(i) for i in range(splitter.count())]
    # `view._workspace` is a plain `QWidget` (tables_row + view.scroll_area),
    # so `PageShell` auto-wraps it in its own `PreferredHeightScrollArea`;
    # `view._panel` is a raw `DevBoardPanel` and gets the same treatment
    # (`page_shell.py`'s `set_workspace()` — every rail/main pane not
    # already a `QScrollArea` is wrapped so its natural content height is
    # never squeezed).
    wrapped_workspace_panes = [
        pane
        for pane in panes
        if isinstance(pane, QScrollArea) and pane.widget() is view._workspace
    ]
    assert len(wrapped_workspace_panes) == 1
    # `view.scroll_area` keeps doing its own scrolling for the chart list,
    # unaffected by the new outer wrapper — still findable as a descendant.
    assert view.scroll_area in view.findChildren(QScrollArea)
    wrapped_panel_panes = [
        pane
        for pane in panes
        if isinstance(pane, QScrollArea) and pane.widget() is view._panel
    ]
    assert len(wrapped_panel_panes) == 1


def test_dashboard_view_header_title(qapp):
    """The Dev Board header clearly labels itself as a developer testbed,
    distinct from the app's end-user dashboard (BOT-014) — rendered by
    `PageShell`'s header band (the page title moved out of `DevBoardPanel`
    and into `DashboardView`'s shell, the same place every other screen's
    title lives)."""
    view = DashboardView()
    view.resize(1200, 800)
    view.set_view_model(DashboardQmlViewModel())
    qapp.processEvents()

    header = view.findChild(QLabel, "pageShellTitle")
    assert header is not None
    assert header.text() == "Developer Board (Live Testbed)"


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
# `EPIC-023A` — Vị thế/Lệnh chờ khớp tables, account-wide, placed in the
# workspace (not `DevBoardPanel`'s rail — a rail column is too narrow for a
# many-column table, `BOT-128`'s own finding).
# ---------------------------------------------------------------------------


def test_dashboard_view_builds_positions_and_open_orders_panels(qapp):
    from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.open_orders_panel import (
        OpenOrdersPanel,
    )
    from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.positions_panel import (
        PositionsPanel,
    )

    view = DashboardView()

    assert isinstance(view._positions_panel, PositionsPanel)
    assert isinstance(view._open_orders_panel, OpenOrdersPanel)
    # Both live inside `view._workspace`, above the chart-card scroll area —
    # not inside `DevBoardPanel`'s rail.
    assert view._positions_panel in view._workspace.findChildren(PositionsPanel)
    assert view._open_orders_panel in view._workspace.findChildren(OpenOrdersPanel)


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
