"""`EPIC-028I` — an entry's TP/SL is placed when its own venue reports it
filled, on the opposite side and reduce-only; an entry that ends any other
way is not protected, and the desk is told either way."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.protective_levels import (
    ProtectiveLevels,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.protective_order_follower import (
    ProtectiveOrderFollower,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_feed import OrderFeed
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)

from .account_tabs_fixtures import order
from .order_entry_fixtures import InlineThreadManager
from .order_entry_presenter_fixtures import placed

_FUTURES = TradingVenue.FUTURES_TESTNET
_LEVELS = ProtectiveLevels(Decimal(63000), Decimal(58000))


class _Desk:
    def __init__(self, qapp) -> None:
        self.qapp = qapp
        self.bus = MemoryEventBus()
        self.submission = FakeOrderSubmission()
        self.submission.submit_answers(placed(order()))
        self.reports: list[tuple[str, bool]] = []
        self.follower = ProtectiveOrderFollower(
            self.submission,
            OrderFeed(self.bus, _FUTURES),
            InlineThreadManager(),
            lambda text, failed: self.reports.append((text, failed)),
        )
        self.entry = order("BTCUSDT", "SEW-entry")

    def report(self, status: OrderStatus, venue: TradingVenue = _FUTURES) -> None:
        self.bus.emit(
            OrderFilledEvent(
                order=replace(self.entry, status=status),
                fill_price=Decimal(60010),
                fill_quantity=self.entry.quantity,
                venue=venue,
            )
        )
        self.qapp.processEvents()


def test_a_filled_entry_is_protected_on_the_opposite_side(qapp) -> None:
    desk = _Desk(qapp)
    desk.follower.expect(desk.entry, _LEVELS)

    desk.report(OrderStatus.FILLED)

    take_profit, stop_loss = desk.submission.submitted_live
    assert (take_profit.order_type, stop_loss.order_type) == (
        OrderType.TAKE_PROFIT_MARKET,
        OrderType.STOP_MARKET,
    )
    for sent in (take_profit, stop_loss):
        assert sent.side is OrderSide.SELL
        assert sent.reduce_only is True
        assert sent.purpose is OrderPurpose.PROTECTIVE
        assert sent.quantity == desk.entry.quantity
        assert sent.last_price == Decimal(60010)
    assert desk.follower.waiting == ()
    assert desk.reports == [
        ("Take-profit placed at 63000. Stop-loss placed at 58000.", False)
    ]


def test_nothing_is_placed_before_the_fill(qapp) -> None:
    desk = _Desk(qapp)
    desk.follower.expect(desk.entry, _LEVELS)

    desk.report(OrderStatus.NEW)
    desk.report(OrderStatus.PARTIALLY_FILLED)
    desk.report(OrderStatus.FILLED, venue=TradingVenue.SPOT_TESTNET)

    assert desk.submission.submitted_live == []
    assert desk.follower.waiting == ("SEW-entry",)


def test_an_entry_that_ends_unfilled_is_forgotten_and_said(qapp) -> None:
    desk = _Desk(qapp)
    desk.follower.expect(desk.entry, _LEVELS)

    desk.report(OrderStatus.CANCELED)

    assert desk.submission.submitted_live == []
    assert desk.follower.waiting == ()
    assert desk.reports == [("The entry ended canceled; no TP/SL was placed.", True)]


def test_a_refused_protective_order_is_named(qapp) -> None:
    desk = _Desk(qapp)
    desk.submission.submit_answers(
        ExecuteOrderResult(ExecuteOrderSafetyGate.TRADING_SWITCH_OFF, None, (), None)
    )
    desk.follower.expect(desk.entry, ProtectiveLevels(None, Decimal(58000)))

    desk.report(OrderStatus.FILLED)

    ((text, failed),) = desk.reports
    assert failed
    assert text.startswith("Stop-loss not placed:")
