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


def _the_venue_shows_the_openings_it_filled(world: GridWorld) -> None:
    """The venue's order and trade history, read from what the book was asked to send: every
    market order is FILLED at the last price, one trade each, the way a market order fills."""

    def market_orders() -> list[tuple[int, str, Decimal, OrderSide]]:
        sent = zip(world.book.requests, world.book.submitted, strict=False)
        return [
            (_EXCHANGE_ORDER + index, client_id, request.quantity, request.side)
            for index, (request, client_id) in enumerate(sent)
            if request.order_type is OrderType.MARKET
        ]

    def order_history(request: HistoryRequest) -> HistoryPage[OrderRecord]:
        rows = tuple(
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
        return HistoryPage(rows, 0, len(rows), (SYMBOL,))

    def trade_history(request: HistoryRequest) -> HistoryPage[TradeRecord]:
        rows = tuple(
            TradeRecord(
                symbol=SYMBOL,
                trade_id=_TRADE + exchange_id,
                order_id=exchange_id,
                side=side,
                price=LAST_PRICE,
                quantity=quantity,
                quote_quantity=LAST_PRICE * quantity,
                fee=Decimal(0),
                fee_asset="USDT",
                time=_AT,
            )
            for exchange_id, _client_id, quantity, side in market_orders()
        )
        return HistoryPage(rows, 0, len(rows), (SYMBOL,))

    world.activity.order_history = order_history  # type: ignore[method-assign]
    world.activity.trade_history = trade_history  # type: ignore[method-assign]


def _started() -> tuple[GridWorld, Opened]:
    """A long position bot that ran its start; the stream has reported nothing."""
    world, _gate = a_position_world(opens_positions=True)
    _the_venue_shows_the_openings_it_filled(world)
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
