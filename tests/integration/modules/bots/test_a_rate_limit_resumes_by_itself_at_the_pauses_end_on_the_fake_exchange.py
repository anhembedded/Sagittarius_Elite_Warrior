"""`EPIC-042F` - a Spot grid met by the exchange's pause waits it out and resumes with no person.

The composed app over the fake Binance server. A counter order's connection check is answered
with a 429 and a `Retry-After`: the bot waits in AWAITING_RECOVERY (it used to be HALTED with a
timer), nothing is sent while the pause runs, and once the pause is over and the dwell has passed
the recovery run takes the old ladder off, derives the inventory from the exchange and lays a fresh
one. The venue's gate keeps its own clock (`RateLimitGate`, the real one), so the journey lifts it
the moment the bot's clock says the pause is over: the gate has its own tests; here the pause's end
is the bot's.
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limit_gate import (
    RateLimitGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)

from .grid_fake_exchange import SPOT, BootedApp, FakeExchange, booted, resting
from .quiet_exchange_readers import (
    NO_PERIODIC_REFRESH,
    forget_the_kept_connection,
    quiet_the_fill_summaries,
)
from .test_a_bot_owns_its_price_stream_on_the_fake_exchange import (
    _INSIDE_THE_RANGE,
    _publish_tick,
    _started,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sanity"))
from fake_exchange.server import FaultAnswer

S = BotLifecycleState
_BEAT = 5
#: What the exchange said: wait this long.
_PAUSE = 30
#: A price that fills the BUY at 48,800: its counter order must then be placed.
_FILLS_A_BUY = 48_800


def _beats(app: BootedApp, seconds: int) -> None:
    for _ in range(0, seconds, _BEAT):
        app.monotonic.advance(_BEAT)
        _publish_tick(app, _INSIDE_THE_RANGE)
        app.ticker.fire()
        app.deliver()


class _Lines(logging.Handler):
    """What the bot's logger said, kept: the `App.*` loggers do not propagate to `caplog`."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


def _held_by_the_pause(app: BootedApp) -> str:
    bot_id = _started(app)
    # The account stream is up, as it is during a pause (the pause refuses requests, not sockets).
    app.engine.event_bus.emit(
        UserStreamHealthEvent(
            UserStreamState.CONNECTED, datetime.now(UTC), 1, venue=SPOT
        )
    )
    app.deliver()
    quiet_the_fill_summaries(app.engine.context.container)
    forget_the_kept_connection(app.engine.context.container, SPOT)
    app.urls.faults.queued.append(
        FaultAnswer(
            "/api/v3/ping",
            status=429,
            body={"code": -1003, "msg": "Too many requests."},
            headers={"Retry-After": str(_PAUSE)},
        )
    )

    app.move_price(_FILLS_A_BUY)

    runtime = app.runtime(bot_id)
    assert app.bot(bot_id).state is S.AWAITING_RECOVERY, runtime.reason_detail
    assert runtime.reason is GridReason.RATE_LIMITED
    assert "resumes by itself" in runtime.reason_detail
    return bot_id


def test_the_bot_waits_for_the_pause_then_lays_a_fresh_ladder_with_no_person(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    lines = _Lines()
    logger = logging.getLogger("App.Bots.GridExecutor")
    logger.addHandler(lines)
    try:
        with booted(exchange, limits=NO_PERIODIC_REFRESH) as app:
            bot_id = _held_by_the_pause(app)
            old_ladder = set(resting(app.urls))
            assert old_ladder, "the pause sent no cancel: the ladder rests through it"
            mark = len(app.urls.requests)

            _beats(app, _PAUSE - _BEAT)
            assert app.bot(bot_id).state is S.AWAITING_RECOVERY, "the pause still runs"
            assert not [
                (method, path)
                for method, path in app.urls.requests[mark:]
                if method in ("POST", "DELETE")
            ], "nothing is placed or cancelled while the pause runs"
            assert not app.bot(bot_id).lifecycle.recovery_attempts

            monkeypatch.setattr(RateLimitGate, "remaining", lambda _gate: 0.0)
            _beats(app, 4 * _BEAT)

            assert app.bot(bot_id).state is S.RUNNING
            assert len(app.bot(bot_id).lifecycle.recovery_attempts) == 1
            laid = set(resting(app.urls))
            assert laid, "a fresh ladder rests on the exchange"
            assert not old_ladder & laid, "none of the old orders remains"
    finally:
        logger.removeHandler(lines)
    tagged = [line for line in lines.lines if "[bot-halt-recovery]" in line]
    assert any("rate_limited is transient" in line for line in tagged)
    assert any("recovery attempt 1 of 3" in line for line in tagged)
    assert any("recovered from rate_limited" in line for line in tagged)


def test_the_recovered_run_keeps_what_its_fills_paid_and_cost(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`BUG-268` - the recovery's STARTING -> RUNNING lays a fresh ladder over the run it resumes:
    the commissions the run's fills paid, and the cost those fees sit in, are the run's, not the
    new ladder's. The owner's Futures bot showed 0.50 of fees after one recovery, the fees of the
    nine fills that followed it, against about 2.13 for the run."""
    with booted(exchange, limits=NO_PERIODIC_REFRESH) as app:
        bot_id = _held_by_the_pause(app)
        before = app.runtime(bot_id)
        assert before.commissions > 0, "the opening and the BUY at 48,800 paid fees"

        _beats(app, _PAUSE - _BEAT)
        monkeypatch.setattr(RateLimitGate, "remaining", lambda _gate: 0.0)
        _beats(app, 4 * _BEAT)

        assert app.bot(bot_id).state is S.RUNNING
        after = app.runtime(bot_id)
        assert after.commissions == before.commissions
        assert after.inventory == before.inventory
        assert after.cost == before.cost
        assert after.realised_total == before.realised_total
