"""
@brief `MarketTickFeed` — one subscriber to `MarketTickEvent`, many screens
display it (`architecture-rule.md` §6).

@details Before this existed, `DashboardPresenter` and `TradingPresenter`
(`EPIC-021I`) each called `self.event_bus.on(MarketTickEvent, ...)`
directly — the exact duplication `tests/unit/test_event_flow_guards.py`'s
`test_one_event_is_not_subscribed_by_two_presenters` exists to catch
(named after the real `HealthUpdatedEvent` defect `EPIC-008G` had to fix,
where two independently-drifted presenters each re-implemented their own
normalization and one silently lost its `Container`). Both screens now
connect to this Feed's `marketTick` signal instead.

Deliberately re-emits the raw `MarketTickEvent` rather than a normalized
DTO — same reasoning `OrderFeed`'s own docstring gives for
`OrderFilledEvent`/`PositionChangedEvent`: `MarketTickEvent` is already a
stable, well-named domain event (`market_data: MarketData`), and every
subscriber reads a different subset of it (Dev Board keys per-symbol
chart cards; Trading filters to its own single active symbol), so there is
nothing to normalize away without losing information a subscriber needs.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from Sagittarius_Elite_Warrior.src.domain.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.base_feed import BaseFeed


class MarketTickFeed(BaseFeed):
    """@brief Chuẩn hoá điểm nghe `MarketTickEvent` một lần, phát lại cho mọi màn."""

    #: Mang một `MarketTickEvent`.
    marketTick = Signal(object)

    def _subscribe(self) -> None:
        self._events.on(MarketTickEvent, self._on_market_tick)

    def _on_market_tick(self, event: Any) -> None:
        self.marketTick.emit(event)
