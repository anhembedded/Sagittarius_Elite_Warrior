"""`EPIC-025` PR 1.4b-2 — the row projections, carried over from the two QML
view models this slice deleted.

Since `EPIC-033N` a row holds values and the table's formatter writes them,
so these tests check the values; how they read is `test_*_panel.py`'s, through
the view's own delegate. The one guarantee deliberately **not** carried over
from the QML is "profit and loss use distinct colours": ADR D21 leaves colour
to the OS palette, so the sign lives in the number and the emphasis is a bold
cell — `test_positions_panel.py` holds that instead.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.holding_row import (
    build_holding_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_order_row import (
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    build_position_row,
)


def position(
    symbol: str = "BTCUSDT",
    amt: str = "0.5",
    pnl: str = "10.0",
    leverage: int = 10,
    liquidation_price: Decimal | None = None,
) -> LivePosition:
    return LivePosition(
        symbol=symbol,
        position_amt=Decimal(amt),
        entry_price=Decimal("64000.00"),
        mark_price=Decimal("64500.00"),
        unrealized_pnl=Decimal(pnl),
        leverage=leverage,
        margin_type=MarginType.CROSSED,
        liquidation_price=liquidation_price,
        updated_at=datetime.now(UTC),
    )


def order(
    symbol: str = "BTCUSDT",
    side: OrderSide = OrderSide.BUY,
    order_type: OrderType = OrderType.LIMIT,
    price: Decimal | None = Decimal("64000.00"),
    client_order_id: str = "sew-1",
    order_time: datetime | None = None,
) -> Order:
    return Order(
        client_order_id=ClientOrderId(client_order_id),
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=Decimal("0.25"),
        price=price,
        status=OrderStatus.NEW,
        order_time=order_time,
    )


class TestAPositionRow:
    def test_it_carries_the_positions_values(self) -> None:
        row = build_position_row(position())

        assert row.symbol == "BTCUSDT"
        assert row.side is PositionSide.LONG
        assert row.quantity == Decimal("0.5")
        assert row.entry_price == Decimal("64000.00")
        assert row.mark_price == Decimal("64500.00")
        assert row.unrealized_pnl == Decimal("10.0")
        assert row.leverage == 10

    def test_side_comes_from_the_signed_amount(self) -> None:
        assert build_position_row(position(amt="1.0")).side is PositionSide.LONG
        assert build_position_row(position(amt="-1.0")).side is PositionSide.SHORT

    def test_a_short_position_shows_its_size_unsigned(self) -> None:
        """The sign is the side, and the side is its own column — a size of
        `-0.5` next to `SHORT` says the same thing twice and reads as a
        negative quantity."""
        assert build_position_row(position(amt="-0.5")).quantity == Decimal("0.5")

    def test_a_loss_keeps_its_sign_and_is_marked_as_a_loss(self) -> None:
        row = build_position_row(position(pnl="-10.0"))

        assert row.unrealized_pnl == Decimal("-10.0")
        assert row.pnl_is_profit is False

    def test_a_break_even_position_is_not_a_loss(self) -> None:
        assert build_position_row(position(pnl="0")).pnl_is_profit is True

    def test_a_liquidation_price_the_exchange_omits_is_unknown(self) -> None:
        assert build_position_row(position()).liquidation_price is None

    def test_a_reported_liquidation_price_is_kept(self) -> None:
        row = build_position_row(position(liquidation_price=Decimal("32140.00")))

        assert row.liquidation_price == Decimal("32140.00")


class TestAnOpenOrderRow:
    def test_it_carries_the_orders_values(self) -> None:
        row = build_open_order_row(order())

        assert row.client_order_id == "sew-1"
        assert row.symbol == "BTCUSDT"
        assert row.side is OrderSide.BUY
        assert row.order_type == "LIMIT"
        assert row.quantity == Decimal("0.25")
        assert row.price == Decimal("64000.00")
        assert row.status == "NEW"

    def test_a_multi_word_type_reads_as_words(self) -> None:
        row = build_open_order_row(order(order_type=OrderType.STOP_MARKET))

        assert row.order_type == "STOP MARKET"

    def test_a_market_order_has_no_price(self) -> None:
        row = build_open_order_row(order(order_type=OrderType.MARKET, price=None))

        assert row.price is None

    def test_an_order_the_exchange_has_not_timestamped_has_no_time(self) -> None:
        assert build_open_order_row(order()).order_time is None

    def test_the_exchange_order_time_is_kept(self) -> None:
        moment = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)

        assert build_open_order_row(order(order_time=moment)).order_time == moment


def holding(asset: str = "BTC", free: str = "0.5", locked: str = "0") -> SpotHolding:
    return SpotHolding(
        asset=asset,
        free=Decimal(free),
        locked=Decimal(locked),
        dust_threshold=Decimal("0.0001"),
    )


class TestAHoldingRow:
    def test_it_carries_the_balances_and_their_value(self) -> None:
        row = build_holding_row(holding(), prices={"BTC": Decimal(64000)})

        assert row.asset == "BTC"
        assert row.free == Decimal("0.5")
        assert row.locked == Decimal(0)
        assert row.value == Decimal(32000)

    def test_free_and_locked_both_contribute_to_value(self) -> None:
        row = build_holding_row(
            holding(free="0.5", locked="0.25"), prices={"BTC": Decimal(64000)}
        )

        assert row.value == Decimal(48000)

    def test_a_missing_price_leaves_the_value_unknown(self) -> None:
        """An asset with no live price known (no chart ever opened for it)
        must not guess a value — `None`, an empty cell, never zero."""
        row = build_holding_row(holding(asset="XRP"), prices={})

        assert row.value is None
