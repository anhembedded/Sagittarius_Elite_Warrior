"""`EPIC-039F` - the risk guard against the Futures fake exchange's own positions.

@details The runtime guard reads what the **exchange reports**: here `positionRisk`'s mark and
liquidation price, taken through the venue's real order client from the composed app over the
fake. A mark moving toward the fake's liquidation price walks the guard SAFE -> WARN ->
CRITICAL before the fake closes the position by force, and that forced close reaches the
owner's book as `POSITION_CHANGED_UNORDERED` - the divergence the bot's watch confirms and then
halts on (`FOREIGN_FILL`, unit-tested in `test_grid_risk_watch.py`)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.risk_guard_futures import (
    FuturesRiskGuard,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.risk_state import (
    RiskLevel,
    RiskSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
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
    OwnerBudgetRegistration,
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

D = Decimal
_TAG = "f1a2b3"
_OWNER = "bot-f1"
_THRESHOLDS = FuturesGridThresholds()
_GUARD = FuturesRiskGuard(_THRESHOLDS)
_BUDGET = OwnerBudget(
    20,
    D(100_000),
    timedelta(milliseconds=250),
    60,
    timedelta(minutes=1),
    futures=FuturesLimits(D(200_000), 10, D(20_000)),
)


def _open_a_long_at_ten_times(futures: FakeExchange, app: BootedFutures) -> None:
    book = futures.urls.futures_book
    assert (
        book.change_margin_type({"symbol": SYMBOL, "marginType": "ISOLATED"})[0] == 200
    )
    assert book.change_leverage({"symbol": SYMBOL, "leverage": "10"})[0] == 200
    app.scope.session_state.enable(set())
    ports = app.engine.context.container.resolve(IVenueTradingPorts).get(FUTURES)
    registration = OwnerBudgetRegistration(
        _OWNER, _TAG, SYMBOL, datetime.now(UTC) - timedelta(hours=1), _BUDGET
    )
    assert ports.trading_session.register_owner_budget(registration).registered
    app.client().place_order(
        Order(
            client_order_id=generate_client_order_id(_TAG),
            symbol=SYMBOL,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=D(1),
            price=D("64000.0"),
            time_in_force=TimeInForce.GTC,
        )
    )
    app.move_price(D(64000))


def _level(app: BootedFutures, previous: RiskLevel) -> RiskLevel:
    """What the guard says of the position `positionRisk` reports right now."""
    (position,) = app.client().get_positions(SYMBOL)
    now = datetime.now(UTC)
    snapshot = RiskSnapshot(
        position.position_amt,
        position.mark_price,
        position.liquidation_price,
        now,
    )
    return _GUARD.watch(snapshot, now, previous).level


def _mark_at_distance(liquidation: Decimal, distance: Decimal) -> Decimal:
    """The mark that puts a long `distance` of the mark above `liquidation`."""
    return (liquidation / (1 - distance)).quantize(D("0.1"))


def test_a_mark_moving_toward_the_exchanges_liquidation_price_walks_the_guard_to_critical(
    futures: FakeExchange,
) -> None:
    with booted_futures(futures) as app:
        _open_a_long_at_ten_times(futures, app)
        (position,) = app.client().get_positions(SYMBOL)
        assert position.liquidation_price is not None
        liquidation = D(position.liquidation_price)

        assert _level(app, RiskLevel.SAFE) is RiskLevel.SAFE

        app.move_price(_mark_at_distance(liquidation, D("0.04")))
        assert _level(app, RiskLevel.SAFE) is RiskLevel.WARN

        app.move_price(_mark_at_distance(liquidation, D("0.015")))
        assert _level(app, RiskLevel.WARN) is RiskLevel.CRITICAL


def test_the_forced_close_reaches_the_owner_as_a_position_it_did_not_order(
    futures: FakeExchange,
) -> None:
    with booted_futures(futures) as app:
        diverged: list[OwnerPositionDivergedEvent] = []
        app.engine.context.container.resolve(IEventBus).on(
            OwnerPositionDivergedEvent, diverged.append
        )
        _open_a_long_at_ten_times(futures, app)
        assert diverged == []

        app.move_price(D(50000))  # through the liquidation price

        assert app.client().get_positions(SYMBOL) == []
        (event,) = diverged
        assert (
            event.divergence.kind is PositionDivergenceKind.POSITION_CHANGED_UNORDERED
        )
        assert (event.divergence.derived, event.divergence.exchange) == (D(1), D(0))
