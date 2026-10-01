from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order import (
    PreviewOrderQuery,
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    NotionalCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.stop_price_check import (
    StopPriceCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    venue_context,
)


class _StaticMetadataProvider(IMarketMetadataProvider):
    """A real, tiny `IMarketMetadataProvider` — no network, no mock.
    `testing-rule.md` §2's "true boundary" for this port is the exchange's
    `exchangeInfo` endpoint; this fake stands in exactly there, nowhere
    else."""

    def __init__(self, catalog: dict[str, SymbolOrderMetadata]) -> None:
        self._catalog = catalog

    def get_or_fetch(self, symbol: str) -> SymbolOrderMetadata | None:
        return self._catalog.get(symbol)

    def refresh(self) -> None:
        raise NotImplementedError("Not exercised by this fake's tests.")


def _btcusdt_metadata(market_step_size: Decimal | None = None) -> SymbolOrderMetadata:
    return SymbolOrderMetadata(
        symbol="BTCUSDT",
        status="TRADING",
        step_size=Decimal("0.001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(100),
        quantity_precision=3,
        price_precision=2,
        fetched_at=datetime(2026, 8, 27, tzinfo=UTC),
        market_step_size=market_step_size,
    )


def _handler(metadata: SymbolOrderMetadata | None = None) -> PreviewOrderQueryHandler:
    provider = _StaticMetadataProvider({"BTCUSDT": metadata or _btcusdt_metadata()})
    return PreviewOrderQueryHandler(
        FakeVenueContexts(
            venue_context(TradingVenue.FUTURES_TESTNET, metadata_provider=provider)
        )
    )


def test_market_order_rounds_quantity_down_to_step_size() -> None:
    """This epic's own worked example (`EPIC-021E` §5): 0.0137 at step
    0.001 rounds down to 0.013."""
    preview = _handler().execute(
        PreviewOrderQuery(
            venue=TradingVenue.FUTURES_TESTNET,
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
            venue=TradingVenue.FUTURES_TESTNET,
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
            venue=TradingVenue.FUTURES_TESTNET,
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
            venue=TradingVenue.FUTURES_TESTNET,
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
            venue=TradingVenue.FUTURES_TESTNET,
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
            venue=TradingVenue.FUTURES_TESTNET,
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
            venue=TradingVenue.FUTURES_TESTNET,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.0137"),
            reference_price=Decimal(64000),
        )
    )

    assert preview.order.time_in_force is None


def test_market_order_rounds_with_market_lot_size_when_published() -> None:
    """`EPIC-027I`'s own acceptance criterion: a MARKET order rounds with
    `MARKET_LOT_SIZE` when the exchange publishes one — this is the wiring
    a `pr-review` finding on PR #283 caught missing: `step_size_for()`
    existed and was unit-tested in isolation, but this handler, the only
    place a live order's quantity is rounded, never called it. Break this
    wiring (revert to plain `metadata.step_size`) and this test goes red."""
    metadata = _btcusdt_metadata(market_step_size=Decimal("0.01"))

    preview = _handler(metadata).execute(
        PreviewOrderQuery(
            venue=TradingVenue.FUTURES_TESTNET,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.0137"),
            reference_price=Decimal(64000),
        )
    )

    # 0.0137 rounded down to a 0.01 step is 0.01, not 0.013 (LOT_SIZE's step).
    assert preview.order.quantity == Decimal("0.01")
    assert preview.step_size == Decimal("0.01")


def test_limit_order_ignores_market_lot_size_even_when_published() -> None:
    """The other half of the same acceptance criterion: a LIMIT order
    always rounds with `LOT_SIZE`, never `MARKET_LOT_SIZE`, even when the
    symbol publishes one."""
    metadata = _btcusdt_metadata(market_step_size=Decimal("0.01"))

    preview = _handler(metadata).execute(
        PreviewOrderQuery(
            venue=TradingVenue.FUTURES_TESTNET,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.0137"),
            reference_price=Decimal("64000.005"),
        )
    )

    assert preview.order.quantity == Decimal("0.013")
    assert preview.step_size == Decimal("0.001")


def test_unknown_symbol_raises_value_error() -> None:
    with pytest.raises(ValueError, match="UNKNOWNUSDT"):
        _handler().execute(
            PreviewOrderQuery(
                venue=TradingVenue.FUTURES_TESTNET,
                symbol="UNKNOWNUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal(1),
                reference_price=Decimal(1),
            )
        )


def _stop_query(
    direction: OrderSide, stop: str, **overrides: object
) -> PreviewOrderQuery:
    fields: dict[str, object] = {
        "venue": TradingVenue.FUTURES_TESTNET,
        "symbol": "BTCUSDT",
        "side": direction,
        "order_type": OrderType.STOP_LIMIT,
        "quantity": Decimal("0.01"),
        "reference_price": Decimal(64100),
        "stop_price": Decimal(stop),
        "last_price": Decimal(64000),
    }
    return PreviewOrderQuery(**(fields | overrides))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("side", "stop", "rounded"),
    [
        (OrderSide.BUY, "64050.001", "64050.01"),
        (OrderSide.SELL, "63950.009", "63950.00"),
    ],
)
def test_a_stop_rounds_to_the_tick_away_from_the_market(
    side: OrderSide, stop: str, rounded: str
) -> None:
    """`EPIC-028O` — the opposite of a limit price: up for a buy stop, down
    for a sell stop, so rounding never moves a stop onto the crossed side."""
    preview = _handler().execute(_stop_query(side, stop))

    assert preview.order.stop_price == Decimal(rounded)
    assert preview.stop_check is StopPriceCheck.ON_TRIGGER_SIDE
    assert preview.order.price is not None
    assert preview.order.time_in_force is TimeInForce.GTC


def test_a_buy_stop_below_the_last_price_is_marked_wrong_side() -> None:
    preview = _handler().execute(_stop_query(OrderSide.BUY, "63999.99"))

    assert preview.stop_check is StopPriceCheck.WRONG_SIDE


def test_a_chosen_time_in_force_replaces_gtc_and_other_orders_have_no_stop_check() -> (
    None
):
    preview = _handler().execute(
        PreviewOrderQuery(
            venue=TradingVenue.FUTURES_TESTNET,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.01"),
            reference_price=Decimal(64000),
            time_in_force=TimeInForce.IOC,
        )
    )

    assert preview.order.time_in_force is TimeInForce.IOC
    assert preview.stop_check is None


def test_a_quote_sized_market_buy_spends_its_quote_and_estimates_the_quantity() -> None:
    preview = _handler().execute(
        PreviewOrderQuery(
            venue=TradingVenue.FUTURES_TESTNET,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal(0),
            reference_price=Decimal(64000),
            quote_quantity=Decimal(1000),
        )
    )

    assert preview.order.quote_quantity == Decimal(1000)
    assert preview.estimated_notional == Decimal(1000)
    # 1000 / 64000 = 0.015625, rounded down to the 0.001 step.
    assert preview.order.quantity == Decimal("0.015")
    assert preview.notional_check is NotionalCheck.SUFFICIENT


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"stop_price": None}, "stop price and the last price"),
        ({"last_price": None}, "stop price and the last price"),
        ({"order_type": OrderType.LIMIT}, "takes no stop price"),
        (
            {
                "order_type": OrderType.MARKET,
                "stop_price": None,
                "time_in_force": TimeInForce.GTC,
            },
            "takes no time in force",
        ),
        (
            {
                "order_type": OrderType.LIMIT,
                "stop_price": None,
                "quote_quantity": Decimal(5),
            },
            "market buy",
        ),
        (
            {
                "order_type": OrderType.MARKET,
                "stop_price": None,
                "side": OrderSide.SELL,
                "quote_quantity": Decimal(5),
            },
            "market buy",
        ),
        (
            {
                "order_type": OrderType.MARKET,
                "stop_price": None,
                "quote_quantity": Decimal(0),
            },
            "positive",
        ),
    ],
)
def test_an_inconsistent_order_is_refused_at_construction(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _stop_query(OrderSide.BUY, "64050", **overrides)
