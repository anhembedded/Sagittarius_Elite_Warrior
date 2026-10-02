"""
@brief `EquityFeed` — `EquitySampledEvent`, one place hears it
(`EPIC-021M`).

@details Same reasoning `OrderFeed` documents for its own single early
subscriber (`EPIC-021H`): `FuturesUserDataStream` is a shared
infrastructure singleton, not a Presenter's own background worker, so it
has no private-Qt-signal path to reach a screen safely — it must
emit onto `IEventBus`, and anything reached that way needs the
`QtEventBridge` hop `BaseFeed` provides (`architecture-rule.md` §6). A
distinct Feed from `OrderFeed`, not a fourth signal bolted onto it:
equity is account-level, not an order or a position — `OrderFeed`'s own
docstring scopes itself to "lệnh/vị thế".

`EPIC-028C` — one venue per Feed, the same rule `OrderFeed` follows: two
venues sample equity on one bus, and a screen shows its own venue's curve.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.equity_sampled_event import (
    EquitySampledEvent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.base_feed import BaseFeed
from sagittarius_engine.interfaces.i_event_bus import IEventBus


class EquityFeed(BaseFeed):
    """@brief Forwards `EquitySampledEvent`, already marshaled onto the
    main Qt thread."""

    #: Carries an `EquitySampledEvent`.
    equitySampled = Signal(object)

    def __init__(
        self,
        event_bus: IEventBus,
        venue: TradingVenue,
        parent: QObject | None = None,
    ) -> None:
        # Set before `super().__init__`: `BaseFeed.__init__` subscribes.
        self._venue = venue
        super().__init__(event_bus, parent)

    def _subscribe(self) -> None:
        self._events.on(EquitySampledEvent, self._on_equity_sampled)

    def _on_equity_sampled(self, event: Any) -> None:
        if event.venue is self._venue:
            self.equitySampled.emit(event)
