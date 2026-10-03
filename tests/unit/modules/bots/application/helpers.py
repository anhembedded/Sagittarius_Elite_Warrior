"""Shared set-up for the bots use-case tests: a fake store, a fake clock, a bot."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FAKE_CLOCK_START,
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def definition(name: str = "grid one") -> BotDefinition:
    return BotDefinition(
        name=name,
        kind="grid",
        venue=TradingVenue.SPOT_TESTNET,
        symbol="BTCUSDT",
        config={"lower": "60000"},
    )


def seed(store: FakeBotStore, bot_id: str, state: BotLifecycleState) -> Bot:
    bot = Bot(BotId(bot_id), definition(), BotLifecycle(state), FAKE_CLOCK_START)
    store.save(StoredBot(bot, {"cycles": 1}))
    return bot


def state_of(store: FakeBotStore, bot_id: str) -> BotLifecycleState:
    return store.load(BotId(bot_id)).bot.state
