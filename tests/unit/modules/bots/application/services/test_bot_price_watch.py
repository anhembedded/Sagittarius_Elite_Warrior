"""`EPIC-035A` — every bot that is not at rest owns its price stream.

No chart is ever built: the stream exists because the bot is not stopped, and a tick
published for its symbol reaches its stop loss.
"""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_price_watch import (
    bot_price_owner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.bot_stream_owner import (
    bot_stream_owner,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    Subscription,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    SYMBOL,
    VENUE,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.price_watch_world import (
    SECOND,
    add_second_bot,
    watched_running,
)

S = BotLifecycleState
_TESTNET = VENUE.market_data_venue
#: The states in which a bot is not at rest: each owns a price stream.
_NOT_AT_REST = [
    S.STARTING,
    S.RUNNING,
    S.PAUSED,
    S.RECOVERING,
    S.HALTED,
    S.STOPPING,
    S.ERROR,
]


def test_a_stop_loss_is_watched_with_no_chart_open() -> None:
    parts = watched_running()

    parts.watch.start()
    assert parts.testnet.held_by(parts.owner()) == Subscription(
        parts.owner(), MarketType.SPOT, (SYMBOL,), TimeFrame.ONE_MINUTE
    )

    parts.tick(89.0)

    assert parts.world.state() is S.STOPPED
    assert parts.world.runtime().reason is GridReason.STOP_LOSS
    assert parts.world.book.open == {}


def test_the_stream_is_the_bots_own_venue_and_no_other() -> None:
    """`BUG-172` — a Spot Testnet bot streams Spot Testnet's market only."""
    parts = watched_running()

    parts.watch.start()

    assert parts.testnet.held_by(parts.owner()) is not None
    assert parts.mainnet.held_by(parts.owner()) is None
    assert set(parts.sources.asked) == {_TESTNET}


@pytest.mark.parametrize("state", _NOT_AT_REST)
def test_a_bot_that_is_not_at_rest_owns_a_stream(state: S) -> None:
    parts = watched_running()
    parts.save_state(state, notify=False)

    parts.watch.start()

    assert parts.testnet.held_by(parts.owner()) is not None


@pytest.mark.parametrize("state", [S.STOPPED, S.DRAFT])
def test_a_bot_at_rest_owns_no_stream(state: S) -> None:
    parts = watched_running()
    parts.save_state(state, notify=False)

    parts.watch.start()

    assert parts.testnet.held_by(parts.owner()) is None
    assert parts.testnet.calls == []


@pytest.mark.parametrize("state", [S.STOPPED, S.DRAFT])
def test_the_stream_is_released_when_the_bot_reaches_rest(state: S) -> None:
    parts = watched_running()
    parts.watch.start()
    assert parts.testnet.held_by(parts.owner()) is not None

    parts.save_state(state)

    assert parts.testnet.held_by(parts.owner()) is None
    assert parts.testnet.is_streaming(SYMBOL) is False


def test_the_stream_is_released_when_the_bot_is_deleted() -> None:
    parts = watched_running()
    parts.watch.start()

    parts.world.store.delete(BotId(BOT))
    parts.watch.on_bot_changed(BotChangedEvent(bot_id=BOT, removed=True))

    assert parts.testnet.held_by(parts.owner()) is None


def test_a_change_that_keeps_the_bot_running_does_not_resubscribe() -> None:
    """A fill saves the bot too: that must not churn the websocket."""
    parts = watched_running()
    parts.watch.start()

    parts.watch.on_bot_changed(BotChangedEvent(bot_id=BOT))
    parts.watch.on_bot_changed(BotChangedEvent(bot_id=BOT))

    assert parts.testnet.calls == [("start", parts.owner())]


def test_two_bots_on_one_symbol_share_the_stream_until_the_last_leaves() -> None:
    parts = watched_running()
    add_second_bot(parts.world)
    second = bot_price_owner(BotId(SECOND))

    parts.watch.start()
    assert parts.testnet.held_by(parts.owner()) is not None
    assert parts.testnet.held_by(second) is not None

    parts.save_state(S.STOPPED)
    assert parts.testnet.is_streaming(SYMBOL) is True, "the other bot still needs it"

    parts.save_state(S.STOPPED, SECOND)
    assert parts.testnet.is_streaming(SYMBOL) is False
    assert parts.testnet.calls == [
        ("start", parts.owner()),
        ("start", second),
        ("stop", parts.owner()),
        ("stop", second),
    ]


def test_a_restored_bot_gets_its_executor_and_its_stream_at_start() -> None:
    """The bots a restart leaves in RECOVERING heard nothing until a fill or the
    switch built their executor; they need both before any tick can matter."""
    parts = watched_running()
    parts.save_state(S.RECOVERING, notify=False)
    assert parts.executors.get(BOT) is None

    parts.watch.start()

    assert parts.executors.get(BOT) is not None
    assert parts.testnet.held_by(parts.owner()) is not None
    parts.tick(89.0)
    assert parts.world.state() is S.STOPPED


def test_closing_the_watch_releases_every_stream_and_the_ticker() -> None:
    parts = watched_running()
    add_second_bot(parts.world)
    parts.watch.start()

    parts.watch.close()

    assert parts.testnet.is_streaming(SYMBOL) is False
    assert parts.ticker.closed is True
    parts.watch.close()  # idempotent


def test_a_watch_that_was_closed_starts_nothing_more() -> None:
    parts = watched_running()
    parts.watch.start()
    parts.watch.close()
    calls = list(parts.testnet.calls)

    parts.watch.on_bot_changed(BotChangedEvent(bot_id=BOT))

    assert parts.testnet.calls == calls


def test_the_streams_owner_is_not_the_charts() -> None:
    """The chart's owner is `bot.<id>`; sharing it would let one replace the
    other's subscription (`BOT-126`)."""
    assert bot_price_owner(BotId(BOT)) != bot_stream_owner(BotId(BOT))


def test_a_bot_on_a_venue_that_trades_no_market_is_not_streamed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Trading off (`TradingVenue.DISABLED`) names no market; a stream needs one,
    and guessing Spot would price the bot from the wrong instrument."""
    parts = watched_running()
    stored = parts.world.store.load(BotId(BOT))
    definition = replace(stored.bot.definition, venue=TradingVenue.DISABLED)
    parts.world.store.save(StoredBot(replace(stored.bot, definition=definition)))

    with caplog.at_level(logging.WARNING, logger="App.Bots.PriceWatch"):
        parts.watch.on_bot_changed(BotChangedEvent(bot_id=BOT))

    assert parts.testnet.calls == []
    assert any("trades no market" in r.getMessage() for r in caplog.records)
