from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order import (
    PreviewOrderQuery,
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.order_quantity_rounding_policy import (
    NotionalCheck,
)


class _StaticMetadataProvider(IMarketMetadataProvider):
    """A real, tiny `IMarketMetadataProvider` — no network, no mock.
    `testing-rule.md` §2's "true boundary" for this port is the exchange's
    `exchangeInfo` endpoint; this fake stands in exactly there, nowhere
    else."""

    def __init__(self, catalog: dict[str, FuturesSymbolMetadata]) -> None:
        self._catalog = catalog

    def get_or_fetch(self, symbol: str) -> FuturesSymbolMetadata | None:
        return self._catalog.get(symbol)

    def refresh(self) -> None:
        raise NotImplementedError("Not exercised by this fake's tests.")


def _btcusdt_metadata() -> FuturesSymbolMetadata:
    return FuturesSymbolMetadata(
        symbol="BTCUSDT",
        status="TRADING",
        step_size=Decimal("0.001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(100),
        quantity_precision=3,
        price_precision=2,
        fetched_at=datetime(2026, 8, 27, tzinfo=UTC),
    )


def _handler() -> PreviewOrderQueryHandler:
    provider = _StaticMetadataProvider({"BTCUSDT": _btcusdt_metadata()})
    return PreviewOrderQueryHandler(provider)


def test_market_order_rounds_quantity_down_to_step_size() -> None:
    """This epic's own worked example (`EPIC-021E` §5): 0.0137 at step
    0.001 rounds down to 0.013."""
    preview = _handler().execute(
        PreviewOrderQuery(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.0137"),
            reference_price=Decimal(64000),
        )
    )

    assert preview.order.quantity == Decimal("0.013")
    assert preview.raw_quantity == Decimal("0.0137")
    assert preview.step_size == Decimal("0.001")


def test_market_order_estimates_notional_and_passes_min_notional() -> None:
    """0.013 * 64000 = 832.00, clears the 100 USDT minimum — the epic's own
    "SẴN SÀNG GỬI" worked example."""
    preview = _handler().execute(
        PreviewOrderQuery(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.0137"),
            reference_price=Decimal(64000),
        )
    )

    assert preview.estimated_notional == Decimal("832.000")
    assert preview.min_notional == Decimal(100)
    assert preview.notional_check is NotionalCheck.SUFFICIENT


def test_small_order_is_rejected_for_insufficient_notional() -> None:
    """0.001 * 64000 = 64.00 < 100 minNotional — the epic's own "TỪ CHỐI
    MIN_NOTIONAL" worked example."""
    preview = _handler().execute(
        PreviewOrderQuery(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.001"),
            reference_price=Decimal(64000),
        )
    )

    assert preview.estimated_notional == Decimal("64.000")
    assert preview.notional_check is NotionalCheck.INSUFFICIENT


def test_market_order_has_no_price_field() -> None:
    preview = _handler().execute(
        PreviewOrderQuery(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.0137"),
            reference_price=Decimal(64000),
        )
    )

    assert preview.order.price is None
    assert preview.order.status is OrderStatus.NEW


def test_limit_order_carries_the_rounded_price() -> None:
    preview = _handler().execute(
        PreviewOrderQuery(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.0137"),
            reference_price=Decimal("64000.005"),
        )
    )

    # BUY rounds its price down to the tick (OrderQuantityRoundingPolicy).
    assert preview.order.price == Decimal("64000.00")


def test_limit_order_defaults_to_good_til_canceled() -> None:
    """`BUG-116` — `Order.time_in_force` defaulted to `None` unconditionally
    (no caller ever set it), which `map_order_to_futures_params()` refuses
    to submit for a real `LIMIT` order ("LIMIT order is missing
    time_in_force."). Latent since `EPIC-021E`: the automated strategy
    path only ever sends `MARKET` orders, so nothing exercised this until
    a user's real click on the manual order card's "Limit" option — the
    first real caller ever to reach a live `LIMIT` submission — hit it
    directly. GTC is the correct default for a plain Limit order with no
    other time-in-force choice exposed anywhere in the UI."""
    preview = _handler().execute(
        PreviewOrderQuery(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.0137"),
            reference_price=Decimal("64000.005"),
        )
    )

    assert preview.order.time_in_force is TimeInForce.GTC


def test_market_order_has_no_time_in_force() -> None:
    preview = _handler().execute(
        PreviewOrderQuery(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.0137"),
            reference_price=Decimal(64000),
        )
    )

    assert preview.order.time_in_force is None


def test_unknown_symbol_raises_value_error() -> None:
    with pytest.raises(ValueError, match="UNKNOWNUSDT"):
        _handler().execute(
            PreviewOrderQuery(
                symbol="UNKNOWNUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal(1),
                reference_price=Decimal(1),
            )
        )
