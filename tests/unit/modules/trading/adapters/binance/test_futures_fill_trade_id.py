"""`EPIC-039D` — a Futures fill carries the exchange's trade id (`t`), so a fill the
stream reports twice is counted once, as `EPIC-035P` does for Spot.

@details `EPIC-039C` found the app counting a duplicated Futures report twice: no
trade id was read, so nothing recognised the second record. Payloads are Binance's
documented `ORDER_TRADE_UPDATE` shape; the parser here owns `t` only (`n`/`N`/`rp`
belong to `EPIC-039G`)."""

from __future__ import annotations

from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_order_updates import (
    FuturesOrderUpdates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.user_data_event_parser import (
    fill_trade_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_event_emitter import (
    VenueEventEmitter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_books import (
    OwnerBooks,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus


def _fill(trade_id: int) -> dict[str, Any]:
    return {
        "e": "ORDER_TRADE_UPDATE",
        "o": {
            "s": "BTCUSDT",
            "c": "SEW-a91f4c72e0b8-1",
            "S": "BUY",
            "o": "LIMIT",
            "q": "0.002",
            "p": "65100",
            "X": "FILLED",
            "x": "TRADE",
            "i": 11,
            "L": "65100",
            "l": "0.002",
            "t": trade_id,
            "T": 1759320200000,
        },
    }


def test_the_trade_id_of_a_fill_is_the_payloads_t() -> None:
    assert fill_trade_id(_fill(4821)) == 4821


def test_a_payload_without_a_trade_has_no_trade_id() -> None:
    payload = _fill(0)
    assert fill_trade_id(payload) is None
    del payload["o"]["t"]
    assert fill_trade_id(payload) is None


def test_a_futures_fill_reported_twice_is_one_event_with_its_trade_id() -> None:
    bus = MemoryEventBus()
    fills: list[OrderFilledEvent] = []
    bus.on(OrderFilledEvent, fills.append)
    updates = FuturesOrderUpdates(
        VenueEventEmitter(bus, TradingVenue.FUTURES_TESTNET, OwnerBooks())
    )

    updates.on_order_trade_update(_fill(4821))
    updates.on_order_trade_update(_fill(4821))
    updates.on_order_trade_update(_fill(4822))

    assert [fill.trade_id for fill in fills] == [4821, 4822]
