"""`BUG-258` — the opening a start counted from the exchange is in the saved runtime when it is RUNNING.

The start counts the opening from the exchange's record (`PositionOpening._count_opening`), yet the
runtime books it only from the user-data stream's fill report. A stream that is late, or down,
leaves the saved position at 0 beside the 0.19 the exchange and trading both show, so the first gap
reconcile after RUNNING logs a WARNING and a second run may act on the mismatch. Red before: the
saved inventory stayed 0 until the stream reported.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HistoryPage,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_request import (
    HistoryRequest,
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
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    LAST_PRICE,
    SYMBOL,
    GridWorld,
    grid_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.position_world import (
    a_position_world,
)

S = BotLifecycleState
_AT = datetime(2026, 10, 21, 9, tzinfo=UTC)
_EXCHANGE_ORDER = 700
_TRADE = 9000


@dataclass(frozen=True)
class Opened:
    client_order_id: str
    quantity: Decimal


def _the_venue_shows_the_openings_it_filled(
    world: GridWorld,
    *,
    trades: int = 1,
    fee: str = "0",
    fee_asset: str = "USDT",
    holds_nothing_yet: bool = False,
    unreadable: bool = False,
) -> None:
    """The venue's order and trade history, read from what the book was asked to send: every
    market order is FILLED at the last price in `trades` trades, the way a market order fills
    (`holds_nothing_yet`: the history has not indexed it; `unreadable`: it does not answer)."""

    def market_orders() -> list[tuple[int, str, Decimal, OrderSide]]:
        sent = zip(world.book.requests, world.book.submitted, strict=False)
        return [
            (_EXCHANGE_ORDER + index, client_id, request.quantity, request.side)
            for index, (request, client_id) in enumerate(sent)
            if request.order_type is OrderType.MARKET
        ]

    def order_history(request: HistoryRequest) -> HistoryPage[OrderRecord]:
        if unreadable:
            raise AccountHistoryUnavailableError("allOrders timed out")
        rows = (
            ()
            if holds_nothing_yet
            else tuple(
                OrderRecord(
                    order=Order(
                        client_id,
                        SYMBOL,
                        side,
                        OrderType.MARKET,
                        quantity,
                        status=OrderStatus.FILLED,
                    ),
                    executed_quantity=quantity,
                    average_price=LAST_PRICE,
                    created_at=_AT,
                    exchange_order_id=exchange_id,
                )
                for exchange_id, client_id, quantity, side in market_orders()
            )
        )
        return HistoryPage(rows, 0, len(rows), (SYMBOL,))

    def trade_history(request: HistoryRequest) -> HistoryPage[TradeRecord]:
        if unreadable:
            raise AccountHistoryUnavailableError("myTrades timed out")
        rows = (
            ()
            if holds_nothing_yet
            else tuple(
                TradeRecord(
                    symbol=SYMBOL,
                    trade_id=_TRADE + exchange_id + part,
                    order_id=exchange_id,
                    side=side,
                    price=LAST_PRICE,
                    quantity=quantity / trades,
                    quote_quantity=LAST_PRICE * quantity / trades,
                    fee=Decimal(fee) / trades,
                    fee_asset=fee_asset,
                    time=_AT,
                )
                for exchange_id, _client_id, quantity, side in market_orders()
                for part in range(trades)
            )
        )
        return HistoryPage(rows, 0, len(rows), (SYMBOL,))

    world.activity.order_history = order_history  # type: ignore[method-assign]
    world.activity.trade_history = trade_history  # type: ignore[method-assign]


def _started(**history: object) -> tuple[GridWorld, Opened]:
    """A long position bot that ran its start; the stream has reported nothing."""
    world, _gate = a_position_world(opens_positions=True)
    _the_venue_shows_the_openings_it_filled(world, **history)  # type: ignore[arg-type]
    world.executor.start()
    assert world.state() is S.RUNNING
    market = [
        (r, c)
        for r, c in zip(world.book.requests, world.book.submitted, strict=False)
        if r.order_type is OrderType.MARKET
    ]
    assert market, "the plan opens a position"
    return world, Opened(market[0][1], sum((r.quantity for r, _ in market), Decimal(0)))


def test_the_saved_position_holds_the_opening_before_the_stream_reports_it() -> None:
    world, opened = _started()

    assert world.runtime().inventory == opened.quantity


def test_a_gap_reconcile_right_after_the_start_finds_no_disagreement(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world, _opened = _started()
    caplog.set_level(logging.WARNING)

    world.executor.facts.reconcile_after_gap()

    assert world.state() is S.RUNNING
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_the_stream_reporting_the_opening_late_does_not_count_it_twice() -> None:
    world, opened = _started()
    before = world.runtime().inventory

    world.executor.facts.on_fill(
        BotOrderFill(
            opened.client_order_id,
            OrderSide.BUY,
            LAST_PRICE,
            opened.quantity,
            Decimal(0),
            "USDT",
            trade_id=_TRADE + _EXCHANGE_ORDER,
        )
    )

    assert world.runtime().inventory == before


def test_every_trade_of_a_slice_is_booked_not_only_the_first() -> None:
    world, opened = _started(trades=2)

    assert world.runtime().inventory == opened.quantity


def test_a_history_that_does_not_hold_the_slice_yet_is_said_and_left_to_the_stream(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Binance's history can lag a market fill: nothing is booked, and the log says why."""
    capture = _Capture()
    logging.getLogger("App").addHandler(capture)
    try:
        world, opened = _started(holds_nothing_yet=True)
    finally:
        logging.getLogger("App").removeHandler(capture)

    assert world.state() is S.RUNNING
    assert world.runtime().inventory == 0
    assert any("not in the history yet" in line for line in capture.lines)
    world.executor.facts.on_fill(
        BotOrderFill(
            opened.client_order_id,
            OrderSide.BUY,
            LAST_PRICE,
            opened.quantity,
            Decimal(0),
            "USDT",
            trade_id=1,
        )
    )
    assert world.runtime().inventory == opened.quantity


def test_a_history_that_does_not_answer_warns_once_and_the_start_goes_on() -> None:
    capture = _Capture()
    logging.getLogger("App").addHandler(capture)
    try:
        world, _opened = _started(unreadable=True)
    finally:
        logging.getLogger("App").removeHandler(capture)

    assert world.state() is S.RUNNING
    assert world.runtime().inventory == 0
    assert [line for line in capture.lines if "did not answer" in line]


def test_a_spot_opening_is_booked_net_of_its_base_fee_as_the_stream_would() -> None:
    """The Spot opening names its slices too: the fee in the base asset leaves the inventory."""
    world = grid_world()
    _the_venue_shows_the_openings_it_filled(world, fee="0.002", fee_asset="BTC")
    world.executor.start()

    slices = sum(1 for r in world.book.requests if r.order_type is OrderType.MARKET)
    assert world.state() is S.RUNNING
    assert (
        world.runtime().inventory == world.book.bought_base - Decimal("0.002") * slices
    )


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.lines: list[str] = []
        logging.getLogger("App").setLevel(logging.DEBUG)

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())
