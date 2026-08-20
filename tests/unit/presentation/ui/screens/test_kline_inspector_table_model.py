from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.kline_inspector_table_model import (
    KLineInspectorTableModel,
)


def _make_candle(
    idx: int,
    open_price: float = 100.0,
    close_price: float = 105.0,
) -> MarketData:
    t = datetime(2024, 1, 1, 0, idx, tzinfo=UTC)
    return MarketData(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE,
        open_time=t,
        close_time=t,
        open_price=open_price,
        high_price=max(open_price, close_price) + 2.0,
        low_price=min(open_price, close_price) - 2.0,
        close_price=close_price,
        volume=10.0,
        quote_asset_volume=10.0 * close_price,
        number_of_trades=50,
        taker_buy_base_asset_volume=5.0,
        taker_buy_quote_asset_volume=5.0 * close_price,
    )


def test_kline_inspector_empty_model(qapp):
    model = KLineInspectorTableModel(page_size=50)
    assert model.rowCount() == 0
    assert model.total_records == 0
    assert model.total_pages == 1
    assert model.current_page == 1


def test_kline_inspector_pagination_and_roles(qapp):
    model = KLineInspectorTableModel(page_size=20)
    candles = [_make_candle(i, 100.0 + i, 105.0 + i) for i in range(55)]
    model.set_klines(candles)

    assert model.total_records == 55
    assert model.total_pages == 3
    assert model.current_page == 1
    assert model.rowCount() == 20

    # Test row 0 data
    idx0 = model.index(0, 0)
    assert (
        model.data(idx0, KLineInspectorTableModel.FormattedTimeRole)
        == "2024-01-01 00:00:00"
    )
    assert model.data(idx0, KLineInspectorTableModel.OpenRole) == "100.00"
    assert model.data(idx0, KLineInspectorTableModel.IsBullishRole) is True
    assert model.data(idx0, KLineInspectorTableModel.TradesRole) == 50

    # Go to page 2
    model.set_page(2)
    assert model.current_page == 2
    assert model.rowCount() == 20
    idx_p2_0 = model.index(0, 0)
    assert (
        model.data(idx_p2_0, KLineInspectorTableModel.FormattedTimeRole)
        == "2024-01-01 00:20:00"
    )

    # Go to page 3 (last page with 15 items)
    model.set_page(3)
    assert model.current_page == 3
    assert model.rowCount() == 15


def test_kline_inspector_jump_to_date(qapp):
    model = KLineInspectorTableModel(page_size=10)
    candles = [_make_candle(i, 100.0, 105.0) for i in range(35)]
    model.set_klines(candles)

    # Jump to minute 25 (should be on page 3)
    found = model.jump_to_date("00:25")
    assert found is True
    assert model.current_page == 3

    # Jump to non-existent date
    not_found = model.jump_to_date("2099-12-31")
    assert not_found is False
