from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.domain.csv_kline_parser import (
    parse_csv_klines,
)


def test_binance_style_header_parses_every_column():
    csv_text = (
        "open_time,open,high,low,close,volume,close_time,quote_asset_volume,"
        "number_of_trades,taker_buy_base_asset_volume,taker_buy_quote_asset_volume\n"
        "1700000000000,100,110,90,105,1234.5,1700000059999,123456.7,42,600.1,60000.2\n"
    )

    result = parse_csv_klines(csv_text, "BTCUSDT", TimeFrame.ONE_MINUTE)

    assert result.warnings == []
    assert len(result.klines) == 1
    kline = result.klines[0]
    assert kline.symbol == "BTCUSDT"
    assert kline.interval == TimeFrame.ONE_MINUTE.value
    assert kline.open_price == 100.0
    assert kline.close_price == 105.0
    assert kline.number_of_trades == 42
    assert kline.taker_buy_base_asset_volume == 600.1
    assert kline.open_time == datetime.fromtimestamp(1700000000, UTC)


def test_tradingview_style_header_defaults_binance_only_fields():
    """TradingView's export has no `close_time`/`quote_asset_volume`/etc — the
    parser must derive `close_time` (`BUG-022` inclusive-instant convention)
    and default the Binance-only fields to 0/0.0 rather than failing."""
    csv_text = "time,open,high,low,close,Volume\n1700000000,1,2,0.5,1.5,10\n"

    result = parse_csv_klines(csv_text, "ETHUSDT", TimeFrame.ONE_MINUTE)

    assert result.warnings == []
    kline = result.klines[0]
    assert kline.open_time == datetime.fromtimestamp(1700000000, UTC)
    expected_close = datetime.fromtimestamp(1700000000 + 60 - 1e-3, UTC)
    assert kline.close_time == expected_close
    assert kline.quote_asset_volume == 0.0
    assert kline.number_of_trades == 0
    assert kline.taker_buy_base_asset_volume == 0.0
    assert kline.taker_buy_quote_asset_volume == 0.0


def test_metatrader_style_header_uses_date_alias_and_iso_timestamp():
    csv_text = "Date,Open,High,Low,Close,Volume\n2026-09-01 00:00:00,1,2,0.5,1.5,10\n"

    result = parse_csv_klines(csv_text, "XAUUSD", TimeFrame.ONE_HOUR)

    assert result.warnings == []
    kline = result.klines[0]
    assert kline.open_time == datetime(2026, 9, 1, 0, 0, 0, tzinfo=UTC)


def test_missing_required_column_fails_whole_file():
    csv_text = "open,high,low,close\n1,2,0.5,1.5\n"

    result = parse_csv_klines(csv_text, "BTCUSDT", TimeFrame.ONE_MINUTE)

    assert result.klines == []
    assert "open_time" in result.warnings[0]


def test_malformed_row_is_skipped_with_warning_not_whole_file():
    csv_text = (
        "open_time,open,high,low,close,volume\n"
        "1700000000,1,2,0.5,1.5,10\n"
        "not_a_timestamp,1,2,0.5,1.5,10\n"
        "1700000060,2,3,1.5,2.5,20\n"
    )

    result = parse_csv_klines(csv_text, "BTCUSDT", TimeFrame.ONE_MINUTE)

    assert len(result.klines) == 2
    assert len(result.warnings) == 1
    assert "Row 3" in result.warnings[0]


def test_empty_file_produces_no_klines_and_one_warning():
    result = parse_csv_klines("", "BTCUSDT", TimeFrame.ONE_MINUTE)

    assert result.klines == []
    assert result.warnings == ["File is empty."]
