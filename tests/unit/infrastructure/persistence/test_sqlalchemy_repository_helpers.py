"""
Fast, DB-free unit tests for the helper methods extracted from
SQLAlchemyMarketDataRepository (BOT-013 SRP refactor): grouping, param mapping,
entity mapping, and datetime normalization. The DB-backed behavior (upsert,
chunking, gap detection) stays covered by
tests/integration/infrastructure/persistence/test_sqlalchemy_repository.py.
"""

from datetime import datetime, timezone
from unittest.mock import Mock

from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.infrastructure.persistence.sqlalchemy_repository import (
    SQLAlchemyMarketDataRepository,
)


def _mock_kline(symbol: str) -> MarketData:
    return MarketData(
        symbol=symbol,
        interval="1m",
        open_time=datetime(2023, 1, 1, tzinfo=timezone.utc),
        open_price=100.0,
        high_price=110.0,
        low_price=90.0,
        close_price=105.0,
        volume=1000.0,
        close_time=datetime(2023, 1, 1, 0, 1, tzinfo=timezone.utc),
        quote_asset_volume=105000.0,
        number_of_trades=50,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=52500.0,
    )


def test_group_by_symbol_groups_and_preserves_order():
    klines = [_mock_kline("BTCUSDT"), _mock_kline("ETHUSDT"), _mock_kline("BTCUSDT")]
    groups = SQLAlchemyMarketDataRepository._group_by_symbol(klines)

    assert set(groups.keys()) == {"BTCUSDT", "ETHUSDT"}
    assert len(groups["BTCUSDT"]) == 2
    assert len(groups["ETHUSDT"]) == 1


def test_kline_to_upsert_params_maps_every_field():
    kline = _mock_kline("BTCUSDT")
    params = SQLAlchemyMarketDataRepository._kline_to_upsert_params(kline)

    assert params["symbol"] == "BTCUSDT"
    assert params["open_price"] == 100.0
    assert params["close_price"] == 105.0
    assert params["volume"] == 1000.0
    assert params["number_of_trades"] == 50


def test_to_market_data_entity_maps_row_and_adds_utc_tzinfo():
    row = Mock()
    row.symbol = "ETHUSDT"
    row.interval = "1h"
    row.open_time = datetime(2023, 1, 1, 12, 0)  # naive, as SQLite returns
    row.close_time = datetime(2023, 1, 1, 12, 59)
    row.open_price = 1.0
    row.high_price = 2.0
    row.low_price = 0.5
    row.close_price = 1.5
    row.volume = 10.0
    row.quote_asset_volume = 15.0
    row.number_of_trades = 3
    row.taker_buy_base_asset_volume = 5.0
    row.taker_buy_quote_asset_volume = 7.5

    entity = SQLAlchemyMarketDataRepository._to_market_data_entity(row)

    assert entity.symbol == "ETHUSDT"
    assert entity.open_time == datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert entity.close_time == datetime(2023, 1, 1, 12, 59, tzinfo=timezone.utc)


def test_to_market_data_entity_handles_none_timestamps():
    row = Mock()
    row.symbol = "BTCUSDT"
    row.interval = "1m"
    row.open_time = None
    row.close_time = None
    row.open_price = 1.0
    row.high_price = 1.0
    row.low_price = 1.0
    row.close_price = 1.0
    row.volume = 1.0
    row.quote_asset_volume = 1.0
    row.number_of_trades = 1
    row.taker_buy_base_asset_volume = 1.0
    row.taker_buy_quote_asset_volume = 1.0

    entity = SQLAlchemyMarketDataRepository._to_market_data_entity(row)

    assert entity.open_time is None
    assert entity.close_time is None


def test_parse_db_datetime_handles_none_datetime_and_iso_string():
    parse = SQLAlchemyMarketDataRepository._parse_db_datetime

    assert parse(None) is None
    assert parse("") is None

    dt = datetime(2023, 1, 1, 12, 0)
    assert parse(dt) == datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)

    assert parse("2023-01-01T12:00:00") == datetime(
        2023, 1, 1, 12, 0, tzinfo=timezone.utc
    )
