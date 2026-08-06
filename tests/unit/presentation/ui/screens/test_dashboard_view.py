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
