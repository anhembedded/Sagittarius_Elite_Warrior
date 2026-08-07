from PySide6.QtWidgets import QScrollArea

from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_view import (
    DashboardView,
)


def test_dashboard_view_header_title(qapp):
    """
    Test that the Dev Board header clearly labels itself as a developer testbed,
    distinct from the app's end-user dashboard (BOT-014).
    """
    view = DashboardView()
    assert view.lbl_header.text() == "Developer Board (Live Testbed)"


def test_dashboard_view_right_column_is_scrollable(qapp):
    """
    Regression test: the right column (ControlCard, IndicatorControlCard,
    MonitorCard, ...) must live inside a QScrollArea. A plain fixed
    QVBoxLayout would silently clip cards off-screen once their combined
    height exceeds the window — as happened when IndicatorControlCard was
    added without one.
    """
    view = DashboardView()

    enclosing_scroll_areas = [
        scroll_area
        for scroll_area in view.findChildren(QScrollArea)
        if view.control_card in scroll_area.findChildren(type(view.control_card))
    ]

    assert len(enclosing_scroll_areas) == 1
    assert enclosing_scroll_areas[0].widgetResizable() is True
    # MonitorCard must be reachable via the same scroll area too.
    assert view.monitor_card in enclosing_scroll_areas[0].findChildren(
        type(view.monitor_card)
    )
