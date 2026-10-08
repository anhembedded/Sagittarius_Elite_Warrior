"""`EPIC-035B` — the user-data stream's gap, in the composed app, on the fake exchange.

`create_app()` builds trading (the Spot adapters, the owner budget, the venue
emitter) and bots (executors, the router and the user-stream watch); only the
network is the fake server. The fake speaks no websocket, so a *gap* is made
the way a real one happens: the exchange fills an order and its
`executionReport` is never delivered. The stream's own health is told to the
bus through the venue's real `VenueEventEmitter`, the call `SpotUserDataStream`
makes when it reconnects.

What each journey proves is the whole path: health event → `UserStreamWatch` →
the bot's executor → `GridReconciler` → REST reads against the fake → the
counter order on the exchange.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.user_stream_watch import (
    DEFAULT_USER_STREAM_LIMITS,
    UserStreamWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)

from .grid_fake_exchange import (
    SYMBOL,
    BootedApp,
    FakeExchange,
    booted,
    ladder,
    resting,
    sides_by_price,
)
from .test_grid_bot_against_fake_server import _started

S = BotLifecycleState


def _lose_the_stream(app: BootedApp, price: int) -> None:
    """The exchange moves and fills, and the stream, being down, says nothing."""
    app.urls.spot_account.set_last_price(SYMBOL, Decimal(price))
    app.urls.spot_account.drain_user_data_events()


def _stream_says(app: BootedApp, state: UserStreamState, since_ago: int = 0) -> None:
    clock_now = app.engine.context.event_bus  # the bus the real emitter publishes on
    assert clock_now is not None
    now = app.stream._supervisor._now()
    app.stream._events.user_stream_health(
        state, now - timedelta(seconds=since_ago), attempt=1
    )


def _the_watch(app: BootedApp) -> UserStreamWatch:
    [handler] = app.engine.context.event_bus.subscriptions()[
        UserStreamHealthEvent.__name__
    ]
    watch = handler.__self__
    assert isinstance(watch, UserStreamWatch)
    return watch


def test_a_fill_missed_while_the_stream_was_down_places_its_counter_on_reconnect(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        bot_id = _started(app)
        assert app.bot(bot_id).state is S.RUNNING
        before = app.runtime(bot_id)
        assert Decimal(48800) in sides_by_price(before)

        _lose_the_stream(app, 48700)  # the buy at 48,800 fills; nobody hears

        assert Decimal(49600) not in sides_by_price(app.runtime(bot_id)), "missed"
        _stream_says(app, UserStreamState.CONNECTED)

        runtime = app.runtime(bot_id)
        assert app.bot(bot_id).state is S.RUNNING
        assert sides_by_price(runtime)[Decimal(49600)] == "SELL", "the counter"
        assert Decimal(48800) not in sides_by_price(runtime)
        assert resting(app.urls) == ladder(runtime), "the ladder is the exchange's"
        assert runtime.inventory > before.inventory


def test_a_reconnect_with_nothing_missed_changes_nothing(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        bot_id = _started(app)
        before = app.runtime(bot_id)
        orders = resting(app.urls)

        _stream_says(app, UserStreamState.CONNECTED)
        _stream_says(app, UserStreamState.CONNECTED)

        assert app.bot(bot_id).state is S.RUNNING
        assert app.runtime(bot_id) == before
        assert resting(app.urls) == orders


def test_a_stream_down_too_long_parks_the_ladder_and_a_return_does_not_resume_it(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        bot_id = _started(app)
        limit = int(DEFAULT_USER_STREAM_LIMITS.down_limit.total_seconds())

        _stream_says(app, UserStreamState.RECONNECTING, since_ago=limit + 1)
        _the_watch(app).check()

        assert app.bot(bot_id).state is S.HALTED
        assert app.runtime(bot_id).reason is GridReason.USER_STREAM_DOWN
        assert resting(app.urls) == {}, "the ladder was taken off the exchange"

        _stream_says(app, UserStreamState.CONNECTED)
        _the_watch(app).check()

        assert app.bot(bot_id).state is S.HALTED, "the owner resumes, not the stream"
        assert resting(app.urls) == {}
