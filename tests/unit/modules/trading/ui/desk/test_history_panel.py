"""`HistoryPanel`: a page of fills, as the user reads it (`EPIC-033N`)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDockWidget, QMainWindow, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_panel import (
    HistoryPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_rows import (
    TradeHistoryRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_table_models import (
    TradeHistoryTableModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_view import (
    HistoryView,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import displayed_text


def _fill(fee_asset: str, realized_pnl: Decimal | None) -> TradeHistoryRow:
    return TradeHistoryRow(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        price=Decimal(60000),
        quantity=Decimal("0.01"),
        quote_quantity=Decimal(600),
        fee=Decimal("0.00001"),
        fee_asset=fee_asset,
        realized_pnl=realized_pnl,
        time=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
    )


def _panel_with(model: TradeHistoryTableModel, *rows: TradeHistoryRow) -> HistoryPanel:
    panel = HistoryPanel(model, "TradeHistory")
    model.set_rows(rows)
    return panel


def _text(panel: HistoryPanel, row: int, key: str) -> str:
    return displayed_text(panel.table, row, TradeHistoryTableModel.column(key))


def test_a_fill_reads_by_kind_with_its_fee_asset_beside_the_fee(qapp):
    model = TradeHistoryTableModel()
    panel = _panel_with(model, _fill("BTC", None))

    assert _text(panel, 0, "time") == "2026-09-15 12:00:00"
    assert _text(panel, 0, "price") == "60,000.00"
    assert _text(panel, 0, "quantity") == "0.01"
    assert _text(panel, 0, "total") == "600.00"
    assert _text(panel, 0, "fee") == "0.00001"
    assert _text(panel, 0, "fee_asset") == "BTC"
    # A Spot fill has no realized PnL: an empty cell, never 0.
    assert _text(panel, 0, "pnl.signed") == ""


def test_a_futures_fill_shows_its_signed_realized_pnl(qapp):
    model = TradeHistoryTableModel()
    panel = _panel_with(model, _fill("USDT", Decimal("-12.5")))

    assert _text(panel, 0, "pnl.signed") == "▼ -12.50"


def test_a_realized_pnl_is_toned_by_its_sign_beside_its_arrow(qapp):
    """`EPIC-043C`: the colour is the meaning table's, and the arrow says the same in words."""
    model = TradeHistoryTableModel()
    panel = _panel_with(
        model,
        _fill("USDT", Decimal("12.5")),
        _fill("USDT", Decimal("-12.5")),
        _fill("BTC", None),
    )
    column = TradeHistoryTableModel.column("pnl.signed")

    def colour(row: int) -> object:
        return panel.table.model().data(
            panel.table.model().index(row, column), Qt.ItemDataRole.ForegroundRole
        )

    palette = QGuiApplication.palette()
    assert _text(panel, 0, "pnl.signed") == "▲ +12.50"
    assert colour(0) == tone_colour(Tone.POSITIVE, palette)
    assert _text(panel, 1, "pnl.signed") == "▼ -12.50"
    assert colour(1) == tone_colour(Tone.NEGATIVE, palette)
    assert colour(2) is None


def test_a_long_notice_is_shown_whole_in_a_dock_as_narrow_as_it_goes(qapp):
    """`BUG-251` review: a size policy that caps the label at its hint cuts the notice again once
    the dock is narrowed towards its minimum width, at any window size."""
    model = TradeHistoryTableModel()
    panel = HistoryPanel(model, "TradeHistory")
    notice = (
        "Binance keeps a Futures order that was cancelled or expired without a fill for 3 "
        "days only; older ones are not listed. A pair whose orders were all cancelled "
        "without a fill, with nothing open, is not found when reading every pair; choose "
        "the pair to see it."
    )
    panel.show_view(HistoryView((), 0, 1, "Orders of ETHUSDT", (notice,)))
    window = QMainWindow()
    dock = QDockWidget("History")
    dock.setWidget(panel)
    window.setCentralWidget(QWidget())
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
    window.resize(1920, 1080)
    window.show()
    window.resizeDocks(
        [dock], [panel.minimumSizeHint().width()], Qt.Orientation.Horizontal
    )
    for _ in range(4):
        qapp.processEvents()
    label = panel._notices

    assert label.width() < 300, "the dock was narrowed"
    assert label.height() >= label.heightForWidth(label.width())
    window.close()
