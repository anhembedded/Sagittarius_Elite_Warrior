from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.repair_data_gap import (
    RepairDataGapCommand,
    RepairDataGapCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    ExchangeRequestCancelledError,
)


def test_repair_data_gap_success():
    client = Mock()
    repo = Mock()
    start = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
    end = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

    dummy_kline = MarketData(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE,
        open_time=start,
        open_price=50000.0,
        high_price=50100.0,
        low_price=49900.0,
        close_price=50050.0,
        volume=100.0,
        close_time=end,
        quote_asset_volume=5000000.0,
        number_of_trades=1000,
        taker_buy_base_asset_volume=50.0,
        taker_buy_quote_asset_volume=2500000.0,
    )
    client.get_historical_klines.return_value = [dummy_kline]

    handler = RepairDataGapCommandHandler(client, repo)
    cmd = RepairDataGapCommand(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE,
        start_time=start,
        end_time=end,
    )

    result = handler.execute(cmd)

    assert result.success is True
    assert result.repaired_candles == 1
    assert "1 candles" in result.message
    repo.save_klines.assert_called_once_with([dummy_kline])


def test_repair_data_gap_cancelled():
    client = Mock()
    client.get_historical_klines.side_effect = ExchangeRequestCancelledError()
    repo = Mock()

    handler = RepairDataGapCommandHandler(client, repo)
    cmd = RepairDataGapCommand(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE,
        start_time=datetime(2024, 1, 1, tzinfo=UTC),
        end_time=datetime(2024, 1, 2, tzinfo=UTC),
    )

    result = handler.execute(cmd)

    assert result.success is False
    assert result.repaired_candles == 0
    assert "cancelled" in result.message
    repo.save_klines.assert_not_called()
