"""
@brief `EquityFeed` — `EquitySampledEvent`, one place hears it
(`EPIC-021M`).

@details Same reasoning `OrderFeed` documents for its own single early
subscriber (`EPIC-021H`): `FuturesUserDataStream` is a shared
infrastructure singleton, not a Presenter's own background worker, so it
has no private-Qt-signal path to reach the Trading screen safely — it must
emit onto `IEventBus`, and anything reached that way needs the
`QtEventBridge` hop `BaseFeed` provides (`architecture-rule.md` §6). A
distinct Feed from `OrderFeed`, not a fourth signal bolted onto it:
equity is account-level, not an order or a position — `OrderFeed`'s own
docstring scopes itself to "lệnh/vị thế".
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from Sagittarius_Elite_Warrior.src.domain.events.equity_sampled_event import (
    EquitySampledEvent,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.base_feed import BaseFeed


class EquityFeed(BaseFeed):
    """@brief Forwards `EquitySampledEvent`, already marshaled onto the
    main Qt thread."""

    #: Carries an `EquitySampledEvent`.
    equitySampled = Signal(object)

    def _subscribe(self) -> None:
        self._events.on(EquitySampledEvent, self._on_equity_sampled)

    def _on_equity_sampled(self, event: Any) -> None:
        self.equitySampled.emit(event)
