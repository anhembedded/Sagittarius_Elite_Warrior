"""`EPIC-035V` (L7) — the planner counts the orders already open on the symbol.

They share the exchange's open-order limit with the plan's, and the bot neither
placed nor will manage them. The count reaches the Design step's checks through
`MarketView.foreign_open_orders`; a read that fails leaves it unread, never zero.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    GetPlannerMarketQuery,
    GetPlannerMarketQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_activity import (
    FakeAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    LAST_PRICE,
    SYMBOL,
    terms_entry,
)

_VENUE = TradingVenue.SPOT_TESTNET


def _order(symbol: str, client_order_id: str) -> Order:
    return Order(
        client_order_id=client_order_id,
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal(1),
        price=Decimal(100),
    )


class _OfflineActivity(FakeAccountActivity):
    def open_orders(self) -> tuple[Order, ...]:
        raise ConnectionError("the exchange did not answer")


def _planner(activity: FakeAccountActivity) -> GetPlannerMarketQueryHandler:
    terms = FakeOrderEntryTerms(
        terms_entry(),
        books={
            SYMBOL: BestBidAsk(SYMBOL, LAST_PRICE, Decimal(1), LAST_PRICE, Decimal(1))
        },
    )
    ports = FakeVenueTradingPorts(
        fake_venue_ports(_VENUE, order_entry_terms=terms, account_activity=activity)
    )
    return GetPlannerMarketQueryHandler(
        ports, DEFAULT_OWNER_BUDGET_CAPS, FakeHistoricalKlines()
    )


def _foreign(activity: FakeAccountActivity) -> int | None:
    market = _planner(activity).execute(GetPlannerMarketQuery(_VENUE, SYMBOL)).market
    assert market is not None
    return market.foreign_open_orders


def test_only_the_orders_on_the_symbol_are_counted() -> None:
    activity = FakeAccountActivity()
    activity.holding_open_orders(
        [_order(SYMBOL, "manual-1"), _order(SYMBOL, "manual-2"), _order("ETHUSDT", "x")]
    )

    assert _foreign(activity) == 2


def test_a_symbol_with_no_open_order_counts_zero() -> None:
    assert _foreign(FakeAccountActivity()) == 0


def test_a_read_that_fails_leaves_the_count_unread_and_the_plan_judgeable() -> None:
    assert _foreign(_OfflineActivity()) is None
