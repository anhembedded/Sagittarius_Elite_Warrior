"""`EPIC-039D` - a Futures owner's position, derived from the exchange's evidence
and checked against it, on the composed app over the fake Futures exchange.

@details Nothing here is a hand-written port: the owner registers through the venue's
own trading session, its orders go through the real order client, the fake matches
them, and the fills reach the books through the user-data stream's own handler
(`BootedFutures.deliver`). The fake's `positionRisk` is the oracle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.owner_position_diverged_event import (
    OwnerPositionDivergedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    FuturesLimits,
    OwnerBudget,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistration,
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    PositionDivergenceKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus

from .futures_fake_exchange import FUTURES, SYMBOL, BootedFutures, booted_futures
from .grid_fake_exchange import FakeExchange

_TAG = "f0a1b2"
_OWNER = "bot-f0"
_RUN_STARTED = datetime.now(UTC) - timedelta(hours=1)
_BUDGET = OwnerBudget(
    20,
    Decimal(100_000),
    timedelta(milliseconds=250),
    60,
    timedelta(minutes=1),
    futures=FuturesLimits(Decimal(200_000), 10, Decimal(20_000)),
)


def _registration(tag: str = _TAG) -> OwnerBudgetRegistration:
    return OwnerBudgetRegistration(_OWNER, tag, SYMBOL, _RUN_STARTED, _BUDGET)


def _register(app: BootedFutures, tag: str = _TAG) -> OwnerBudgetRegistrationResult:
    app.scope.session_state.enable(set())
    ports = app.engine.context.container.resolve(IVenueTradingPorts).get(FUTURES)
    return ports.trading_session.register_owner_budget(_registration(tag))


def _limit(
    app: BootedFutures,
    side: OrderSide,
    price: str,
    quantity: str,
    *,
    tag: str | None = _TAG,
    reduce_only: bool = False,
) -> Order:
    return app.client().place_order(
        Order(
            client_order_id=generate_client_order_id(tag),
            symbol=SYMBOL,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=Decimal(quantity),
            price=Decimal(price),
            time_in_force=TimeInForce.GTC,
            reduce_only=reduce_only,
        )
    )


def _market_by_hand(app: BootedFutures, side: OrderSide, quantity: str) -> None:
    """A position the bot did not order: an untagged market order, as the user's own."""
    app.client().place_order(
        Order(
            client_order_id=ClientOrderId(generate_client_order_id()),
            symbol=SYMBOL,
            side=side,
            order_type=OrderType.MARKET,
            quantity=Decimal(quantity),
        )
    )
    app.deliver()


def _book_position(app: BootedFutures) -> Decimal:
    position = app.scope.session_state.owner_books.position_of(_TAG, _OWNER)
    assert position is not None
    return position.quantity


def _exchange_position(app: BootedFutures) -> Decimal:
    return sum((p.position_amt for p in app.client().get_positions(SYMBOL)), Decimal(0))


def test_the_derived_position_equals_the_fakes_position_risk_after_a_ladder_of_fills(
    futures: FakeExchange,
) -> None:
    with booted_futures(futures) as app:
        _limit(app, OrderSide.BUY, "63000.0", "0.010")
        app.move_price(Decimal(63000))
        _limit(app, OrderSide.BUY, "62000.0", "0.020")
        app.move_price(Decimal(62000))
        _limit(app, OrderSide.SELL, "64000.0", "0.015", reduce_only=True)
        app.move_price(Decimal(64000))
        assert _exchange_position(app) == Decimal("0.015")

        result = _register(app)

        assert result.registered and result.divergence is None
        assert result.position is not None
        assert result.position.quantity == _exchange_position(app)
        assert result.position.average_entry == (
            (Decimal("0.010") * 63000 + Decimal("0.020") * 62000) / Decimal("0.030")
        )


def test_a_fill_after_registration_moves_the_book_with_the_exchange(
    futures: FakeExchange,
) -> None:
    with booted_futures(futures) as app:
        assert _register(app).registered
        _limit(app, OrderSide.BUY, "63000.0", "0.010")

        app.move_price(Decimal(63000))

        assert _book_position(app) == _exchange_position(app) == Decimal("0.010")


def test_a_position_older_than_the_run_is_foreign_and_refuses_registration(
    futures: FakeExchange,
) -> None:
    with booted_futures(futures) as app:
        _market_by_hand(app, OrderSide.BUY, "0.050")

        result = _register(app)

        assert result.refusal is OwnerBudgetRefusal.FOREIGN_POSITION
        assert result.foreign_position is not None
        assert result.foreign_position.describe() == (
            f"{SYMBOL} already has a long position of 0.05 that this bot did not "
            "open; close it or pick another symbol"
        )
        assert app.scope.session_state.owner_books.holder_of(_TAG) is None


def test_a_mismatch_with_position_risk_is_reported_not_overwritten(
    futures: FakeExchange,
) -> None:
    with booted_futures(futures) as app:
        _limit(app, OrderSide.BUY, "63000.0", "0.010")
        app.move_price(Decimal(63000))
        _market_by_hand(app, OrderSide.BUY, "0.040")  # the user adds to it by hand

        result = _register(app)

        assert result.registered
        assert result.divergence is not None
        assert result.divergence.kind is PositionDivergenceKind.POSITION_MISMATCH
        assert (result.divergence.derived, result.divergence.exchange) == (
            Decimal("0.010"),
            Decimal("0.050"),
        )
        assert _book_position(app) == Decimal("0.010")


def test_a_fill_without_a_tag_changes_the_position_and_is_reported_as_unordered(
    futures: FakeExchange,
) -> None:
    with booted_futures(futures) as app:
        diverged: list[OwnerPositionDivergedEvent] = []
        app.engine.context.container.resolve(IEventBus).on(
            OwnerPositionDivergedEvent, diverged.append
        )
        _limit(app, OrderSide.BUY, "63000.0", "0.010")
        app.move_price(Decimal(63000))
        assert _register(app).divergence is None

        _market_by_hand(app, OrderSide.SELL, "0.010")  # a close the bot never ordered
        app.deliver()

        assert _book_position(app) == Decimal("0.010")
        (event,) = diverged
        assert (
            event.divergence.kind is PositionDivergenceKind.POSITION_CHANGED_UNORDERED
        )
        assert (event.divergence.derived, event.divergence.exchange) == (
            Decimal("0.010"),
            Decimal(0),
        )


def test_a_burst_of_the_owners_own_fills_is_no_divergence(
    futures: FakeExchange,
) -> None:
    """The book is compared with the amount each `ACCOUNT_UPDATE` reports, not with a
    later read that already holds the next fill of the burst (review of PR #485)."""
    with booted_futures(futures) as app:
        diverged: list[OwnerPositionDivergedEvent] = []
        app.engine.context.container.resolve(IEventBus).on(
            OwnerPositionDivergedEvent, diverged.append
        )
        assert _register(app).registered
        _limit(app, OrderSide.BUY, "63000.0", "0.010")
        _limit(app, OrderSide.BUY, "62500.0", "0.020")

        app.move_price(Decimal(62000))  # crosses both levels at once

        assert _exchange_position(app) == Decimal("0.030")
        assert _book_position(app) == Decimal("0.030")
        assert diverged == []
