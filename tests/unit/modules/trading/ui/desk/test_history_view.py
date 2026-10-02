"""`EPIC-028J` — a history tab names the pairs it read, says where its page
sits, and renders a figure the venue did not report as "—"."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HistoryPage,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_rows import (
    build_order_history_row,
    build_trade_history_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_view import (
    history_view_for,
    scope_text_for,
)

_AT = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)


def _record(average: Decimal | None) -> OrderRecord:
    return OrderRecord(
        order=Order(
            client_order_id=ClientOrderId("SEW-1"),
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.01"),
            status=OrderStatus.CANCELED,
            price=Decimal(59000),
        ),
        executed_quantity=Decimal(0),
        average_price=average,
        created_at=_AT,
    )


def _page(total: int, page: int, scanned: tuple[str, ...]) -> HistoryPage[OrderRecord]:
    return HistoryPage(
        rows=(_record(None),),
        page=page,
        total_rows=total,
        scanned_symbols=scanned,
        notices=("Older algo orders are not listed.",),
    )


def test_every_pair_read_is_named_so_the_tab_never_implies_the_whole_account() -> None:
    text = scope_text_for(("BTCUSDT", "ETHUSDT"))

    assert "BTCUSDT, ETHUSDT" in text
    assert "outside this list is not shown" in text


def test_one_pair_is_named_as_the_only_one_shown() -> None:
    assert scope_text_for(("BTCUSDT",)) == "Showing BTCUSDT."


def test_no_pair_to_read_says_why() -> None:
    assert "No pair to read" in scope_text_for(())


def test_a_middle_page_offers_both_directions_and_its_notices() -> None:
    view = history_view_for(
        _page(total=120, page=1, scanned=("BTCUSDT",)), build_order_history_row
    )

    assert view.page_text == "Page 2 of 3"
    assert (view.has_previous, view.has_next) == (True, True)
    assert view.notices == ("Older algo orders are not listed.",)


def test_the_last_page_offers_no_next() -> None:
    view = history_view_for(
        _page(total=100, page=1, scanned=("BTCUSDT",)), build_order_history_row
    )

    assert (view.has_previous, view.has_next) == (True, False)


def test_an_empty_history_has_no_pages() -> None:
    page: HistoryPage[OrderRecord] = HistoryPage(
        rows=(), page=0, total_rows=0, scanned_symbols=()
    )
    view = history_view_for(page, build_order_history_row)

    assert view.page_text == "No rows"
    assert (view.has_previous, view.has_next) == (False, False)


def test_an_order_with_nothing_filled_has_no_average_price() -> None:
    row = build_order_history_row(_record(None))

    assert row.average_price_text == "—"
    assert row.stop_price_text == "—"
    assert row.filled_text == "0.0000"
    assert row.status_text == "CANCELED"


def test_a_spot_fill_has_no_realized_pnl_and_keeps_its_fee_asset() -> None:
    row = build_trade_history_row(
        TradeRecord(
            symbol="BTCUSDT",
            trade_id=7,
            order_id=8,
            side=OrderSide.BUY,
            price=Decimal(60000),
            quantity=Decimal("0.01"),
            quote_quantity=Decimal(600),
            fee=Decimal("0.00001"),
            fee_asset="BTC",
            time=_AT,
        )
    )

    assert row.realized_pnl_text == "—"
    assert row.fee_text == "0.00001000 BTC"
