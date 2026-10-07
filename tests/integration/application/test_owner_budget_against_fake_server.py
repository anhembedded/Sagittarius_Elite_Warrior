"""`EPIC-029A` — an owner budget end to end against the fake exchange.

@details Every trading piece is real: the Spot adapters over `python-binance`
to the fake server, `ExecuteOrderCommandHandler`, the registration handler
with the real `SpotHistoryReader`, Emergency Stop, and the venue's emission
path (`SpotUserDataStream` → `VenueEventEmitter`). The fake has no websocket,
so each test drains its executionReports and hands them to the stream, the
way the stream's own tests do. The caps allow a zero spacing here so the
ladder needs no wait (`testing-rule.md` §2, no sleeps); the spacing check
has its own unit tests.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

from binance.client import Client
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.listed_symbols import (
    ListedSymbols,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_account_reader import (
    SpotAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_book_ticker_reader import (
    SpotBookTickerReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_history_reader import (
    SpotHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_metadata_provider import (
    SpotMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client_factory import (
    SpotTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_user_data_stream import (
    SpotUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_event_emitter import (
    VenueEventEmitter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.handler import (
    ExecuteOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.handler import (
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.query import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_inventory_deriver import (
    OwnerInventoryDeriver,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop import (
    EmergencyStopCommand,
    EmergencyStopCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.register_owner_budget import (
    RegisterOwnerBudgetCommand,
    RegisterOwnerBudgetCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.session_readiness import (
    SessionReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_ended_event import (
    OrderEndedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudget,
    OwnerBudgetCaps,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistration,
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_owner_inventory_checkpoints import (
    FakeOwnerInventoryCheckpoints,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    DEFAULT_TRADING_LIMITS,
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.credentials_doubles import ResolveOnlyCredentials
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.recording_publisher import (
    RecordingPublisher,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    single_venue_scopes,
    venue_context,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests" / "sanity"))

from binance_fake_server import FakeServerUrls, run_binance_fake_server

_SPOT = TradingVenue.SPOT_TESTNET
_TAG = "a3f9c1"
_OWNER = "bot-1"
#: The fake's starting balances: the user's own coins before enabling.
_BASELINE = {"USDT": Decimal(100000), "BTC": Decimal(10), "ETH": Decimal(100)}
_CAPS = OwnerBudgetCaps(100, timedelta(0), 600)
#: An order built only to ask the book for its facts.
_PROBE = Order(
    ClientOrderId("probe"), "BTCUSDT", OrderSide.BUY, OrderType.LIMIT, Decimal(0)
)


class _Credentials(ResolveOnlyCredentials):
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="fake-key", api_secret="fake-secret"),
            CredentialsSource.FILE,
        )


@dataclass
class _Venue:
    """One Spot venue over the fake, with its session, handlers and the
    emission path the user-data stream feeds."""

    urls: FakeServerUrls
    context: VenueContext
    state: TradingSessionState
    bus: MemoryEventBus
    stream: SpotUserDataStream

    def register(self, run_started_at: datetime) -> OwnerBudgetRegistrationResult:
        handler = RegisterOwnerBudgetCommandHandler(
            single_venue_scopes(self.context, self.state),
            OwnerInventoryDeriver(FakeOwnerInventoryCheckpoints()),
            _CAPS,
        )
        return handler.execute(
            RegisterOwnerBudgetCommand(_registration(run_started_at), venue=_SPOT)
        )

    def send(self, side: OrderSide, price: str, quantity: str) -> ExecuteOrderResult:
        scopes = single_venue_scopes(self.context, self.state)
        handler = ExecuteOrderCommandHandler(
            scopes,
            PreviewOrderQueryHandler(FakeVenueContexts(self.context)),
            TradingLimitPolicy(DEFAULT_TRADING_LIMITS),
            SessionReadiness(scopes, RecordingPublisher()),
        )
        query = PreviewOrderQuery(
            venue=_SPOT,
            symbol="BTCUSDT",
            side=side,
            order_type=OrderType.LIMIT,
            quantity=Decimal(quantity),
            reference_price=Decimal(price),
            client_order_tag=_TAG,
        )
        return handler.execute(
            ExecuteOrderCommand(order_request=query, live=True, owner_id=_OWNER)
        )

    def deliver_reports(self) -> None:
        """Hands the fake's executionReports to the venue's stream."""
        for event in self.urls.spot_account.drain_user_data_events():
            if event["e"] == "executionReport":
                asyncio.run(self.stream._handle_message(event))

    def open_orders(self) -> int:
        facts = self.state.owner_books.facts(_TAG, _OWNER, _PROBE, datetime.now(UTC))
        assert facts is not None
        return facts.open_order_count


def _registration(run_started_at: datetime) -> OwnerBudgetRegistration:
    budget = OwnerBudget(10, Decimal(5000), timedelta(0), 60, timedelta(minutes=1))
    return OwnerBudgetRegistration(_OWNER, _TAG, "BTCUSDT", run_started_at, budget)


def _venue(urls: FakeServerUrls) -> _Venue:
    sessions = SpotSessionFactory()
    cache = InMemorySymbolOrderMetadataCache()
    metadata = SpotMetadataProvider(sessions, cache)
    account_reader = SpotAccountReader(sessions, _Credentials())
    context = venue_context(
        _SPOT,
        account_reader=account_reader,
        client_factory=SpotTradingClientFactory(sessions, _Credentials(), metadata),
        metadata_provider=metadata,
        history_reader=SpotHistoryReader(
            sessions, _Credentials(), ListedSymbols(metadata, cache)
        ),
        book_ticker_reader=SpotBookTickerReader(sessions),
    )
    state = TradingSessionState()
    state.enable(set(), spot_baseline_holdings=_BASELINE)
    bus = MemoryEventBus()
    stream = SpotUserDataStream(
        VenueEventEmitter(bus, _SPOT, state.owner_books),
        Mock(),
        _Credentials(),
        account_reader,
        EquityCurveRecorder(),
    )
    return _Venue(urls, context, state, bus, stream)


def _with_venue(body: Callable[[_Venue], None]) -> None:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        body(_venue(urls))


def _run_start() -> datetime:
    return datetime.now(UTC) - timedelta(minutes=5)


def test_a_ladder_of_ten_rests_the_eleventh_is_refused_and_a_fill_frees_a_slot() -> (
    None
):
    def body(venue: _Venue) -> None:
        assert venue.register(_run_start()).registered

        ladder = [
            venue.send(OrderSide.BUY, f"{49000 - 10 * n}", "0.0002") for n in range(10)
        ]
        eleventh = venue.send(OrderSide.BUY, "48800", "0.0002")

        assert [result.blocked_by for result in ladder] == [None] * 10
        assert eleventh.blocked_by is TradingLimitViolation.OWNER_BUDGET_OPEN_ORDERS

        venue.urls.spot_account.set_last_price("BTCUSDT", Decimal(49000))
        venue.deliver_reports()

        assert venue.open_orders() == 9
        assert venue.send(OrderSide.BUY, "48800", "0.0002").blocked_by is None

    _with_venue(body)


def test_a_fill_lets_the_counter_sell_through_up_to_the_inventory_net_of_fees() -> None:
    """The fake charges a buy's fee in the base asset (0.1 %): 0.01 BTC bought
    leaves 0.00999 held, so a counter sell of 0.01 is refused and 0.00999
    passes."""

    def body(venue: _Venue) -> None:
        venue.register(_run_start())
        assert venue.send(OrderSide.BUY, "49000", "0.01").blocked_by is None
        venue.urls.spot_account.set_last_price("BTCUSDT", Decimal(49000))
        venue.deliver_reports()

        too_much = venue.send(OrderSide.SELL, "49500", "0.01")
        held = venue.send(OrderSide.SELL, "49500", "0.00999")

        assert too_much.blocked_by is (
            TradingLimitViolation.OWNER_BUDGET_SELL_EXCEEDS_INVENTORY
        )
        assert held.blocked_by is None

    _with_venue(body)


def test_a_cancel_reaches_the_book_and_the_bus_under_the_orders_own_id() -> None:
    """`BUG-141`: the fake's cancel report names the cancel request in `c`
    and the order in `C`."""

    def body(venue: _Venue) -> None:
        venue.register(_run_start())
        placed = venue.send(OrderSide.BUY, "48000", "0.0002").submitted_order
        assert placed is not None
        ended: list[OrderEndedEvent] = []
        venue.bus.on(OrderEndedEvent, ended.append)

        venue.context.client_factory.create(OrderSubmissionMode.LIVE).cancel_order(
            "BTCUSDT", str(placed.client_order_id)
        )
        venue.deliver_reports()

        assert [event.order.client_order_id for event in ended] == [
            placed.client_order_id
        ]
        assert venue.open_orders() == 0

    _with_venue(body)


def test_registering_again_derives_the_inventory_from_the_venues_history() -> None:
    """The fill, its base-asset fee and nothing else: an untagged manual buy
    on the same symbol is the user's."""

    def body(venue: _Venue) -> None:
        run_started_at = _run_start()
        venue.register(run_started_at)
        venue.send(OrderSide.BUY, "49000", "0.01")
        venue.urls.spot_account.set_last_price("BTCUSDT", Decimal(49000))
        venue.context.client_factory.create(OrderSubmissionMode.LIVE).place_order(
            Order(
                ClientOrderId("web_manualbuy0001"),
                "BTCUSDT",
                OrderSide.BUY,
                OrderType.MARKET,
                Decimal("0.5"),
            )
        )

        result = venue.register(run_started_at)

        assert result.inventory == OwnerInventory(Decimal("0.00999"), Decimal(490))

    _with_venue(body)


def test_an_emergency_stop_sells_the_bots_coins_under_its_tag_and_not_the_users() -> (
    None
):
    """The user holds 10 BTC from before enabling; the bot bought 0.00999 net.
    The stop sells exactly the bot's 0.00999 under its tag, so the inventory
    derived again is zero and the user's 10 BTC are where they were."""

    def body(venue: _Venue) -> None:
        run_started_at = _run_start()
        venue.register(run_started_at)
        venue.send(OrderSide.BUY, "49000", "0.01")
        venue.urls.spot_account.set_last_price("BTCUSDT", Decimal(49000))
        venue.deliver_reports()

        EmergencyStopCommandHandler(
            single_venue_scopes(venue.context, venue.state), RecordingPublisher()
        ).execute(EmergencyStopCommand(venue=_SPOT))

        deriver = OwnerInventoryDeriver(FakeOwnerInventoryCheckpoints())
        after = deriver.derive(
            _registration(run_started_at),
            venue.context.history_reader,
            datetime.now(UTC),
        ).inventory
        btc = {
            row["asset"]: Decimal(row["free"])
            for row in venue.urls.spot_account.account_balances()
        }["BTC"]
        assert after.quantity == 0
        assert btc == _BASELINE["BTC"]

    _with_venue(body)
