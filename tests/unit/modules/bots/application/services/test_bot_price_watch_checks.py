"""`EPIC-035A` — the watch's periodic check: a quiet feed halts, a refused stream is retried.

The ticker is the verified fake and the clock a fake monotonic one; nothing sleeps.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_price_watch import (
    bot_price_owner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_executor_factory import (
    GridExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParamsError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.price_freshness import (
    PRICE_STALE_AFTER_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    StreamOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    VENUE,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.price_watch_world import (
    SECOND,
    add_second_bot,
    running_world,
    watched,
    watched_running,
)

S = BotLifecycleState
_TESTNET = VENUE.market_data_venue
_MAINNET = MarketDataVenue.MAINNET_PUBLIC
_AT = datetime(2026, 10, 8, 9, tzinfo=UTC)


def test_the_ticker_runs_the_age_check_and_a_silent_feed_halts_the_bot() -> None:
    parts = watched_running()
    parts.watch.start()
    parts.tick(121.0)

    parts.world.monotonic.advance(PRICE_STALE_AFTER_SECONDS)
    parts.ticker.fire()

    assert parts.world.state() is S.HALTED
    assert parts.world.runtime().reason is GridReason.PRICE_FEED_STALE


def test_the_ticker_leaves_a_bot_that_keeps_hearing_ticks_alone() -> None:
    parts = watched_running()
    parts.watch.start()

    for _ in range(4):
        parts.tick(121.0)
        parts.world.monotonic.advance(PRICE_STALE_AFTER_SECONDS - 1)
        parts.ticker.fire()

    assert parts.world.state() is S.RUNNING


class _RefusingOnce(FakeMarketStream):
    """A stream whose first `start` fails, as a port may answer."""

    def __init__(self) -> None:
        super().__init__()
        self.refused = 0

    def start(
        self,
        owner_id: str,
        market_type: MarketType,
        symbols: Sequence[str],
        interval: TimeFrame,
    ) -> StreamOutcome:
        if self.refused == 0:
            self.refused += 1
            return StreamOutcome(success=False, message="no connection")
        return super().start(owner_id, market_type, symbols, interval)


def test_a_stream_that_would_not_start_is_tried_again_on_the_next_check(
    caplog: pytest.LogCaptureFixture,
) -> None:
    testnet = _RefusingOnce()
    parts = watched(running_world(), testnet=testnet)

    with caplog.at_level(logging.WARNING, logger="App.Bots.PriceWatch"):
        parts.watch.start()
    assert testnet.held_by(parts.owner()) is None
    assert any("no connection" in r.getMessage() for r in caplog.records)

    parts.ticker.fire()

    assert testnet.held_by(parts.owner()) is not None


class _VenueNotEnabledYet(GridExecutorFactory):
    """A factory whose venue's trading is not enabled until `enable()`."""

    def __init__(self, inner: GridExecutorFactory) -> None:
        self._inner = inner
        self.enabled = False

    def create(self, bot: Bot):  # type: ignore[no-untyped-def]
        if not self.enabled:
            raise VenueNotEnabledError(bot.definition.venue, ())
        return self._inner.create(bot)


def test_a_bot_on_a_venue_not_enabled_yet_gets_its_executor_when_it_is() -> None:
    world = running_world()
    gated = _VenueNotEnabledYet(world.factory)
    parts = watched(world, factory=gated)
    parts.save_state(S.RECOVERING, notify=False)

    parts.watch.start()
    assert parts.executors.get(BOT) is None, "boot must not fail on it"
    assert parts.testnet.held_by(parts.owner()) is not None

    gated.enabled = True
    parts.ticker.fire()

    assert parts.executors.get(BOT) is not None


class _Unreadable(GridExecutorFactory):
    """A factory that refuses the stored bot, as a hand-edited file may make it."""

    def __init__(self) -> None:
        self.attempts = 0

    def create(self, bot: Bot):  # type: ignore[no-untyped-def]
        self.attempts += 1
        raise GridParamsError("lower is missing")


def test_a_bot_no_executor_can_be_built_for_does_not_stop_the_others_and_is_said_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = running_world()
    refusing = _Unreadable()
    parts = watched(world, factory=refusing)
    add_second_bot(world)

    with caplog.at_level(logging.ERROR, logger="App.Bots.PriceWatch"):
        parts.watch.start()
        parts.ticker.fire()
        parts.ticker.fire()

    assert parts.testnet.held_by(parts.owner()) is not None
    assert parts.testnet.held_by(bot_price_owner(BotId(SECOND))) is not None
    assert refusing.attempts >= 4, "each check tries again"
    said = [r for r in caplog.records if "no executor could be built" in r.getMessage()]
    assert len(said) == 2, "once for each of the two bots, not once per check"
