"""`EPIC-028I` — an entry's TP/SL is placed when its own venue reports it
filled, on the opposite side and reduce-only, even when the fill was
reported before the desk asked; an entry cancelled after a partial fill is
protected for what filled; one that ends with nothing filled is not; the
desk is told each time.

@details Events are the ones the streams really emit: `OrderFilledEvent`
for each trade, `OrderEndedEvent` for an order over unfilled (the PR #307
review: an `OrderFilledEvent` with `CANCELED` is never produced)."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_ended_event import (
    OrderEndedEvent,
)
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

    def report(
        self,
        status: OrderStatus,
        venue: TradingVenue = _FUTURES,
        quantity: Decimal | None = None,
        client_order_id: str = "SEW-entry",
    ) -> None:
        """One trade of the entry (or of `client_order_id`), as the stream
        reports it."""
        self.bus.emit(
            OrderFilledEvent(
                order=replace(
                    self.entry,
                    status=status,
                    client_order_id=ClientOrderId(client_order_id),
                ),
                fill_price=Decimal(60010),
                fill_quantity=quantity or self.entry.quantity,
                venue=venue,
            )
        )
        self.qapp.processEvents()

    def end(self, status: OrderStatus) -> None:
        """The entry over without having filled whole."""
        self.bus.emit(
            OrderEndedEvent(order=replace(self.entry, status=status), venue=_FUTURES)
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


def test_a_fill_reported_before_the_desk_asks_is_still_protected(qapp) -> None:
    """The PR #307 review: the stream's fill and the submit's answer reach
    the UI thread separately, and a market order often fills first."""
    desk = _Desk(qapp)

    desk.report(OrderStatus.FILLED)
    desk.follower.expect(desk.entry, _LEVELS)

    assert len(desk.submission.submitted_live) == 2
    assert desk.follower.waiting == ()


def test_an_early_fill_outlives_other_orders_reported_meanwhile(qapp) -> None:
    desk = _Desk(qapp)
    desk.report(OrderStatus.FILLED)
    for n in range(10):
        desk.report(OrderStatus.FILLED, client_order_id=f"SEW-other-{n}")

    desk.follower.expect(desk.entry, _LEVELS)

    assert len(desk.submission.submitted_live) == 2


def test_nothing_is_placed_before_the_fill(qapp) -> None:
    desk = _Desk(qapp)
    desk.follower.expect(desk.entry, _LEVELS)

    desk.report(OrderStatus.PARTIALLY_FILLED, quantity=Decimal("0.004"))
    desk.report(OrderStatus.FILLED, venue=TradingVenue.SPOT_TESTNET)

    assert desk.submission.submitted_live == []
    assert desk.follower.waiting == ("SEW-entry",)


def test_an_entry_that_ends_with_nothing_filled_is_forgotten_and_said(qapp) -> None:
    desk = _Desk(qapp)
    desk.follower.expect(desk.entry, _LEVELS)

    desk.end(OrderStatus.CANCELED)

    assert desk.submission.submitted_live == []
    assert desk.follower.waiting == ()
    assert desk.reports == [("The entry ended canceled; no TP/SL was placed.", True)]


def test_an_entry_cancelled_after_a_partial_fill_protects_what_filled(qapp) -> None:
    desk = _Desk(qapp)
    desk.follower.expect(desk.entry, _LEVELS)

    desk.report(OrderStatus.PARTIALLY_FILLED, quantity=Decimal("0.003"))
    desk.report(OrderStatus.PARTIALLY_FILLED, quantity=Decimal("0.001"))
    desk.end(OrderStatus.CANCELED)

    assert [sent.quantity for sent in desk.submission.submitted_live] == [
        Decimal("0.004"),
        Decimal("0.004"),
    ]
    ((text, failed),) = desk.reports
    assert not failed
    assert text.startswith(
        "The entry ended canceled after 0.004 of 0.01 filled; TP/SL protect 0.004."
    )


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
