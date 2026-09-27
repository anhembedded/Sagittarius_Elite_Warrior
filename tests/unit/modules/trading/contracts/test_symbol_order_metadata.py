"""`SymbolOrderMetadata.step_size_for()` (`EPIC-027I`) — the MARKET-vs-LIMIT
lot-size selection this type gained when it stopped being Futures-only
(`FuturesSymbolMetadata` -> `SymbolOrderMetadata`). Not covered before this
task: the type had no dedicated unit test file until now."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import (
    OrderType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)

_FIXED_TIME = datetime(2026, 9, 1, tzinfo=UTC)


def _metadata(market_step_size: Decimal | None) -> SymbolOrderMetadata:
    return SymbolOrderMetadata(
        symbol="BTCUSDT",
        status="TRADING",
        step_size=Decimal("0.001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(5),
        quantity_precision=None,
        price_precision=None,
        fetched_at=_FIXED_TIME,
        market_step_size=market_step_size,
    )


def test_a_limit_order_always_uses_lot_size_step():
    metadata = _metadata(market_step_size=Decimal("0.0001"))

    assert metadata.step_size_for(OrderType.LIMIT) == Decimal("0.001")


def test_a_market_order_uses_market_lot_size_step_when_published():
    metadata = _metadata(market_step_size=Decimal("0.0001"))

    assert metadata.step_size_for(OrderType.MARKET) == Decimal("0.0001")


def test_a_market_order_falls_back_to_lot_size_step_when_market_lot_size_is_absent():
    """Every Futures symbol today, and any Spot symbol whose `exchangeInfo`
    genuinely carries no `MARKET_LOT_SIZE` filter (`SymbolOrderMetadata`'s
    own docstring)."""
    metadata = _metadata(market_step_size=None)

    assert metadata.step_size_for(OrderType.MARKET) == Decimal("0.001")


def test_a_stop_market_order_uses_lot_size_step_not_market_lot_size():
    """Only `OrderType.MARKET` itself gets the `MARKET_LOT_SIZE` fallback —
    `STOP_MARKET` is a LIMIT-shaped resting order on Binance's own book
    despite the name (`EPIC-027I`'s own acceptance criterion: "a LIMIT
    order with `LOT_SIZE`")."""
    metadata = _metadata(market_step_size=Decimal("0.0001"))

    assert metadata.step_size_for(OrderType.STOP_MARKET) == Decimal("0.001")
