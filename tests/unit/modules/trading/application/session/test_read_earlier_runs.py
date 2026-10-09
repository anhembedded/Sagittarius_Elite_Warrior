"""`BUG-196` — what an owner's earlier runs left, from the venue's history.

@details The handler is real over `FakeAccountHistoryReader` (the port's fake);
the account's holdings come from a `Mock(spec=ITradingAccountReader)`, trading's
own port. Time is the fake history's `now`, so no test depends on the clock.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.application.session.read_earlier_runs import (
    ReadEarlierRunsCommand,
    ReadEarlierRunsCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.earlier_runs_inventory import (
    EarlierRunsInventory,
    EarlierRunsRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_history_reader import (
    FakeAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    single_venue_scopes,
    venue_context,
)

_SPOT = TradingVenue.SPOT_TESTNET
_NOW = datetime.now(UTC)
_CREATED = _NOW - timedelta(days=5)
_RUN_2 = _NOW - timedelta(days=1)
_TAG = "a3f9c1"
_REQUEST = EarlierRunsRequest(_TAG, "ETHUSDT", "ETH", _CREATED, _RUN_2)


def _buy(
    number: int, at: datetime, quantity: str = "0.01", tag: str = _TAG
) -> tuple[OrderRecord, TradeRecord]:
    order = Order(
        ClientOrderId(f"SEW-{tag}-{number:010x}"),
        "ETHUSDT",
        OrderSide.BUY,
        OrderType.MARKET,
        Decimal(quantity),
        OrderStatus.FILLED,
    )
    record = OrderRecord(order, Decimal(quantity), Decimal(2500), at, number)
    trade = TradeRecord(
        "ETHUSDT",
        900 + number,
        number,
        OrderSide.BUY,
        Decimal(2500),
        Decimal(quantity),
        Decimal(2500) * Decimal(quantity),
        Decimal(0),
        "BNB",
        at,
    )
    return record, trade


def _account(free: str | None) -> Mock:
    reader = Mock(spec=ITradingAccountReader)
    holdings = (
        None
        if free is None
        else (SpotHolding("ETH", Decimal(free), Decimal(0), Decimal("0.0001")),)
    )
    reader.check_connection.return_value = ExchangeConnectionStatus(
        _SPOT, True, None, 0, Decimal(0), None, None, None, holdings
    )
    return reader


def _ask(
    history: FakeAccountHistoryReader, free: str | None = "1"
) -> EarlierRunsInventory:
    context = venue_context(
        _SPOT,
        history_reader=history,
        account_reader=_account(free),  # type: ignore[arg-type]
    )
    handler = ReadEarlierRunsCommandHandler(
        single_venue_scopes(context, TradingSessionState())
    )
    return handler.execute(ReadEarlierRunsCommand(_REQUEST, venue=_SPOT))


def _history(*rows: tuple[OrderRecord, TradeRecord]) -> FakeAccountHistoryReader:
    return FakeAccountHistoryReader(
        [order for order, _ in rows], [trade for _, trade in rows], now=_NOW
    )


def test_base_a_run_before_this_one_bought_is_left() -> None:
    earlier = _buy(1, _CREATED + timedelta(hours=1))

    answer = _ask(_history(earlier))

    assert answer.is_known
    assert answer.quantity == Decimal("0.01")
    assert answer.cost == Decimal(25)


def test_a_fill_of_the_current_run_is_not_an_earlier_runs() -> None:
    answer = _ask(_history(_buy(1, _RUN_2 + timedelta(hours=1))))

    assert answer.quantity == 0
    assert answer.is_known


def test_another_owners_orders_are_not_counted() -> None:
    answer = _ask(_history(_buy(1, _CREATED + timedelta(hours=1), tag="bbbbbb")))

    assert answer.quantity == 0


def test_a_sell_between_the_runs_takes_its_share_away() -> None:
    bought = _buy(1, _CREATED + timedelta(hours=1), "0.02")
    order, trade = _buy(2, _CREATED + timedelta(hours=2), "0.01")
    sold = (
        OrderRecord(
            Order(
                order.order.client_order_id,
                "ETHUSDT",
                OrderSide.SELL,
                OrderType.MARKET,
                Decimal("0.01"),
                OrderStatus.FILLED,
            ),
            order.executed_quantity,
            Decimal(2500),
            order.created_at,
            order.exchange_order_id,
        ),
        TradeRecord(
            "ETHUSDT",
            trade.trade_id,
            trade.order_id,
            OrderSide.SELL,
            trade.price,
            trade.quantity,
            trade.quote_quantity,
            Decimal(0),
            "USDT",
            trade.time,
        ),
    )

    answer = _ask(_history(bought, sold))

    assert answer.quantity == Decimal("0.01")


def test_a_coin_the_user_moved_by_hand_is_not_claimed() -> None:
    answer = _ask(_history(_buy(1, _CREATED + timedelta(hours=1))), free="0.004")

    assert answer.quantity == Decimal("0.004")
    assert answer.cost == Decimal(10)


def test_a_venue_that_does_not_answer_is_unknown_not_empty() -> None:
    history = _history(_buy(1, _CREATED + timedelta(hours=1)))
    history.order_history = Mock(  # type: ignore[method-assign]
        side_effect=AccountHistoryUnavailableError("down")
    )

    answer = _ask(history)

    assert not answer.is_known
    assert answer.quantity == 0
    assert "down" in answer.unavailable


def test_holdings_that_were_not_read_are_unknown_not_empty() -> None:
    answer = _ask(_history(_buy(1, _CREATED + timedelta(hours=1))), free=None)

    assert not answer.is_known
