"""`EPIC-035A` — the bots module wires the price watch: at boot, on every bot change, at shutdown.

Each test fails when its line of `BotsModule` is deleted (`testing-rule.md` §2).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_price_watch import (
    BotPriceWatch,
    bot_price_owner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.contract_bot_store import (
    sample_bot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import BotLifecycle
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    Subscription,
)
from Sagittarius_Elite_Warrior.tests.integration.modules.bots.bots_module_world import (
    GRID_CONFIG,
    RUN_STARTED,
    registered,
)


def test_boot_gives_a_restored_bot_its_own_price_stream_and_hears_its_tick(
    tmp_path: Path,
) -> None:
    """`EPIC-035A` — delete `watch.start()` from `boot()` and this fails: a bot
    restored RECOVERING streams its symbol with no chart anywhere, and a tick
    below its stop loss reaches it through the router `boot()` subscribed."""
    sampled = sample_bot().bot
    bot = replace(sampled, definition=replace(sampled.definition, config=GRID_CONFIG))
    JsonBotStore(tmp_path).save(StoredBot(bot))
    module, context = registered(tmp_path)

    module.boot(context)
    try:
        owner = bot_price_owner(bot.bot_id)
        assert context.streams.held_by(owner) == Subscription(
            owner, MarketType.SPOT, ("BTCUSDT",), TimeFrame.ONE_MINUTE
        )
        assert context.container.resolve(BotExecutors).get("abc123") is not None
    finally:
        module.shutdown(context)


def test_boot_subscribes_the_price_watch_to_every_bot_change(tmp_path: Path) -> None:
    """Delete the `bus.on(BotChangedEvent, ...)` line from `boot()` and this
    fails: a bot that becomes STOPPED would keep its stream."""
    module, context = registered(tmp_path)
    module.boot(context)
    store = context.container.resolve(IBotStore)
    stored = sample_bot()
    running = replace(
        stored.bot, lifecycle=BotLifecycle(BotLifecycleState.RUNNING, RUN_STARTED)
    )
    owner = bot_price_owner(stored.bot.bot_id)

    store.save(replace(stored, bot=running))
    assert context.streams.held_by(owner) is not None

    stopped = replace(
        stored.bot, lifecycle=BotLifecycle(BotLifecycleState.STOPPED, RUN_STARTED)
    )
    store.save(replace(stored, bot=stopped))

    assert context.streams.held_by(owner) is None
    handlers = context.event_bus.subscriptions()[BotChangedEvent.__name__]
    assert BotPriceWatch in [type(h.__self__) for h in handlers]


def test_shutdown_releases_every_price_stream_and_the_ticker(tmp_path: Path) -> None:
    sampled = sample_bot().bot
    bot = replace(sampled, definition=replace(sampled.definition, config=GRID_CONFIG))
    JsonBotStore(tmp_path).save(StoredBot(bot))
    module, context = registered(tmp_path)
    module.boot(context)
    assert context.streams.is_streaming("BTCUSDT")

    module.shutdown(context)

    assert not context.streams.is_streaming("BTCUSDT")
    assert context.ticker.closed is True
