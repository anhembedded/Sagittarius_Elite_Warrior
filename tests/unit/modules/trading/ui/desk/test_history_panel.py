"""`HistoryPanel`: a page of fills, as the user reads it (`EPIC-033N`)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

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
    assert _text(panel, 0, "pnl") == ""


def test_a_futures_fill_shows_its_signed_realized_pnl(qapp):
    model = TradeHistoryTableModel()
    panel = _panel_with(model, _fill("USDT", Decimal("-12.5")))

    assert _text(panel, 0, "pnl") == "-12.50"
