from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.use_cases.database.clear_market_data import (
    ClearMarketDataCommand,
    ClearMarketDataCommandHandler,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


def test_clear_market_data_for_specific_symbol_and_interval():
    repo = Mock()
    repo.clear_klines.return_value = 1440
    handler = ClearMarketDataCommandHandler(repo)

    cmd = ClearMarketDataCommand(symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE)
    result = handler.execute(cmd)

    assert result.success is True
    assert result.deleted_records == 1440
    assert "BTCUSDT" in result.message
    repo.clear_klines.assert_called_once_with(
        symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE
    )


def test_clear_market_data_for_symbol_all_intervals():
    repo = Mock()
    repo.clear_klines.return_value = 5000
    handler = ClearMarketDataCommandHandler(repo)

    cmd = ClearMarketDataCommand(symbol="ETHUSDT", interval=None)
    result = handler.execute(cmd)

    assert result.success is True
    assert result.deleted_records == 5000
    repo.clear_klines.assert_called_once_with(symbol="ETHUSDT", interval=None)


def test_clear_market_data_purge_all():
    repo = Mock()
    repo.purge_all.return_value = 12
    handler = ClearMarketDataCommandHandler(repo)

    cmd = ClearMarketDataCommand(purge_all=True)
    result = handler.execute(cmd)

    assert result.success is True
    assert result.deleted_records == 12
    assert "12 database shards" in result.message
    repo.purge_all.assert_called_once()


def test_clear_market_data_empty_symbol_fails():
    repo = Mock()
    handler = ClearMarketDataCommandHandler(repo)

    cmd = ClearMarketDataCommand(symbol="")
    result = handler.execute(cmd)

    assert result.success is False
    assert result.deleted_records == 0
    assert "trống" in result.message


def test_clear_market_data_exception_returns_failure():
    repo = Mock()
    repo.clear_klines.side_effect = RuntimeError("Disk IO failure")
    handler = ClearMarketDataCommandHandler(repo)

    cmd = ClearMarketDataCommand(symbol="BTCUSDT")
    result = handler.execute(cmd)

    assert result.success is False
    assert result.deleted_records == 0
    assert "Disk IO failure" in result.message
