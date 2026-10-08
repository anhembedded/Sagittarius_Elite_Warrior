"""`EPIC-028C` — emits one venue's account events onto the event bus.

@details Futures and Spot user-data streams run together and publish onto one
bus. Each stream is handed the emitter of its own venue instead of the raw
bus, so the venue is stamped in exactly one place and no stream can emit a
fill, a position or an equity sample without saying whose it is. A screen's
feeds then forward only their own venue's events (`ui/screen_venue_feeds.py`).

`EPIC-029` ADR D6 — a fill or an end is applied to the venue's owner books
(`OwnerBooks`) **before** it is published, so any subscriber, a bot placing
its counter order synchronously in its handler included, sees a book that
already holds it. Trading is never a peer subscriber of its own events for
this: the order of the two steps is this file's, not the bus's.

Plausible extensions, each one new method here (`architecture-rule.md`
§7.2.1): an open-order change once a stream reports one to the UI
(`EPIC-028E`), a balance-changed event (`EPIC-028D`).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_books import (
    OwnerBooks,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.equity_sample import (
    EquitySample,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.equity_sampled_event import (
    EquitySampledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_ended_event import (
    OrderEndedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_closed_event import (
    PositionClosedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus


class VenueEventEmitter:
    """Every account event one venue's stream emits, with that venue on it."""

    def __init__(
        self, event_bus: IEventBus, venue: TradingVenue, owner_books: OwnerBooks
    ) -> None:
        self._event_bus = event_bus
        self._venue = venue
        self._owner_books = owner_books

    @property
    def venue(self) -> TradingVenue:
        return self._venue

    def order_filled(
        self,
        order: Order,
        fill: tuple[Decimal, Decimal],
        fee: tuple[Decimal, str] | None = None,
        trade_id: int | None = None,
    ) -> None:
        """`fill` is `(price, quantity)` of this one fill; `fee` is
        `(amount, asset)` where the venue reports one (Spot), else `None`;
        `trade_id` is the exchange's id of this fill where the venue reports
        one (Spot), which the owner books and the bots use to count a fill once (`EPIC-035P`)."""
        fill_price, fill_quantity = fill
        self._owner_books.apply_fill(order, fill, fee, trade_id)
        self._event_bus.emit(
            OrderFilledEvent(
                order=order,
                fill_price=fill_price,
                fill_quantity=fill_quantity,
                fee_amount=fee[0] if fee is not None else None,
                fee_asset=fee[1] if fee is not None else None,
                trade_id=trade_id,
                venue=self._venue,
            )
        )

    def order_ended(self, order: Order) -> None:
        """`EPIC-028I` — `order` is over without having filled whole
        (`ended_without_filling`)."""
        self._owner_books.apply_end(order)
        self._event_bus.emit(OrderEndedEvent(order=order, venue=self._venue))

    def equity_sampled(self, sample: EquitySample) -> None:
        self._event_bus.emit(EquitySampledEvent(sample=sample, venue=self._venue))

    def position_changed(self, position: LivePosition) -> None:
        self._event_bus.emit(PositionChangedEvent(position=position, venue=self._venue))

    def position_closed(self, symbol: str) -> None:
        self._event_bus.emit(PositionClosedEvent(symbol=symbol, venue=self._venue))

    def user_stream_health(
        self, state: UserStreamState, since: datetime, attempt: int = 0
    ) -> None:
        """`EPIC-035B` — where this venue's user-data stream is now."""
        self._event_bus.emit(
            UserStreamHealthEvent(
                state=state, since=since, attempt=attempt, venue=self._venue
            )
        )
