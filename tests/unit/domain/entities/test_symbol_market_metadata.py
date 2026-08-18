"""Unit tests for SymbolMarketMetadata domain model and order intent validation (BOT-095E1)."""

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.domain.entities.symbol_market_metadata import (
    LotSizeFilter,
    MetadataVerificationStatus,
    NotionalFilter,
    OrderIntent,
    PriceFilter,
    SymbolMarketMetadata,
    validate_order_intent,
)


def _make_metadata(
    symbol: str = "BTCUSDT",
    min_price: float = 0.01,
    max_price: float = 100000.0,
    tick_size: float = 0.01,
    min_qty: float = 0.0001,
    max_qty: float = 1000.0,
    step_size: float = 0.0001,
    min_notional: float = 5.0,
    fetched_at: datetime | None = None,
) -> SymbolMarketMetadata:
    return SymbolMarketMetadata(
        symbol=symbol,
        status="TRADING",
        base_asset="BTC",
        quote_asset="USDT",
        price_filter=PriceFilter(min_price, max_price, tick_size),
        lot_size_filter=LotSizeFilter(min_qty, max_qty, step_size),
        notional_filter=NotionalFilter(min_notional, apply_to_market=True),
        fetched_at=fetched_at or datetime.now(UTC),
    )


def test_price_filter_validation():
    pf = PriceFilter(min_price=10.0, max_price=1000.0, tick_size=0.1)
    assert pf.validate_price(100.5) is None
    assert "nhỏ hơn giá tối thiểu" in pf.validate_price(5.0)
    assert "vượt quá giá tối đa" in pf.validate_price(2000.0)
    assert "không khớp bước giá tick size" in pf.validate_price(100.55)


def test_lot_size_filter_validation():
    ls = LotSizeFilter(min_qty=0.01, max_qty=100.0, step_size=0.01)
    assert ls.validate_quantity(1.5) is None
    assert "nhỏ hơn khối lượng tối thiểu" in ls.validate_quantity(0.005)
    assert "vượt quá khối lượng tối đa" in ls.validate_quantity(200.0)
    assert "không khớp bước nhảy lot size" in ls.validate_quantity(1.555)


def test_notional_filter_validation():
    nf = NotionalFilter(min_notional=10.0)
    assert nf.validate_notional(50.0) is None
    assert "nhỏ hơn giá trị tối thiểu" in nf.validate_notional(5.0)


def test_metadata_staleness():
    now = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
    fresh_meta = _make_metadata(fetched_at=now - timedelta(hours=1))
    assert not fresh_meta.is_stale(max_age_seconds=86400, now=now)

    stale_meta = _make_metadata(fetched_at=now - timedelta(days=2))
    assert stale_meta.is_stale(max_age_seconds=86400, now=now)


def test_validate_order_intent_missing_metadata():
    intent = OrderIntent(symbol="BTCUSDT", price=50000.0, quantity=0.1)
    result = validate_order_intent(intent, None)
    assert result.status == MetadataVerificationStatus.UNVERIFIED_MISSING
    assert result.is_valid is True
    assert "chưa có metadata" in result.explanation


def test_validate_order_intent_stale_metadata():
    now = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
    metadata = _make_metadata(fetched_at=now - timedelta(days=5))
    intent = OrderIntent(symbol="BTCUSDT", price=50000.0, quantity=0.1)
    result = validate_order_intent(intent, metadata, now=now)
    assert result.status == MetadataVerificationStatus.UNVERIFIED_STALE
    assert result.is_valid is True
    assert "metadata đã cũ" in result.explanation


def test_validate_order_intent_verified_valid():
    metadata = _make_metadata(min_notional=10.0)
    intent = OrderIntent(symbol="BTCUSDT", price=50000.0, quantity=0.1)
    result = validate_order_intent(intent, metadata)
    assert result.status == MetadataVerificationStatus.VERIFIED
    assert result.is_valid is True
    assert result.issues == ()
    assert "Đã xác minh theo quy tắc sàn Binance" in result.explanation


def test_validate_order_intent_verified_invalid_notional():
    metadata = _make_metadata(min_notional=100.0)
    intent = OrderIntent(
        symbol="BTCUSDT", price=500.0, quantity=0.1
    )  # notional = 50 < 100
    result = validate_order_intent(intent, metadata)
    assert result.status == MetadataVerificationStatus.VERIFIED
    assert result.is_valid is False
    assert len(result.issues) == 1
    assert "nhỏ hơn giá trị tối thiểu" in result.issues[0]
