"""`EPIC-034H` — a world the readiness reader reads: the bots store, the Grid
kind, a funded Spot Testnet account, the venue's terms and book, and the
session whose lease it asks about. Every collaborator is its verified fake.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_readiness_reader import (
    BotReadinessReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FakeBotClock,
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_account_snapshot import (
    a_venue_account_snapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_accounts import (
    FakeVenueAccountReader,
    FakeVenueAccounts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CAP,
    CONFIG,
    LAST_PRICE,
    SYMBOL,
    terms_entry,
)

FUNDED = Decimal(50_000)


@dataclass
class ReadinessWorld:
    store: FakeBotStore
    clock: FakeBotClock
    session: FakeTradingSession
    account: FakeVenueAccountReader
    reader: BotReadinessReader
    caps: OwnerBudgetCaps


def readiness_world(
    *,
    cap: Decimal = CAP,
    caps: OwnerBudgetCaps = DEFAULT_OWNER_BUDGET_CAPS,
    available: Decimal = FUNDED,
    bot_venue: TradingVenue = TradingVenue.SPOT_TESTNET,
    config: dict[str, str] | None = None,
    can_trade: bool | None = True,
) -> ReadinessWorld:
    session = FakeTradingSession()
    ports = FakeVenueTradingPorts(
        fake_venue_ports(
            TradingVenue.SPOT_TESTNET,
            trading_session=session,
            order_entry_terms=FakeOrderEntryTerms(
                terms_entry(),
                books={
                    SYMBOL: BestBidAsk(
                        SYMBOL, LAST_PRICE, Decimal(1), LAST_PRICE, Decimal(1)
                    )
                },
                notional_limit=cap,
            ),
        )
    )
    snapshot = replace(
        a_venue_account_snapshot(symbol=SYMBOL),
        available=available,
        can_trade=can_trade,
        price=LAST_PRICE,
    )
    account = FakeVenueAccountReader(AccountSource.SPOT_TESTNET, snapshot)
    store, clock = FakeBotStore(), FakeBotClock()
    definition = BotDefinition("grid one", "grid", bot_venue, SYMBOL, config or CONFIG)
    store.save(StoredBot(Bot.draft(BotId(BOT), definition, clock.now()), {}))
    kinds = BotKindCatalog([GridKind(None, GridThresholds())])  # type: ignore[arg-type]
    reader = BotReadinessReader(store, kinds, FakeVenueAccounts(account), ports, caps)
    return ReadinessWorld(store, clock, session, account, reader, caps)


def add_bot(
    world: ReadinessWorld,
    bot_id: str,
    state: BotLifecycleState,
    config: dict[str, str] | None = None,
) -> None:
    definition = BotDefinition(
        f"grid {bot_id}", "grid", TradingVenue.SPOT_TESTNET, SYMBOL, config or CONFIG
    )
    world.store.save(
        StoredBot(
            Bot(BotId(bot_id), definition, BotLifecycle(state), world.clock.now()), {}
        )
    )


def failing(world: ReadinessWorld, failure: ConnectFailure) -> None:
    world.account.answer_with(failure)
