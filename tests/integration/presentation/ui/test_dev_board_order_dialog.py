"""`EPIC-028M` — the Dev Board's F9 dialog in the real app: the desks' order
panel for the venue the board trades, or a notice when none is enabled.

@details The app boots for real (`navigate`); this suite's configuration
leaves trading off (`TradingVenue.DISABLED`, `src/config/app_config.json`),
so the dialog must say so and hold nothing that sends an order — the same
rule a disabled desk follows. It replaces the manual-order card's click test:
the card is gone, and with no venue on there is no panel to click. The panel
itself, placed against a venue, is proven in
`tests/unit/modules/trading/ui/dashboard/test_dev_board_order_entry.py`.
"""

from PySide6.QtWidgets import QLabel, QPushButton
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dev_board_panel import (
    MANUAL_ORDER_DIALOG,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_panel import (
    OrderEntryPanel,
)


def test_f9_with_no_venue_enabled_says_so_and_holds_no_order_panel(
    qtbot, main_window, navigate
):
    view = navigate("dashboard")["view_instance"]

    view._manual_order_action.trigger()

    dialog = view._surface.show_modal(MANUAL_ORDER_DIALOG)
    assert dialog.isVisible()
    notice = dialog.findChild(QLabel, "lblOrderEntryUnavailable")
    assert notice is not None
    assert "No trading venue is enabled" in notice.text()
    assert dialog.findChildren(OrderEntryPanel) == []
    assert [
        b for b in dialog.findChildren(QPushButton) if b.text() in ("Buy", "Sell")
    ] == []
