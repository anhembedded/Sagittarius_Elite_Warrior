"""`EPIC-035A` — the watch's periodic check: a quiet feed halts, a refused stream is retried.

The ticker is the verified fake and the clock a fake monotonic one; nothing sleeps.
"""

from __future__ import annotations

import logging
import threading
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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
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
    PRICE_START_GRACE_SECONDS,
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
    recovering_world,
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


def test_a_bot_entering_starting_gets_no_executor_from_the_watch() -> None:
    """`BotRunner.start` saves STARTING and then builds the run's executor
    (`fresh`); an executor built by the watch in between would be a second writer
    for the bot, and a tick could be routed to it."""
    parts = watched_running()
    parts.save_state(S.STOPPED)
    assert parts.executors.get(BOT) is None

    parts.save_state(S.STARTING)
    parts.ticker.fire()

    assert parts.executors.get(BOT) is None
    assert parts.testnet.held_by(parts.owner()) is not None, "its stream is held"


class _SlowStop(FakeMarketStream):
    """A stream whose `stop` can be held, to put a second thread in its way."""

    def __init__(self) -> None:
        super().__init__()
        self.stopping = threading.Event()
        self.proceed = threading.Event()

    def stop(self, owner_id: str) -> StreamOutcome:
        self.stopping.set()
        assert self.proceed.wait(timeout=5.0)
        return super().stop(owner_id)


def test_a_stop_in_flight_cannot_close_the_stream_a_restart_just_opened() -> None:
    """Stop then Start of one bot on two threads: the release of the old run must
    finish before the new run's stream opens, or its late `stop(owner)` closes
    the new stream (same owner) while the watch believes it is open, and the bot
    halts `PRICE_FEED_STALE` for nothing."""
    testnet = _SlowStop()
    parts = watched(running_world(), testnet=testnet)
    parts.watch.start()
    parts.save_state(S.STOPPED, notify=False)
    releasing = threading.Thread(
        target=parts.watch.on_bot_changed, args=(BotChangedEvent(bot_id=BOT),)
    )
    releasing.start()
    assert testnet.stopping.wait(timeout=5.0)
    parts.save_state(S.STARTING, notify=False)
    restarting = threading.Thread(
        target=parts.watch.on_bot_changed, args=(BotChangedEvent(bot_id=BOT),)
    )
    restarting.start()

    testnet.proceed.set()
    releasing.join(timeout=5.0)
    restarting.join(timeout=5.0)

    assert testnet.held_by(parts.owner()) is not None
    assert [c for c in testnet.calls if c[0] == "start"] == [
        ("start", parts.owner()),
        ("start", parts.owner()),
    ]
    assert testnet.calls[-1] == ("start", parts.owner()), "the open came last"


def test_a_recovering_bot_with_trading_off_still_halts_on_a_quiet_feed() -> None:
    """Pinned (PR 430 review). A restored bot waiting for trading to open cannot
    watch its stop loss with no feed, so the quiet-feed halt is not exempted the
    way a switch-off halt is: the user sees HALTED with the feed's reason. Whether
    the ladder can then be taken off is trading's answer, not this rule's: with
    the switch off its cancels are refused and `GridTaskGuard` appends that to the
    detail (`test_grid_executor_parking.py`); the simulated venue here does not
    model the refusal, so this pins the decision only."""
    world = recovering_world()
    world.session.set_enabled(enabled=False)

    world.monotonic.advance(PRICE_START_GRACE_SECONDS)
    world.executor.facts.on_price_age_check()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.PRICE_FEED_STALE
