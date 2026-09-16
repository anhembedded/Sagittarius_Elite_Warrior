"""`EPIC-025` PR 1.4b-2 — the row projections, carried over from the two QML
view models this slice deleted.

Every assertion here was in `qml/PositionsTable/tests/test_positions_vm.py` or
`qml/OpenOrdersTable/tests/test_open_orders_vm.py`, restated against the
dataclass instead of the QML-facing dict those VMs produced. The one guarantee
deliberately **not** carried over is "profit and loss use distinct colours":
ADR D21 leaves colour to the OS palette, so the sign lives in the text and the
emphasis is a bold cell — `test_positions_panel.py` holds that instead.
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
    def test_every_field_is_formatted_text(self) -> None:
        row = build_position_row(position())

        assert row.symbol == "BTCUSDT"
        assert row.side is PositionSide.LONG
        assert row.quantity_text == "0.5000"
        assert row.entry_price_text == "64,000.00"
        assert row.mark_price_text == "64,500.00"
        assert row.unrealized_pnl_text == "+10.00 USDT"
        assert row.leverage == 10

    def test_side_comes_from_the_signed_amount(self) -> None:
        assert build_position_row(position(amt="1.0")).side is PositionSide.LONG
        assert build_position_row(position(amt="-1.0")).side is PositionSide.SHORT

    def test_a_short_position_shows_its_size_unsigned(self) -> None:
        """The sign is the side, and the side is its own column — a size of
        `-0.5000` next to `SHORT` says the same thing twice and reads as a
        negative quantity."""
        assert build_position_row(position(amt="-0.5")).quantity_text == "0.5000"

    def test_a_loss_is_signed_and_marked_as_a_loss(self) -> None:
        row = build_position_row(position(pnl="-10.0"))

        assert row.unrealized_pnl_text == "-10.00 USDT"
        assert row.pnl_is_profit is False

    def test_a_liquidation_price_the_exchange_omits_renders_as_a_dash(self) -> None:
        assert build_position_row(position()).liquidation_price_text == "—"

    def test_a_reported_liquidation_price_renders_formatted(self) -> None:
        row = build_position_row(position(liquidation_price=Decimal("32140.00")))

        assert row.liquidation_price_text == "32,140.00"


class TestAnOpenOrderRow:
    def test_every_field_is_formatted_text(self) -> None:
        row = build_open_order_row(order())

        assert row.client_order_id == "sew-1"
        assert row.symbol == "BTCUSDT"
        assert row.side is OrderSide.BUY
        assert row.order_type_text == "LIMIT"
        assert row.quantity_text == "0.2500"
        assert row.price_text == "64,000.00"
        assert row.status_text == "NEW"

    def test_a_market_order_has_no_price_to_show(self) -> None:
        row = build_open_order_row(order(order_type=OrderType.MARKET, price=None))

        assert row.price_text == "—"

    def test_an_order_the_exchange_has_not_timestamped_shows_a_dash(self) -> None:
        assert build_open_order_row(order()).order_time_text == "—"

    def test_the_exchange_order_time_renders_in_the_display_timezone(self) -> None:
        row = build_open_order_row(
            order(order_time=datetime(2026, 9, 15, 12, 0, tzinfo=UTC)),
            tz_name="UTC",
        )

        assert row.order_time_text.startswith("2026-09-15")
