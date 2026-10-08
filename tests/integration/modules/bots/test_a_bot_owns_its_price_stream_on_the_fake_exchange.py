"""`EPIC-035A` — a running bot watches its stop loss with no chart anywhere.

The composed app over the fake Binance server (`grid_fake_exchange`). No Bots
screen is ever built in these journeys, so nothing but the bots module itself
can be streaming the symbol: if the price watch is not wired at boot, the stream
is never held and the stop loss is never evaluated. The websocket is the one
substitution (a verified `FakeMarketStream`), and the test publishes
`MarketTickEvent` on the bus exactly as the real adapter does.
"""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_price_watch import (
    bot_price_owner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.price_freshness import (
    PRICE_STALE_AFTER_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    Subscription,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
    TradingSwitchChangedEvent,
)

from .grid_fake_exchange import (
    GRID,
    SPOT,
    SYMBOL,
    BootedApp,
    FakeExchange,
    booted,
    ladder,
    resting,
)

S = BotLifecycleState
_AT = datetime(2026, 10, 8, 9, tzinfo=UTC)
#: `GRID`'s stop loss is `price:40000`, its range 48,000-52,000.
_BELOW_STOP_LOSS = 39_000.0
_INSIDE_THE_RANGE = 50_000.0


def _started(app: BootedApp) -> str:
    created = app.engine.dispatch(
        CreateBotCommand, CreateBotCommand("grid", "grid", SPOT, SYMBOL, GRID)
    )
    assert isinstance(created, BotCommandResult)
    assert created.bot_id is not None
    started = app.engine.dispatch(StartBotCommand, StartBotCommand(created.bot_id))
    assert isinstance(started, BotCommandResult)
    assert started.accepted, started.message
    return created.bot_id


def _publish_tick(app: BootedApp, price: float) -> None:
    """What the venue's kline websocket publishes for a trade at `price`."""
    app.engine.event_bus.emit(
        MarketTickEvent(
            MarketData(
                symbol=SYMBOL,
                interval="1m",
                open_time=_AT,
                open_price=price,
                high_price=price,
                low_price=price,
                close_price=price,
                volume=1.0,
                close_time=_AT,
                quote_asset_volume=1.0,
                number_of_trades=1,
                taker_buy_base_asset_volume=1.0,
                taker_buy_quote_asset_volume=1.0,
            ),
            market_type=MarketType.SPOT,
            market_data_venue=SPOT.market_data_venue,
        )
    )


def test_a_stop_loss_is_watched_with_no_chart_open(exchange: FakeExchange) -> None:
    with booted(exchange) as app:
        bot_id = _started(app)
        owner = bot_price_owner(BotId(bot_id))

        assert app.market.held_by(owner) == Subscription(
            owner, MarketType.SPOT, (SYMBOL,), TimeFrame.ONE_MINUTE
        )
        assert app.bot(bot_id).state is S.RUNNING

        _publish_tick(app, _BELOW_STOP_LOSS)

        assert app.bot(bot_id).state is S.STOPPED
        assert app.runtime(bot_id).reason is GridReason.STOP_LOSS
        assert resting(app.urls) == {}, "the stop took the ladder off the exchange"
        assert app.market.held_by(owner) is None, "a stopped bot releases its stream"


def test_a_bot_restored_after_a_restart_watches_its_stop_loss_before_trading_opens(
    exchange: FakeExchange,
) -> None:
    """The window the audit named: RECOVERING after a restart watched nothing."""
    with booted(exchange) as first:
        bot_id = _started(first)

    with booted(exchange) as second:
        assert second.bot(bot_id).state is S.RECOVERING
        owner = bot_price_owner(BotId(bot_id))
        assert second.market.held_by(owner) is not None

        _publish_tick(second, _BELOW_STOP_LOSS)
        second.deliver()

        assert second.bot(bot_id).state is S.STOPPED
        assert second.runtime(bot_id).reason is GridReason.STOP_LOSS
        assert resting(second.urls) == {}


def test_a_silent_feed_halts_the_bot_and_takes_its_ladder_off(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        bot_id = _started(app)
        assert resting(app.urls) == ladder(app.runtime(bot_id))
        _publish_tick(app, _INSIDE_THE_RANGE)

        app.monotonic.advance(PRICE_STALE_AFTER_SECONDS)
        app.ticker.fire()
        app.deliver()

        assert app.bot(bot_id).state is S.HALTED
        assert app.runtime(bot_id).reason is GridReason.PRICE_FEED_STALE
        assert resting(app.urls) == {}

        _publish_tick(app, _INSIDE_THE_RANGE)
        app.ticker.fire()
        assert app.bot(bot_id).state is S.HALTED, "a fresh tick does not resume it"


def test_enabling_trading_does_not_disturb_a_bot_that_hears_ticks(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as first:
        bot_id = _started(first)

    with booted(exchange) as second:
        _publish_tick(second, _INSIDE_THE_RANGE)
        second.engine.event_bus.emit(
            TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=SPOT)
        )
        second.ticker.fire()

        assert second.bot(bot_id).state is S.RUNNING
