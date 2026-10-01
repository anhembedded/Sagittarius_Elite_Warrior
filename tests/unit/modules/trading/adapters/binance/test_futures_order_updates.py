"""`EPIC-028R` — the Futures user-data stream reports a triggered stop's
fill as the order the app placed: the `ALGO_UPDATE` naming the regular order
it placed (`ai`) links that order to the app's client order id.

@details Payloads are Binance's documented `ALGO_UPDATE` and
`ORDER_TRADE_UPDATE` shapes; no live stream verified them."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_order_updates import (
    FuturesOrderUpdates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_user_data_stream import (
    FuturesUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_event_emitter import (
    VenueEventEmitter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

_ID = "SEW-a91f4c72e0b8"


def _fill_of(order_id: int, client_order_id: str) -> dict[str, Any]:
    """An `ORDER_TRADE_UPDATE` fill, Binance's documented shape."""
    return {
        "e": "ORDER_TRADE_UPDATE",
        "o": {
            "s": "BTCUSDT",
            "c": client_order_id,
            "S": "BUY",
            "o": "LIMIT",
            "q": "0.002",
            "p": "65100",
            "X": "FILLED",
            "x": "TRADE",
            "i": order_id,
            "L": "65100",
            "l": "0.002",
            "T": 1759320200000,
        },
    }


def _triggered(placed_order_id: int) -> dict[str, Any]:
    return {
        "e": "ALGO_UPDATE",
        "T": 1759320100000,
        "o": {
            "caid": _ID,
            "o": "STOP",
            "s": "BTCUSDT",
            "S": "BUY",
            "q": "0.002",
            "X": "TRIGGERED",
            "ai": str(placed_order_id),
        },
    }


def _updates() -> tuple[FuturesOrderUpdates, list[OrderFilledEvent]]:
    bus = MemoryEventBus()
    fills: list[OrderFilledEvent] = []
    bus.on(OrderFilledEvent, fills.append)
    return (
        FuturesOrderUpdates(VenueEventEmitter(bus, TradingVenue.FUTURES_TESTNET)),
        fills,
    )


def test_a_triggered_stops_fill_is_reported_as_the_order_the_app_placed() -> None:
    updates, fills = _updates()

    updates.on_algo_update(_triggered(8389765519))
    updates.on_order_trade_update(_fill_of(8389765519, "exchange-made-id"))

    assert [f.order.client_order_id for f in fills] == [_ID]


async def test_the_stream_routes_algo_updates_to_the_order_updates() -> None:
    """The wiring: `FuturesUserDataStream` hands `ALGO_UPDATE` on, so a
    triggered stop's fill arrives under the app's id end to end."""
    bus = MemoryEventBus()
    fills: list[OrderFilledEvent] = []
    bus.on(OrderFilledEvent, fills.append)
    stream = FuturesUserDataStream(
        VenueEventEmitter(bus, TradingVenue.FUTURES_TESTNET),
        Mock(),
        Mock(),
        Mock(),
        TradingSessionState(),
        EquityCurveRecorder(),
    )

    await stream._handle_message(_triggered(8389765519))
    await stream._handle_message(_fill_of(8389765519, "exchange-made-id"))

    assert [f.order.client_order_id for f in fills] == [_ID]


def test_a_fill_of_any_other_order_keeps_its_own_id() -> None:
    updates, fills = _updates()

    updates.on_algo_update(_triggered(8389765519))
    updates.on_order_trade_update(_fill_of(42, "SEW-other"))

    assert [f.order.client_order_id for f in fills] == ["SEW-other"]


def test_a_malformed_algo_update_is_logged_and_dropped(caplog) -> None:
    updates, fills = _updates()
    malformed = _triggered(1)
    del malformed["o"]["caid"]

    updates.on_algo_update(malformed)
    updates.on_order_trade_update(_fill_of(1, "exchange-made-id"))

    assert "Could not parse ALGO_UPDATE" in caplog.text
    assert [f.order.client_order_id for f in fills] == ["exchange-made-id"]
