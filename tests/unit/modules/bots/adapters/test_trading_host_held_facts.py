"""`EPIC-047B` - the facts only the host holds, read from the ports the Bots screen's reads use."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.adapters.latest_venue_reads import (
    LatestVenueReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.trading_host_held_facts import (
    TradingHostHeldFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_held_facts import (
    BotExchangeRead,
    SymbolLease,
    VenueKeyState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_credentials_provider import (
    FakeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import seed
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.host_facts.host_facts_world import (
    PLANTED_KEY_LIKE,
    spot_facts,
)

SPOT = TradingVenue.SPOT_TESTNET
FUTURES = TradingVenue.FUTURES_TESTNET


class OnlyBuilt(FakeVenueContexts):
    """Contexts where only some venues have been asked for, and asking for another one is a fault:
    reading the host's facts must never be what builds a venue."""

    def __init__(
        self, built: tuple[TradingVenue, ...], *contexts: VenueContext
    ) -> None:
        super().__init__(*contexts)
        self._built = built
        self.asked: list[TradingVenue] = []

    def built(self) -> tuple[TradingVenue, ...]:
        return self._built

    def get(self, venue: TradingVenue) -> VenueContext:
        assert venue in self._built, f"{venue} was built by reading its key state"
        self.asked.append(venue)
        return super().get(venue)


class World:
    def __init__(self, *, has_key: bool = True, built_futures: bool = False) -> None:
        self.spot_session = FakeTradingSession()
        self.futures_session = FakeTradingSession()
        self.store = FakeBotStore()
        self.reads = LatestVenueReads()
        self.provider = FakeCredentialsProvider(has_key=has_key)
        self.ports = FakeVenueTradingPorts(
            fake_venue_ports(SPOT, trading_session=self.spot_session),
            fake_venue_ports(FUTURES, trading_session=self.futures_session),
        )
        built = (SPOT, FUTURES) if built_futures else (SPOT,)
        self.contexts: IVenueContexts = OnlyBuilt(
            built,
            fake_venue_context(SPOT, credentials_provider=self.provider),
            fake_venue_context(FUTURES, credentials_provider=FakeCredentialsProvider()),
        )

    def held(self) -> TradingHostHeldFacts:
        return TradingHostHeldFacts(
            self.ports, self.contexts, self.store, DEFAULT_OWNER_BUDGET_CAPS, self.reads
        )


def test_the_enabled_venues_and_the_caps_are_the_ports_own() -> None:
    world = World()

    read = world.held().read()

    assert read.enabled_venues == (SPOT, FUTURES)
    assert read.caps == DEFAULT_OWNER_BUDGET_CAPS


def test_a_built_venue_with_a_key_says_a_key_is_saved_and_one_without_says_it_is_not() -> (
    None
):
    saved = World(has_key=True).held().read()
    missing = World(has_key=False).held().read()

    assert saved.venue_keys == (VenueKeyState(SPOT, key_saved=True),)
    assert missing.venue_keys == (VenueKeyState(SPOT, key_saved=False),)


def test_the_key_itself_is_nowhere_in_what_is_read() -> None:
    world = World()
    world.provider.save_to_file(PLANTED_KEY_LIKE, PLANTED_KEY_LIKE[::-1])

    read = world.held().read()

    assert PLANTED_KEY_LIKE not in repr(read)
    assert PLANTED_KEY_LIKE[::-1] not in repr(read)


def test_a_venue_nothing_has_built_is_not_built_by_reading_it() -> None:
    """`OnlyBuilt.get` fails the test if the reader asks a venue nothing has used. The venue is
    still listed as enabled; its key state and leases are simply not known yet."""
    world = World(built_futures=False)
    seed(world.store, "aaaaaa", BotLifecycleState.STOPPED, venue=FUTURES)

    read = world.held().read()

    assert FUTURES in read.enabled_venues
    assert [key.venue for key in read.venue_keys] == [SPOT]
    assert {lease.venue for lease in read.leases} <= {SPOT}


def test_a_lease_is_read_for_each_symbol_a_stored_bot_is_on() -> None:
    world = World()
    seed(world.store, "aaaaaa", BotLifecycleState.RUNNING)
    assert world.spot_session.claim_symbol("BTCUSDT", "grid:aaaaaa")

    read = world.held().read()

    assert read.leases == (SymbolLease(SPOT, "BTCUSDT", "grid:aaaaaa"),)


def test_a_symbol_nobody_holds_is_listed_with_no_holder() -> None:
    world = World()
    seed(world.store, "aaaaaa", BotLifecycleState.STOPPED)

    read = world.held().read()

    assert read.leases == (SymbolLease(SPOT, "BTCUSDT", ""),)


def test_the_lease_of_a_built_futures_venue_is_read_beside_spots() -> None:
    world = World(built_futures=True)
    seed(world.store, "aaaaaa", BotLifecycleState.RUNNING)
    assert world.futures_session.claim_symbol("BTCUSDT", "strategy:ema")

    read = world.held().read()

    assert SymbolLease(FUTURES, "BTCUSDT", "strategy:ema") in read.leases
    assert SymbolLease(SPOT, "BTCUSDT", "") in read.leases


def test_a_host_with_no_bots_has_no_leases_to_read() -> None:
    assert World().held().read().leases == ()


def test_the_last_snapshot_a_reader_took_is_carried_for_a_stored_bot() -> None:
    world = World()
    seed(world.store, "aaaaaa", BotLifecycleState.RUNNING)
    snapshot = ExchangeUnavailable("Spot Testnet is not enabled")
    world.reads.record("aaaaaa", snapshot)

    read = world.held().read()

    assert read.exchange_reads == (BotExchangeRead("aaaaaa", snapshot),)


def test_a_deleted_bots_snapshot_is_not_carried() -> None:
    world = World()
    world.reads.record("gone", ExchangeUnavailable("x"))

    assert world.held().read().exchange_reads == ()


def test_snapshots_are_listed_in_bot_order() -> None:
    world = World()
    for bot_id in ("bbbbbb", "aaaaaa"):
        seed(world.store, bot_id, BotLifecycleState.RUNNING)
        world.reads.record(bot_id, ExchangeUnavailable(bot_id))

    read = world.held().read()

    assert [r.bot_id for r in read.exchange_reads] == ["aaaaaa", "bbbbbb"]


def test_a_bot_the_host_never_read_has_no_snapshot_not_an_empty_one() -> None:
    world = World()
    seed(world.store, "aaaaaa", BotLifecycleState.RUNNING)

    assert world.held().read().exchange_reads == ()


def test_a_refused_bot_file_does_not_stop_the_read() -> None:
    world = World()
    seed(world.store, "aaaaaa", BotLifecycleState.RUNNING)
    world.store.refuse_file(BotId("bbbbbb"), "not a bot")

    read = world.held().read()

    assert read.leases == (SymbolLease(SPOT, "BTCUSDT", ""),)


def test_nothing_in_what_is_read_needs_the_exchange() -> None:
    """The reader holds no exchange port at all: it is given the ports' sessions, the contexts' key
    states, the store and the recorded reads. A fake with an account that raises proves nothing the
    constructor does not already say; this pins the constructor."""
    assert spot_facts().symbol == "BTCUSDT"
    held = World().held()
    assert set(vars(held)) == {"_ports", "_contexts", "_store", "_caps", "_reads"}
