"""`EPIC-029F` — the detail panel's orders (from the runtime) and fills (from
the venue's order history, by the bot's tag)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills import (
    GetBotFillsQuery,
    GetBotFillsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
    ListBotsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
    LevelOrder,
    RuntimeLevel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HISTORY_PAGE_SIZE,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_activity import (
    FakeAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .helpers import seed

_AT = datetime(2026, 10, 1, 12, tzinfo=UTC)


def test_the_list_carries_each_resting_order_lowest_level_first() -> None:
    store = FakeBotStore()
    bot = seed(store, "a3f9c1", BotLifecycleState.RUNNING)
    buy = LevelOrder("SEW-a3f9c1-0000000001", OrderSide.BUY, Decimal(99), Decimal(1))
    sell = LevelOrder(
        "SEW-a3f9c1-0000000002",
        OrderSide.SELL,
        Decimal(101),
        Decimal(1),
        executed=Decimal("0.4"),
    )
    runtime = GridRuntime(
        (
            RuntimeLevel(0, Decimal(99), Decimal(1), LevelState.RESTING, buy),
            RuntimeLevel(1, Decimal(100), Decimal(1)),
            RuntimeLevel(2, Decimal(101), Decimal(1), LevelState.PARTIAL, sell),
        )
    )
    store.save(StoredBot(bot, dict(encode_runtime(runtime))))

    (listed,) = ListBotsQueryHandler(store).execute(ListBotsQuery()).bots

    assert listed.progress is not None
    assert [
        (line.level, line.side, line.price, line.executed)
        for line in listed.progress.orders
    ] == [
        (0, "BUY", Decimal(99), Decimal(0)),
        (2, "SELL", Decimal(101), Decimal("0.4")),
    ]


def _record(
    tag: str | None, executed: str, side: OrderSide = OrderSide.BUY
) -> OrderRecord:
    return OrderRecord(
        order=Order(
            generate_client_order_id(tag),
            "BTCUSDT",
            side,
            OrderType.LIMIT,
            Decimal(1),
            status=OrderStatus.FILLED,
            price=Decimal(100),
            order_time=_AT,
        ),
        executed_quantity=Decimal(executed),
        average_price=Decimal(100) if Decimal(executed) > 0 else None,
        created_at=_AT,
        exchange_order_id=1,
    )


def _handler(
    records: list[OrderRecord], *, enabled: bool = True
) -> tuple[GetBotFillsQueryHandler, FakeAccountActivity, FakeBotStore]:
    store = FakeBotStore()
    seed(store, "a3f9c1", BotLifecycleState.RUNNING)
    activity = FakeAccountActivity()
    activity.holding_history(orders=records)
    bundle = fake_venue_ports(TradingVenue.SPOT_TESTNET, account_activity=activity)
    ports = FakeVenueTradingPorts(bundle) if enabled else _NoVenues(bundle)
    return GetBotFillsQueryHandler(store, ports), activity, store


class _NoVenues(FakeVenueTradingPorts):
    def enabled(self) -> tuple[TradingVenue, ...]:
        return ()


def test_only_the_bots_executed_orders_are_its_fills() -> None:
    handler, _, _ = _handler(
        [
            _record("a3f9c1", "1", OrderSide.SELL),
            _record("b00000", "1"),  # another bot
            _record(None, "1"),  # a manual order
            _record("a3f9c1", "0"),  # cancelled before any fill
            _record("a3f9c1", "0.25"),
        ]
    )

    fills = handler.execute(GetBotFillsQuery("a3f9c1"))

    assert fills.problem == ""
    assert [(fill.side, fill.quantity) for fill in fills.fills] == [
        ("SELL", Decimal(1)),
        ("BUY", Decimal("0.25")),
    ]
    assert all(fill.client_order_id.startswith("SEW-a3f9c1-") for fill in fills.fills)


def test_the_read_starts_at_the_bots_creation_before_any_run() -> None:
    handler, activity, store = _handler([])

    handler.execute(GetBotFillsQuery("a3f9c1"))

    created = store.load_all().bots[0].bot.created_at
    assert [(r.symbol, r.since, r.page) for r in activity.order_requests] == [
        ("BTCUSDT", created, 0)
    ]


def test_a_history_longer_than_the_scan_says_it_was_cut() -> None:
    handler, activity, _ = _handler(
        [_record("a3f9c1", "1") for _ in range(HISTORY_PAGE_SIZE * 5)]
    )

    fills = handler.execute(GetBotFillsQuery("a3f9c1"))

    assert fills.truncated
    assert [r.page for r in activity.order_requests] == [0, 1, 2, 3]


def test_a_history_that_ends_on_a_page_boundary_is_not_cut() -> None:
    handler, activity, _ = _handler(
        [_record("a3f9c1", "1") for _ in range(HISTORY_PAGE_SIZE * 2)]
    )

    fills = handler.execute(GetBotFillsQuery("a3f9c1"))

    assert not fills.truncated
    assert len(fills.fills) == HISTORY_PAGE_SIZE * 2
    assert [r.page for r in activity.order_requests] == [0, 1]


def test_a_disabled_venue_and_a_deleted_bot_are_named_as_the_problem() -> None:
    disabled, _, _ = _handler([], enabled=False)
    gone, _, _ = _handler([])

    assert "spot_testnet" in disabled.execute(GetBotFillsQuery("a3f9c1")).problem
    assert "no longer exists" in gone.execute(GetBotFillsQuery("zzzzzz")).problem
