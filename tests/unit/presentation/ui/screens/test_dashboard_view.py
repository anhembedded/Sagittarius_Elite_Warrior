import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view import (
    DashboardView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view_model import (
    DashboardQmlViewModel,
)
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QScrollArea, QSplitter


def test_dashboard_view_hybrid_layout_hosts_chart_scroll_area_and_qml_panel(qapp):
    """
    Regression test for the BOT-030 Phase 4 hybrid layout: the chart column
    stays a QScrollArea of QtWidgets ChartCards (unchanged), and System
    Controls/Indicators/Monitor move into a single QQuickWidget — both
    living inside a QSplitter so the user can resize either side.
    """
    view = DashboardView()

    assert isinstance(view.scroll_area, QScrollArea)
    assert view.scroll_area.widgetResizable() is True
    assert isinstance(view.quick_widget, QQuickWidget)

    splitters = view.findChildren(QSplitter)
    assert len(splitters) == 1
    splitter = splitters[0]
    assert view.scroll_area in [splitter.widget(i) for i in range(splitter.count())]
    assert view.quick_widget in [splitter.widget(i) for i in range(splitter.count())]


def test_dashboard_view_header_title(qapp, qml_item):
    """The Dev Board header clearly labels itself as a developer testbed,
    distinct from the app's end-user dashboard (BOT-014) — now rendered by
    DevBoardPanel.qml instead of a QLabel."""
    view = DashboardView()
    view.resize(1200, 800)
    view.set_view_model(DashboardQmlViewModel())
    view.load_qml()
    qapp.processEvents()

    assert view.quick_widget.errors() == []
    root = view.quick_widget.rootObject()
    header = qml_item(root, "lblHeaderTitle")
    assert header.property("text") == "Developer Board (Live Testbed)"


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
