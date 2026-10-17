"""`EPIC-042C` - the incident of 2026-10-17, on the composed app over the fake Binance server.

A Spot grid heard no tick for the limit and halted. The feed came back. Before this change the bot
stayed HALTED until a person resumed it, and the headless host had no way to. Now it waits in
AWAITING_RECOVERY, resumes through the Resume path once the feed has stayed healthy for the dwell
(the fake exchange sees the old ladder cancelled and a new one laid), and ends as a Stop if the
price it reads at the attempt is through the stop loss. The websocket is the one substitution;
the beat is the price watch's ticker, fired by hand, and the clock is the test's.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.price_freshness import (
    PRICE_STALE_AFTER_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    DEFAULT_RULE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)

from .grid_fake_exchange import SPOT, BootedApp, FakeExchange, booted, resting
from .test_a_bot_owns_its_price_stream_on_the_fake_exchange import (
    _BELOW_STOP_LOSS,
    _INSIDE_THE_RANGE,
    _publish_tick,
    _started,
)

S = BotLifecycleState
_BEAT = 5
_DWELL = int(DEFAULT_RULE.dwell.total_seconds())


def _beats(
    app: BootedApp, seconds: int, *, price: float | None = _INSIDE_THE_RANGE
) -> None:
    for _ in range(0, seconds, _BEAT):
        app.monotonic.advance(_BEAT)
        if price is not None:
            _publish_tick(app, price)
        app.ticker.fire()
        app.deliver()


def _halted_by_a_silent_feed(app: BootedApp) -> str:
    bot_id = _started(app)
    # The account stream is up, as it was in the incident; an attempt needs every cause clear.
    app.engine.event_bus.emit(
        UserStreamHealthEvent(
            UserStreamState.CONNECTED, datetime.now(UTC), 1, venue=SPOT
        )
    )
    app.deliver()
    _publish_tick(app, _INSIDE_THE_RANGE)
    app.monotonic.advance(PRICE_STALE_AFTER_SECONDS)
    app.ticker.fire()
    app.deliver()
    assert app.bot(bot_id).state is S.AWAITING_RECOVERY
    assert resting(app.urls) == {}, "the waiting bot has nothing on the exchange"
    return bot_id


class _Lines(logging.Handler):
    """What the bot's logger said, kept: the `App.*` loggers do not propagate to `caplog`."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


def test_the_feed_returns_and_the_bot_lays_a_fresh_ladder_with_no_person(
    exchange: FakeExchange,
) -> None:
    lines = _Lines()
    logger = logging.getLogger("App.Bots.GridExecutor")
    logger.addHandler(lines)
    try:
        with booted(exchange) as app:
            bot_id = _halted_by_a_silent_feed(app)

            _beats(app, _DWELL + 3 * _BEAT)

            assert app.bot(bot_id).state is S.RUNNING
            assert resting(app.urls), "a new ladder rests on the exchange"
            assert len(app.bot(bot_id).lifecycle.recovery_attempts) == 1
    finally:
        logger.removeHandler(lines)
    tagged = [line for line in lines.lines if "[bot-halt-recovery]" in line]
    assert any("is transient" in line for line in tagged), "the entry is logged"
    assert any("recovery attempt 1 of 3" in line for line in tagged), (
        "the attempt is logged"
    )
    assert any("recovered from price_feed_stale" in line for line in tagged), (
        "the outcome is"
    )


def test_a_feed_that_stays_silent_leaves_the_bot_waiting_with_nothing_on_the_exchange(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        bot_id = _halted_by_a_silent_feed(app)

        _beats(app, 20 * 60, price=None)

        assert app.bot(bot_id).state is S.AWAITING_RECOVERY
        assert resting(app.urls) == {}
        assert app.bot(bot_id).lifecycle.recovery_attempts == ()


def test_the_attempt_reads_the_price_and_a_stop_loss_crossed_in_the_gap_ends_the_bot(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        bot_id = _halted_by_a_silent_feed(app)
        _beats(app, _DWELL - 2 * _BEAT)
        app.move_price(int(_BELOW_STOP_LOSS))

        _beats(app, 6 * _BEAT)

        assert app.bot(bot_id).state is S.STOPPED
        assert app.runtime(bot_id).reason is GridReason.STOP_LOSS
        assert resting(app.urls) == {}


def test_the_ledger_is_in_the_bots_file_and_a_restart_ends_the_wait_in_halted(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as first:
        bot_id = _halted_by_a_silent_feed(first)
        _beats(first, _DWELL + 3 * _BEAT)
        assert first.bot(bot_id).state is S.RUNNING
        _publish_tick(first, _INSIDE_THE_RANGE)
        first.monotonic.advance(PRICE_STALE_AFTER_SECONDS)
        first.ticker.fire()
        first.deliver()
        assert first.bot(bot_id).state is S.AWAITING_RECOVERY

    with booted(exchange) as second:
        restored = second.bot(bot_id)
        assert restored.state is S.HALTED, "a restart is not a person's confirmation"
        assert len(restored.lifecycle.recovery_attempts) == 1
