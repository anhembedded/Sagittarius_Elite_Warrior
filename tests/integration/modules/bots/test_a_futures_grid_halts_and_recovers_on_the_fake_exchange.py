"""`EPIC-039H` - what a Futures Long Grid does when things go wrong, on the fake exchange.

@details The composed app over the Futures testnet fake with its bots running (`futures_bots_world`).
The cases that matter for a leveraged position: a halt never leaves it bare (decision O8), a
restart in the middle of the ladder recovers both the orders and the position, a user-stream gap
is reconciled against the exchange's position, and a start is refused for what stands in its way
(a position the bot did not open, settings the venue will not make the bot's, a plan whose
liquidation risk is refused).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
    TradingSwitchChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)

from .futures_bots_world import (
    GRID,
    OPENING_QUANTITY,
    ORDER_QUANTITY,
    BootedFuturesBots,
    booted_futures_bots,
)
from .futures_fake_exchange import FUTURES, SYMBOL
from .grid_fake_exchange import FakeExchange

S = BotLifecycleState
D = Decimal
_AT = datetime(2026, 10, 13, 9, tzinfo=UTC)


def _created(app: BootedFuturesBots, config: dict[str, str] | None = None) -> str:
    created = app.engine.dispatch(
        CreateBotCommand,
        CreateBotCommand("futures grid", "grid", FUTURES, SYMBOL, config or GRID),
    )
    assert isinstance(created, BotCommandResult)
    assert created.bot_id is not None, created.message
    return created.bot_id


def _start(app: BootedFuturesBots, bot_id: str) -> BotCommandResult:
    started = app.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))
    assert isinstance(started, BotCommandResult)
    return started


def _started(app: BootedFuturesBots, config: dict[str, str] | None = None) -> str:
    bot_id = _created(app, config)
    started = _start(app, bot_id)
    assert started.accepted, started.message
    return bot_id


def _publish_tick(app: BootedFuturesBots, price: float) -> None:
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
            market_type=MarketType.FUTURES_USD_M,
            market_data_venue=FUTURES.market_data_venue,
        )
    )


def _by_hand(app: BootedFuturesBots, quantity: str) -> None:
    """The user buys on the exchange's own website: a market order nobody here sent."""
    app.client().place_order(
        Order(
            client_order_id=ClientOrderId("web-by-hand"),
            symbol=SYMBOL,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=D(quantity),
        )
    )


def test_a_halt_by_a_silent_feed_ends_flat_with_no_orders_and_says_why(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app)
        app.move_price(62900)  # the 63,000 buy fills: the bot is long 0.018
        assert app.position() == OPENING_QUANTITY + ORDER_QUANTITY
        _publish_tick(app, 63000.0)

        app.monotonic.advance(PRICE_STALE_AFTER_SECONDS)
        app.ticker.fire()
        app.deliver()

        runtime = app.runtime(bot_id)
        assert runtime.reason is GridReason.PRICE_FEED_STALE
        assert app.bot(bot_id).state is S.STOPPED
        assert app.position() == 0, "a halt never leaves a leveraged position bare"
        assert app.resting() == {}
        assert runtime.inventory == 0
        assert "position is closed" in runtime.reason_detail


def test_a_restart_in_the_middle_of_the_ladder_recovers_its_orders_and_its_position(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as first:
        bot_id = _started(first)

    # While the app is closed the 65,000 sell fills (a long exit) and nobody hears it.
    futures.urls.futures_book.move_price(SYMBOL, D(65100))
    futures.urls.futures_book.drain_user_data_events()
    assert futures.urls.futures_book is not None

    with booted_futures_bots(futures) as second:
        assert second.bot(bot_id).state is S.RECOVERING
        assert len(second.resting()) == 3, "nothing was placed at boot"

        second.engine.event_bus.emit(
            TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=FUTURES)
        )

        runtime = second.runtime(bot_id)
        assert second.bot(bot_id).state is S.RUNNING
        assert second.position() == OPENING_QUANTITY - ORDER_QUANTITY
        assert runtime.inventory == second.position()
        assert {o.client_order_id for o in runtime.open_orders} == set(second.resting())
        prices = [price for _side, price, _reduce in second.resting().values()]
        assert len(prices) == len(set(prices)), "no level holds two orders"
        assert sorted(second.resting().values()) == [
            ("BUY", D(62000), False),
            ("BUY", D(63000), False),
            ("BUY", D(64000), False),
            ("SELL", D(66000), True),
        ]


def test_a_stream_gap_reconciles_the_position_and_places_the_missed_counter(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures, stream_up=False) as app:
        bot_id = _started(app)
        app.deliver()
        before = app.runtime(bot_id)

        futures.urls.futures_book.move_price(SYMBOL, D(62900))  # fills; nobody hears
        futures.urls.futures_book.drain_user_data_events()
        assert app.runtime(bot_id).inventory == before.inventory, "missed"

        app.engine.event_bus.emit(
            UserStreamHealthEvent(
                UserStreamState.CONNECTED, datetime.now(UTC), 1, venue=FUTURES
            )
        )

        runtime = app.runtime(bot_id)
        assert app.bot(bot_id).state is S.RUNNING
        assert runtime.inventory == app.position() == OPENING_QUANTITY + ORDER_QUANTITY
        assert {o.client_order_id for o in runtime.open_orders} == set(app.resting())
        assert ("SELL", D(64000), True) in app.resting().values(), "the counter"


def test_a_position_added_by_hand_halts_the_recovery_and_only_the_bots_own_is_closed(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as first:
        bot_id = _started(first)
    futures.urls.futures_book.move_price(SYMBOL, D(64000))
    with booted_futures_bots(futures) as second:
        _by_hand(second, "0.003")
        second.engine.event_bus.emit(
            TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=FUTURES)
        )

        runtime = second.runtime(bot_id)
        assert runtime.reason is GridReason.POSITION_MISMATCH
        assert second.bot(bot_id).state is S.STOPPED
        # The owner's decision (2026-10-13): the halt closes the position the bot built from its
        # own fills and leaves the one opened by hand, which it reports in words.
        assert second.position() == D("0.003")
        assert second.resting() == {}
        assert "was left open" in runtime.reason_detail
        assert "not this bot's" in runtime.reason_detail


def test_a_start_is_refused_for_a_position_the_bot_did_not_open(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        _by_hand(app, "0.002")
        bot_id = _created(app)

        started = _start(app, bot_id)

        assert not started.accepted
        assert "already holds a long position" in started.message
        assert app.resting() == {}
        assert app.position() == D("0.002"), "the bot sent nothing"


def test_a_start_is_refused_when_the_venue_will_not_make_its_settings_the_bots(
    futures: FakeExchange,
) -> None:
    book = futures.urls.futures_book
    assert book.change_leverage({"symbol": SYMBOL, "leverage": "5"})[0] == 200
    with booted_futures_bots(futures) as app:
        # A resting order of the user's own: the exchange refuses a leverage change with it.
        app.client().place_order(
            Order(
                client_order_id=ClientOrderId("web-resting"),
                symbol=SYMBOL,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                # 100 USDT, the symbol's minimum notional (`EPIC-037E`: the fake refuses less).
                quantity=D("0.002"),
                price=D("50000"),
                time_in_force=TimeInForce.GTC,
            )
        )
        bot_id = _created(app)

        _start(app, bot_id)

        runtime = app.runtime(bot_id)
        assert runtime.reason is GridReason.START_REFUSED
        assert "Nothing was changed" in runtime.reason_detail
        assert app.position() == 0
        assert list(app.resting().values()) == [("BUY", D(50000), False)]


def test_a_start_is_refused_when_the_plans_liquidation_risk_is_refused(
    futures: FakeExchange,
) -> None:
    config = {**GRID, "stop_loss": "off"}
    with booted_futures_bots(futures) as app:
        bot_id = _created(app, config)

        started = _start(app, bot_id)

        assert started.accepted, started.message
        runtime = app.runtime(bot_id)
        assert runtime.reason is GridReason.START_REFUSED
        assert "no exit on its losing side" in runtime.reason_detail
        assert app.position() == 0
        assert app.resting() == {}
