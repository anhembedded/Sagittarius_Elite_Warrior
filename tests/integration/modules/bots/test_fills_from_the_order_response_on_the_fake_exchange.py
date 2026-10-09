"""`BOT-173` — a fill is counted from the order response, not only from the stream.

@details The composed app over the fake Binance server with a user-data stream
that delivers nothing (`booted(stream_up=False)`). The exchange's own answer to
a market order lists its trades by id; trading reports them the moment the
order returns, and the stream's report of the same trades, when it comes back,
changes nothing. The journey is the owner's: Start (the opening buy), then Stop
selling the base at market (the same market-order path a stop loss or a take
profit takes).
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from sagittarius_engine.interfaces.i_event_bus import IEventBus

from .grid_fake_exchange import FakeExchange, booted
from .test_a_start_with_the_user_stream_down_on_the_fake_exchange import _held, _start


def _fills_on_the_bus(app: object) -> list[OrderFilledEvent]:
    seen: list[OrderFilledEvent] = []
    bus = app.engine.context.container.resolve(IEventBus)  # type: ignore[attr-defined]
    bus.on(OrderFilledEvent, seen.append)
    return seen


def test_the_opening_buy_is_published_from_the_response_while_the_stream_is_down(
    exchange: FakeExchange,
) -> None:
    with booted(exchange, stream_up=False) as app:
        seen = _fills_on_the_bus(app)

        bot_id = _start(app)

        buys = [e for e in seen if e.order.side is OrderSide.BUY]
        assert buys, "no fill reached the bus although the stream said nothing"
        assert all(e.trade_id is not None for e in buys)
        assert _held(app) > 0
        # The bot's own ladder state learned the opening from the same record.
        assert app.runtime(bot_id).inventory == _held(app)


def test_the_streams_late_report_of_a_response_counted_trade_changes_nothing(
    exchange: FakeExchange,
) -> None:
    with booted(exchange, stream_up=False) as app:
        seen = _fills_on_the_bus(app)
        _start(app)
        trades_before = sorted(e.trade_id for e in seen if e.trade_id is not None)
        held_before = _held(app)

        app.deliver()  # the stream comes back and reports what it missed

        assert (
            sorted(e.trade_id for e in seen if e.trade_id is not None) == trades_before
        )
        assert len(set(trades_before)) == len(trades_before)
        assert _held(app) == held_before


def test_a_market_sell_at_stop_is_counted_from_its_response_with_the_stream_down(
    exchange: FakeExchange,
) -> None:
    with booted(exchange, stream_up=False) as app:
        seen = _fills_on_the_bus(app)
        bot_id = _start(app)
        held = _held(app)
        assert held > 0

        stopped = app.engine.dispatch(
            StopBotCommand, StopBotCommand(bot_id, BaseHandling.SELL_AT_MARKET)
        )

        assert stopped.accepted, stopped.message  # type: ignore[attr-defined]
        sells = [e for e in seen if e.order.side is OrderSide.SELL]
        assert sells, "the market sell was never counted"
        assert sum((e.fill_quantity for e in sells), Decimal(0)) > 0
        app.deliver()
        assert len([e for e in seen if e.order.side is OrderSide.SELL]) == len(sells)
