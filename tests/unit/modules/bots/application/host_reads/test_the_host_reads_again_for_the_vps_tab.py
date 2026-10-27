"""`EPIC-047H` - what the host reads again for the VPS tab is read at ROUTINE priority and recorded only when it happened.

The reader is the real `ExchangeBotReadRefresh` over a real store fake, the real memories and a venue that
answers what each test says; the priority is what `current_priority()` reports *inside* the read, which is
the value the venue's call policy gates on.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_timeframes import (
    DEFAULT_CHART_TIMEFRAMES,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.latest_exchange_reads import (
    LatestExchangeReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.latest_venue_reads import (
    LatestVenueReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills import (
    GetBotFillsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    GetPlannerMarketQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.host_reads.exchange_bot_read_refresh import (
    CANDLES_BACK,
    ExchangeBotReadRefresh,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_fills import (
    BotFill,
    BotFills,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeLoaded,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    VenueSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_read_refresh import (
    RefreshScope,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_facts import (
    IVenueFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.request_priority import (
    RequestPriority,
    current_priority,
    prioritised,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_market_metadata_provider import (
    FakeMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.host_facts.host_facts_world import (
    spot_facts,
)

VENUE = TradingVenue.SPOT_TESTNET
NOW = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)
TERMS = ExchangeTerms(
    Decimal("0.01"),
    Decimal("0.001"),
    Decimal(10),
    Decimal("0.001"),
    Decimal("0.001"),
    Decimal(5000),
    40,
)


class _Clock(IBotClock):
    def now(self) -> datetime:
        return NOW


class _Facts(IVenueFacts):
    def __init__(self) -> None:
        self.answer: VenueSnapshot = ExchangeLoaded(spot_facts())
        self.priorities: list[RequestPriority] = []

    def read(self, bot: Bot) -> VenueSnapshot:
        self.priorities.append(current_priority())
        return self.answer


class _Dispatcher(ICommandDispatcher):
    def __init__(self) -> None:
        self.market = PlannerMarket(TERMS, MarketView(Decimal(100)), None, None)
        self.fills = BotFills((BotFill(NOW, "BUY", Decimal(99), Decimal(1), "x"),))
        self.priorities: list[RequestPriority] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.priorities.append(current_priority())
        if handler_class is GetPlannerMarketQuery:
            return self.market
        assert handler_class is GetBotFillsQuery
        return self.fills


class _World:
    def __init__(self, state: BotLifecycleState = BotLifecycleState.RUNNING) -> None:
        self.store = FakeBotStore()
        self.facts = _Facts()
        self.dispatcher = _Dispatcher()
        self.provider = FakeMarketMetadataProvider()
        self.sync = FakeMarketDataSync()
        self.venue_reads = LatestVenueReads()
        self.exchange_reads = LatestExchangeReads()
        self.add("aaaaaa", state)
        self.refresh = ExchangeBotReadRefresh(
            self.store,
            self.facts,
            self.dispatcher,
            FakeVenueContexts(
                fake_venue_context(VENUE, metadata_provider=self.provider)
            ),
            _Clock(),
            self.venue_reads,
            self.exchange_reads,
            FakeMarketDataSources().serving(
                FakeMarketDataSources.ports(VENUE.market_data_venue, sync=self.sync)
            ),
        )

    def add(self, bot_id: str, state: BotLifecycleState) -> None:
        definition = BotDefinition("grid", "grid", VENUE, "BTCUSDT", {"lower": "1"})
        self.store.save(
            StoredBot(Bot(BotId(bot_id), definition, BotLifecycle(state), NOW))
        )


def test_every_read_goes_out_at_routine_priority() -> None:
    world = _World()

    for scope in RefreshScope:
        outcome = world.refresh.refresh("aaaaaa", scope)
        assert outcome.read_at is not None, scope

    assert world.facts.priorities == [RequestPriority.ROUTINE]
    assert world.dispatcher.priorities == [RequestPriority.ROUTINE] * 2


def test_inside_an_exit_guards_scope_the_refresh_reads_nothing_rather_than_spend_the_reserve() -> (
    None
):
    world = _World()

    with prioritised(RequestPriority.EXIT_GUARD):
        outcomes = [world.refresh.refresh("aaaaaa", scope) for scope in RefreshScope]
        outcomes.append(world.refresh.refresh_static(VENUE))

    assert [outcome.read_at for outcome in outcomes] == [None] * 5
    assert world.facts.priorities == []
    assert world.dispatcher.priorities == []
    assert world.provider.refreshes == 0
    assert world.sync.requests == []


def test_a_read_that_happened_is_recorded_with_the_time_it_was_read() -> None:
    world = _World()

    world.refresh.refresh("aaaaaa", RefreshScope.FACTS)
    world.refresh.refresh("aaaaaa", RefreshScope.PLANNER)
    world.refresh.refresh("aaaaaa", RefreshScope.FILLS)

    held = world.exchange_reads.latest()
    assert [read.bot_id for read in world.venue_reads.latest()] == ["aaaaaa"]
    assert (held.planner[0].bot_id, held.planner[0].read_at) == ("aaaaaa", NOW)
    assert (held.fills[0].bot_id, held.fills[0].read_at) == ("aaaaaa", NOW)


def test_a_failed_facts_read_leaves_the_last_good_snapshot_and_its_read_at() -> None:
    world = _World()
    world.refresh.refresh("aaaaaa", RefreshScope.FACTS)
    good = world.venue_reads.latest()

    world.facts.answer = ExchangeUnavailable("Binance said: key AKIA-SECRET timed out")
    outcome = world.refresh.refresh("aaaaaa", RefreshScope.FACTS)

    assert outcome.read_at is None
    assert world.venue_reads.latest() == good
    assert "AKIA" not in outcome.problem, "the exchange's words stay out of the outcome"


def test_a_planner_with_a_problem_and_refused_fills_are_not_recorded() -> None:
    world = _World()
    world.dispatcher.market = PlannerMarket(None, None, None, None, "no answer")
    world.dispatcher.fills = BotFills(problem="no answer")

    planner = world.refresh.refresh("aaaaaa", RefreshScope.PLANNER)
    fills = world.refresh.refresh("aaaaaa", RefreshScope.FILLS)

    assert planner.read_at is None
    assert fills.read_at is None
    assert world.exchange_reads.latest().planner == ()
    assert world.exchange_reads.latest().fills == ()


def test_a_bot_that_is_gone_is_a_failed_read_not_an_error() -> None:
    outcome = _World().refresh.refresh("nobody", RefreshScope.FACTS)

    assert outcome.read_at is None


@pytest.mark.parametrize(
    ("state", "exposure"),
    [
        (BotLifecycleState.RUNNING, True),
        (BotLifecycleState.PAUSED, True),
        (BotLifecycleState.HALTED, True),
        (BotLifecycleState.DRAFT, False),
        (BotLifecycleState.STOPPED, False),
    ],
    ids=lambda value: getattr(value, "value", str(value)),
)
def test_a_bot_not_at_rest_has_exposure_and_one_at_rest_is_asked_for_only(
    state: BotLifecycleState, *, exposure: bool
) -> None:
    (target,) = _World(state).refresh.targets()

    assert target.exposure is exposure


def test_a_deleted_bots_planner_and_fills_are_forgotten() -> None:
    world = _World()
    world.refresh.refresh("aaaaaa", RefreshScope.PLANNER)
    world.store.delete(BotId("aaaaaa"))

    world.refresh.targets()

    assert world.exchange_reads.latest().planner == ()


def test_the_static_info_is_read_again_and_the_bots_symbol_rules_are_kept() -> None:
    world = _World()
    world.provider.seed(
        [
            SymbolOrderMetadata(
                "BTCUSDT",
                "TRADING",
                Decimal("0.001"),
                Decimal("0.01"),
                Decimal(10),
                None,
                None,
                NOW,
            )
        ]
    )

    outcome = world.refresh.refresh_static(VENUE)

    assert outcome.read_at == NOW
    assert world.provider.refreshes == 1
    (rules,) = world.exchange_reads.latest().symbol_rules
    assert (rules.venue, rules.symbol, rules.read_at) == (VENUE, "BTCUSDT", NOW)


def test_the_candles_are_synced_for_each_pinned_timeframe_back_one_charts_window() -> (
    None
):
    world = _World()

    outcome = world.refresh.refresh("aaaaaa", RefreshScope.CANDLES)

    assert outcome.read_at == NOW
    asked = {request.interval.value: request for request in world.sync.requests}
    assert list(asked) == list(DEFAULT_CHART_TIMEFRAMES)
    five = asked["5m"]
    assert (five.symbols, five.market) == (("BTCUSDT",), VENUE.market_type)
    assert five.start_time == NOW - timedelta(minutes=5 * CANDLES_BACK)
    assert five.end_time is None


def test_a_sync_that_fails_is_a_failed_read_in_words_not_an_error() -> None:
    world = _World()

    def refused(_request: object) -> None:
        raise OSError("connection reset: key AKIA-SECRET")

    world.sync.sync = refused  # type: ignore[method-assign]
    outcome = world.refresh.refresh("aaaaaa", RefreshScope.CANDLES)

    assert outcome.read_at is None
    assert "AKIA" not in outcome.problem


def test_the_candles_are_read_inside_no_exit_guard_scope_either() -> None:
    world = _World()

    with prioritised(RequestPriority.EXIT_GUARD):
        outcome = world.refresh.refresh("aaaaaa", RefreshScope.CANDLES)

    assert outcome.read_at is None
    assert world.sync.requests == []
