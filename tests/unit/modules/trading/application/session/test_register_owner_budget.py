"""`EPIC-029` ADR D6 — registering an owner budget.

@details The handler is real, over a real `TradingSessionState`; the venue's
history is `FakeAccountHistoryReader` (the port's fake) and its open orders
come from a `Mock(spec=ITradingClientFactory)`, trading's own port.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_inventory_deriver import (
    OwnerInventoryDeriver,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.register_owner_budget import (
    RegisterOwnerBudgetCommand,
    RegisterOwnerBudgetCommandHandler,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client_factory import (
    ITradingClientFactory,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
    OwnerBudget,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistration,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_history_reader import (
    FakeAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_owner_inventory_checkpoints import (
    FakeOwnerInventoryCheckpoints,
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
_RUN = _NOW - timedelta(days=1)
_REGISTRATION = OwnerBudgetRegistration(
    owner_id="bot-1",
    tag="a3f9c1",
    symbol="BTCUSDT",
    run_started_at=_RUN,
    budget=OwnerBudget(
        10, Decimal(1000), timedelta(milliseconds=250), 60, timedelta(minutes=1)
    ),
)


def _bought(exchange_id: int = 1) -> tuple[OrderRecord, TradeRecord]:
    order = Order(
        client_order_id=ClientOrderId(f"SEW-a3f9c1-{exchange_id:010x}"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.002"),
        status=OrderStatus.FILLED,
        price=Decimal(50000),
    )
    record = OrderRecord(
        order, Decimal("0.002"), Decimal(50000), _RUN + timedelta(hours=1), exchange_id
    )
    trade = TradeRecord(
        symbol="BTCUSDT",
        trade_id=100 + exchange_id,
        order_id=exchange_id,
        side=OrderSide.BUY,
        price=Decimal(50000),
        quantity=Decimal("0.002"),
        quote_quantity=Decimal(100),
        fee=Decimal("0.000002"),
        fee_asset="BTC",
        time=_RUN + timedelta(hours=2),
    )
    return record, trade


def _resting(
    number: int, side: OrderSide = OrderSide.SELL, tag: str = "a3f9c1"
) -> Order:
    return Order(
        client_order_id=ClientOrderId(f"SEW-{tag}-{number:010x}"),
        symbol="BTCUSDT",
        side=side,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.001"),
        price=Decimal(51000),
    )


def _factory(
    open_orders: list[Order] | None = None, error: Exception | None = None
) -> Mock:
    """The venue's open orders, or the failure reading them."""
    factory = Mock(spec=ITradingClientFactory)
    read = factory.create.return_value.get_open_orders
    read.return_value = open_orders or []
    read.side_effect = error
    return factory


def _handler(
    state: TradingSessionState,
    history: object | None = None,
    factory: Mock | None = None,
    venue: TradingVenue = _SPOT,
) -> RegisterOwnerBudgetCommandHandler:
    context = venue_context(
        venue,
        client_factory=factory or _factory(),
        history_reader=history or FakeAccountHistoryReader(now=_NOW),  # type: ignore[arg-type]
    )
    return RegisterOwnerBudgetCommandHandler(
        single_venue_scopes(context, state),
        OwnerInventoryDeriver(FakeOwnerInventoryCheckpoints()),
        DEFAULT_OWNER_BUDGET_CAPS,
    )


def _enabled() -> TradingSessionState:
    state = TradingSessionState()
    state.enable(set())
    return state


def _register(handler: RegisterOwnerBudgetCommandHandler, **changes: object):
    registration = replace(_REGISTRATION, **changes)  # type: ignore[arg-type]
    return handler.execute(RegisterOwnerBudgetCommand(registration, venue=_SPOT))


def test_the_inventory_is_derived_from_the_venue() -> None:
    order, trade = _bought()
    state = _enabled()
    history = FakeAccountHistoryReader([order], [trade], now=_NOW)

    result = _register(_handler(state, history))

    assert result.registered
    assert result.inventory == OwnerInventory(Decimal("0.001998"), Decimal(100))
    assert state.owner_books.holder_of("a3f9c1") == "bot-1"


def test_resting_orders_of_the_owner_are_adopted_and_others_ignored() -> None:
    state = _enabled()
    handler = _handler(
        state,
        factory=_factory([_resting(1), _resting(2), _resting(3, tag="b00000")]),
    )

    _register(handler)

    shares = state.owner_books.shares()
    assert [share.tag for share in shares] == ["a3f9c1"]
    facts = state.owner_books.facts("a3f9c1", "bot-1", _resting(9), _NOW)
    assert facts is not None
    assert (facts.open_order_count, facts.open_sell_quantity) == (2, Decimal("0.002"))
    assert facts.orders_in_window == 0


def test_a_budget_is_refused_on_a_futures_venue() -> None:
    state = _enabled()
    handler = _handler(state, venue=TradingVenue.FUTURES_TESTNET)

    result = handler.execute(
        RegisterOwnerBudgetCommand(_REGISTRATION, venue=TradingVenue.FUTURES_TESTNET)
    )

    assert result.refusal is OwnerBudgetRefusal.VENUE_NOT_SPOT


def test_a_budget_is_refused_while_trading_is_off() -> None:
    result = _register(_handler(TradingSessionState()))
    assert result.refusal is OwnerBudgetRefusal.TRADING_SWITCH_OFF


def test_a_symbol_not_quoted_in_usdt_is_refused() -> None:
    result = _register(_handler(_enabled()), symbol="ETHBTC")
    assert result.refusal is OwnerBudgetRefusal.SYMBOL_NOT_SUPPORTED


def test_a_budget_above_a_global_cap_is_refused_naming_it() -> None:
    too_many = replace(_REGISTRATION.budget, max_open_orders=101)
    result = _register(_handler(_enabled()), budget=too_many)
    assert (result.refusal, result.exceeded_cap) == (
        OwnerBudgetRefusal.ABOVE_GLOBAL_CAP,
        "max_open_orders",
    )


def test_a_tag_another_owner_holds_is_refused() -> None:
    state = _enabled()
    _register(_handler(state))

    result = _register(_handler(state), owner_id="bot-2")

    assert result.refusal is OwnerBudgetRefusal.TAG_HELD_BY_ANOTHER_OWNER
    assert state.owner_books.holder_of("a3f9c1") == "bot-1"


def test_a_run_past_the_history_is_refused() -> None:
    result = _register(_handler(_enabled()), run_started_at=_NOW - timedelta(days=31))
    assert result.refusal is OwnerBudgetRefusal.INVENTORY_BEYOND_LOOKBACK


class _SilentHistory(FakeAccountHistoryReader):
    def order_history(self, symbol: str, since: datetime) -> tuple[OrderRecord, ...]:
        raise AccountHistoryUnavailableError("orders: timeout")


def test_a_venue_that_does_not_answer_is_refused() -> None:
    result = _register(_handler(_enabled(), _SilentHistory(now=_NOW)))
    assert result.refusal is OwnerBudgetRefusal.INVENTORY_UNAVAILABLE


def test_open_orders_that_cannot_be_read_are_refused() -> None:
    state = _enabled()
    handler = _handler(state, factory=_factory(error=ConnectionError("down")))

    assert _register(handler).refusal is OwnerBudgetRefusal.INVENTORY_UNAVAILABLE
    assert state.owner_books.holder_of("a3f9c1") is None


class _DisablingHistory(FakeAccountHistoryReader):
    """Trading is switched off while the history is being read."""

    def __init__(self, state: TradingSessionState) -> None:
        super().__init__(now=_NOW)
        self._state = state

    def order_history(self, symbol: str, since: datetime) -> tuple[OrderRecord, ...]:
        self._state.disable()
        return super().order_history(symbol, since)


def test_a_disable_during_the_reads_wins_and_installs_nothing() -> None:
    state = _enabled()

    result = _register(_handler(state, _DisablingHistory(state)))

    assert result.refusal is OwnerBudgetRefusal.TRADING_SWITCH_OFF
    assert state.owner_books.holder_of("a3f9c1") is None
