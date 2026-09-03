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
    # `view.scroll_area` is already its own `QScrollArea` (built by this
    # view itself, well before `PageShell.set_workspace()` existed) so it
    # lands in the splitter unwrapped; `view._panel` is a raw `DevBoardPanel`
    # and gets `PageShell`'s own scroll-wrap treatment (`page_shell.py`'s
    # `set_workspace()` — every rail/main pane not already a `QScrollArea`
    # is wrapped so its natural content height is never squeezed).
    assert view.scroll_area in panes
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
