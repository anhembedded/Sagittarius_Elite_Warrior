"""`BUG-216` - a pause met while an `ACCOUNT_UPDATE`'s position is re-read does not end the stream session.

@details The re-read goes through the venue's gated client. While the exchange's pause runs it
raises `ExchangeRateLimitedError`; letting that out of `_handle_message` made the supervisor
report "connection lost" on a healthy socket and reconnect, and the reconnect (`CONNECTED`) made
every bot reconcile against the exchange the moment the pause ended: more weight, at the worst
time. The symbol waits for the next update instead.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.test_futures_user_data_stream import (
    _account_update,
    _live_position,
    _stream,
)


def _position_line(symbol: str) -> dict:
    return {"s": symbol, "pa": "0.002", "ep": "64105.35"}


def _the_exchange_asks_for_a_pause() -> ExchangeRateLimitedError:
    return ExchangeRateLimitedError(
        timedelta(seconds=30), banned=False, raw_message="no request is sent"
    )


async def test_a_pause_during_the_position_re_read_does_not_end_the_stream_session() -> (
    None
):
    """`BUG-216`: the re-read of an `ACCOUNT_UPDATE` meets the exchange's pause, and the error
    left `_handle_message`, so the supervisor reported "connection lost" on a healthy socket and
    reconnected; the reconnect then made every bot reconcile the moment the pause ended."""
    client = Mock()
    client.get_positions.side_effect = _the_exchange_asks_for_a_pause()
    stream, event_bus = _stream(client)
    seen: list = []
    event_bus.on(PositionChangedEvent, seen.append)

    await stream._handle_message(_account_update([_position_line("BTCUSDT")]))

    assert seen == [], "nothing is published on a position that was not read"


async def test_a_symbol_whose_re_read_a_pause_kept_is_read_with_the_next_update() -> (
    None
):
    client = Mock()
    client.get_positions.side_effect = [
        _the_exchange_asks_for_a_pause(),
        [_live_position("BTCUSDT")],
        [_live_position("ETHUSDT")],
    ]
    stream, event_bus = _stream(client)
    seen: list = []
    event_bus.on(PositionChangedEvent, seen.append)

    await stream._handle_message(_account_update([_position_line("BTCUSDT")]))
    await stream._handle_message(_account_update([_position_line("ETHUSDT")]))

    assert [call.args for call in client.get_positions.call_args_list] == [
        ("BTCUSDT",),
        ("BTCUSDT",),
        ("ETHUSDT",),
    ], "the kept symbol first, once, then the update's own"
    assert [e.position.symbol for e in seen] == ["BTCUSDT", "ETHUSDT"]
