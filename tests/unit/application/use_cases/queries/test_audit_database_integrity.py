from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.use_cases.queries.audit_database_integrity import (
    AuditDatabaseIntegrityQuery,
    AuditDatabaseIntegrityQueryHandler,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


def _make_candle(
    ts: datetime,
    open_price: float = 100.0,
    high_price: float = 105.0,
    low_price: float = 95.0,
    close_price: float = 102.0,
    volume: float = 10.0,
    trades: int = 100,
) -> MarketData:
    return MarketData(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE,
        open_time=ts,
        close_time=ts,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        volume=volume,
        quote_asset_volume=volume * close_price,
        number_of_trades=trades,
        taker_buy_base_asset_volume=volume * 0.5,
        taker_buy_quote_asset_volume=volume * close_price * 0.5,
    )


def test_audit_clean_data():
    t0 = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    t1 = datetime(2024, 1, 1, 0, 1, tzinfo=UTC)
    repo = Mock()
    repo.get_klines.return_value = [
        _make_candle(t0, 100.0, 110.0, 90.0, 105.0, 50.0),
        _make_candle(t1, 105.0, 115.0, 100.0, 110.0, 60.0),
    ]

    handler = AuditDatabaseIntegrityQueryHandler(repo)
    result = handler.execute(
        AuditDatabaseIntegrityQuery(symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE)
    )

    assert result.is_clean is True
    assert result.anomaly_count == 0
    assert len(result.anomalies) == 0
    assert result.total_checked == 2


def test_audit_detects_high_less_than_low():
    t0 = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    repo = Mock()
    # High is deliberately 90 while low is 110.
    repo.get_klines.return_value = [_make_candle(t0, 100.0, 90.0, 110.0, 95.0, 50.0)]

    handler = AuditDatabaseIntegrityQueryHandler(repo)
    result = handler.execute(
        AuditDatabaseIntegrityQuery(symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE)
    )

    assert result.is_clean is False
    assert result.anomaly_count >= 1
    types = [a.anomaly_type for a in result.anomalies]
    assert "HIGH_LESS_THAN_LOW" in types


def test_audit_detects_negative_volume():
    t0 = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    repo = Mock()
    repo.get_klines.return_value = [_make_candle(t0, 100.0, 105.0, 95.0, 102.0, -10.0)]

    handler = AuditDatabaseIntegrityQueryHandler(repo)
    result = handler.execute(
        AuditDatabaseIntegrityQuery(symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE)
    )

    assert result.is_clean is False
    types = [a.anomaly_type for a in result.anomalies]
    assert "NEGATIVE_VOLUME" in types


def test_audit_detects_non_finite_values():
    t0 = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    repo = Mock()
    repo.get_klines.return_value = [
        _make_candle(t0, float("nan"), 105.0, 95.0, 102.0, 10.0)
    ]

    handler = AuditDatabaseIntegrityQueryHandler(repo)
    result = handler.execute(
        AuditDatabaseIntegrityQuery(symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE)
    )

    assert result.is_clean is False
    types = [a.anomaly_type for a in result.anomalies]
    assert "NON_FINITE_VALUE" in types


def test_audit_detects_duplicate_timestamps():
    t0 = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    repo = Mock()
    repo.get_klines.return_value = [
        _make_candle(t0, 100.0, 105.0, 95.0, 102.0, 10.0),
        _make_candle(t0, 101.0, 106.0, 96.0, 103.0, 12.0),
    ]

    handler = AuditDatabaseIntegrityQueryHandler(repo)
    result = handler.execute(
        AuditDatabaseIntegrityQuery(symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE)
    )

    assert result.is_clean is False
    types = [a.anomaly_type for a in result.anomalies]
    assert "DUPLICATE_TIMESTAMP" in types
