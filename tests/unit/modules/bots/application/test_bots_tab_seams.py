"""`EPIC-029F` — what the Bots tab reads from the bots module: every store write
announced, a run's account in the snapshot, the kinds by id, and the numbers
a panel judges a plan against."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IDomainEvent,
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot import (
    GetBotQuery,
    GetBotQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    GetPlannerMarketQuery,
    GetPlannerMarketQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
    ListBotsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.notifying_bot_store import (
    NotifyingBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    UnknownBotKindError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
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

from .helpers import seed
from .services.grid_world import LAST_PRICE, SYMBOL, terms_entry


@dataclass
class _RecordingPublisher(IEventPublisher):
    events: list[IDomainEvent] = field(default_factory=list)

    def publish(self, event: IDomainEvent) -> None:
        self.events.append(event)


def test_every_save_and_delete_announces_the_bot() -> None:
    publisher = _RecordingPublisher()
    store = NotifyingBotStore(FakeBotStore(), publisher)

    bot = seed(store, "a3f9c1", BotLifecycleState.DRAFT)  # type: ignore[arg-type]
    store.delete(bot.bot_id)

    assert [(e.bot_id, e.removed) for e in publisher.events] == [  # type: ignore[attr-defined]
        ("a3f9c1", False),
        ("a3f9c1", True),
    ]
    assert all(isinstance(e, BotChangedEvent) for e in publisher.events)


def test_a_failed_save_announces_nothing() -> None:
    publisher = _RecordingPublisher()
    store = NotifyingBotStore(FakeBotStore(), publisher)

    with pytest.raises(Exception):  # noqa: B017 -- any refusal of the inner store
        store.delete(BotId("a3f9c1"))

    assert publisher.events == []


def _with_runtime(store: FakeBotStore, runtime: dict[str, object]) -> None:
    bot = seed(store, "a3f9c1", BotLifecycleState.RUNNING)
    store.save(StoredBot(bot, runtime))  # type: ignore[arg-type]


def test_the_list_and_the_bot_carry_the_runs_account() -> None:
    store = FakeBotStore()
    runtime = GridRuntime(
        (),
        inventory=Decimal("0.5"),
        cost=Decimal(50),
        realised_profit=Decimal("12.5"),
        completed_cycles=3,
        reason=GridReason.SWITCH_OFF,
        reason_detail="trading turned off",
    )
    _with_runtime(store, dict(encode_runtime(runtime)))

    (listed,) = ListBotsQueryHandler(store).execute(ListBotsQuery()).bots
    one = GetBotQueryHandler(store).execute(GetBotQuery("a3f9c1"))

    assert one is not None
    for snapshot in (listed, one):
        progress = snapshot.progress
        assert progress is not None
        assert progress.realised_profit == Decimal("12.5")
        assert progress.completed_cycles == 3
        assert progress.inventory == Decimal("0.5")
        assert progress.average_cost == Decimal(100)
        assert (progress.reason, progress.reason_detail) == (
            "switch_off",
            "trading turned off",
        )


def test_a_bot_with_no_run_has_no_account() -> None:
    store = FakeBotStore()
    store.save(StoredBot(seed(store, "a3f9c1", BotLifecycleState.DRAFT), {}))

    (listed,) = ListBotsQueryHandler(store).execute(ListBotsQuery()).bots

    assert listed.progress is None


def test_an_unreadable_runtime_shows_no_account_and_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = FakeBotStore()
    _with_runtime(store, {"levels": "not a list"})

    with caplog.at_level(logging.WARNING, logger="App.Bots.Progress"):
        (listed,) = ListBotsQueryHandler(store).execute(ListBotsQuery()).bots

    assert listed.progress is None
    assert "a3f9c1" in caplog.text


def _grid_kind() -> GridKind:
    return GridKind(executor_factory=None, thresholds=GridThresholds())  # type: ignore[arg-type]


def test_the_catalog_finds_a_kind_by_its_id_and_refuses_an_unknown_one() -> None:
    grid = _grid_kind()
    catalog = BotKindCatalog([grid])

    assert catalog.kinds() == (grid,)
    assert catalog.kind("grid") is grid
    with pytest.raises(UnknownBotKindError):
        catalog.kind("dca")


def test_two_kinds_with_one_id_are_refused() -> None:
    with pytest.raises(ValueError, match="share an id"):
        BotKindCatalog([_grid_kind(), _grid_kind()])


def _planner(*, enabled: bool = True, days: int = 30) -> GetPlannerMarketQueryHandler:
    terms = FakeOrderEntryTerms(
        terms_entry(),
        books={
            SYMBOL: BestBidAsk(
                SYMBOL, LAST_PRICE, Decimal(1), LAST_PRICE + 2, Decimal(1)
            )
        },
    )
    bundles = (fake_venue_ports(TradingVenue.SPOT_TESTNET, order_entry_terms=terms),)
    ports = FakeVenueTradingPorts(*bundles) if enabled else _NoVenues(*bundles)
    klines = FakeHistoricalKlines()
    klines.seed(
        [
            candle(
                SYMBOL,
                minutes=day * 1440,
                interval=TimeFrame.ONE_DAY,
                close_price=99.0 + 2 * (day % 2),
            )
            for day in range(days)
        ],
        MarketType.SPOT,
    )
    return GetPlannerMarketQueryHandler(ports, DEFAULT_OWNER_BUDGET_CAPS, klines)


class _NoVenues(FakeVenueTradingPorts):
    def enabled(self) -> tuple[TradingVenue, ...]:
        return ()


def test_the_planner_reads_terms_price_and_daily_volatility() -> None:
    market = _planner().execute(
        GetPlannerMarketQuery(TradingVenue.SPOT_TESTNET, SYMBOL)
    )

    assert market.problem == ""
    assert market.terms is not None and market.terms.min_notional == Decimal(5)
    assert market.market is not None
    assert market.market.last_price == LAST_PRICE + 1
    # Every stored day spans 90-110 and closes inside it: a true range of 20.
    assert market.market.daily_atr == Decimal(20)
    assert market.atr_range is not None and market.bollinger is not None
    assert market.atr_range.lower < Decimal(100) < market.atr_range.upper
    assert market.bollinger.lower < market.bollinger.upper


def test_too_few_daily_candles_leave_the_suggestions_out() -> None:
    market = _planner(days=10).execute(
        GetPlannerMarketQuery(TradingVenue.SPOT_TESTNET, SYMBOL)
    )

    assert market.terms is not None
    assert market.market is not None and market.market.daily_atr is None
    assert (market.atr_range, market.bollinger) == (None, None)


def test_a_venue_that_is_not_enabled_is_named_as_the_problem() -> None:
    market = _planner(enabled=False).execute(
        GetPlannerMarketQuery(TradingVenue.SPOT_TESTNET, SYMBOL)
    )

    assert market.terms is None and market.market is None
    assert "spot" in market.problem.lower()


def test_an_unknown_symbol_is_named_as_the_problem() -> None:
    market = _planner().execute(
        GetPlannerMarketQuery(TradingVenue.SPOT_TESTNET, "NOPEUSDT")
    )

    assert market.terms is None
    assert "NOPEUSDT" in market.problem
