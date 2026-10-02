"""
@brief `MarketTickFeed` — one subscriber to `MarketTickEvent`, many screens
display it (`architecture-rule.md` §6).

@details Before this existed, `DashboardPresenter` and the Trading screen's
presenter (`EPIC-021I`, retired in `EPIC-028M`) each called `self.event_bus.on(MarketTickEvent, ...)`
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

**Moved from `modules/trading/ui/` (`BOT-019`).** `MarketTickEvent` is
`market_data`'s own contract; a Feed normalizing one module's own event
belongs in that module's `ui/`, the same call `EPIC-025` PR 4.4a already
made for `sync_progress_feed.py`. `trading`'s two consumers
(`dashboard_presenter.py`, `trading_presenter.py`) read it from here via an
explicit `allowlist_module_boundaries.txt` entry, mirroring that same
precedent, rather than a copy living in each module.

**One market per Feed (`EPIC-028C`).** Spot and Futures candles share one
bus, and `BTCUSDT@1m` exists on both at two prices. Each screen builds its
Feed with the market it charts and hears only that market's ticks, so no
screen draws another market's candle as its own. The market is asked per
tick, not fixed at construction: the Dev Board's chart changes market with
its combo box while the Feed lives on.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.base_feed import BaseFeed
from sagittarius_engine.interfaces.i_event_bus import IEventBus


class MarketTickFeed(BaseFeed):
    """@brief Chuẩn hoá điểm nghe `MarketTickEvent` một lần, phát lại cho mọi màn."""

    #: Mang một `MarketTickEvent`.
    marketTick = Signal(object)

    def __init__(
        self,
        event_bus: IEventBus,
        market: Callable[[], MarketType],
        parent: QObject | None = None,
    ) -> None:
        # Set before `super().__init__`: `BaseFeed.__init__` subscribes.
        self._market = market
        super().__init__(event_bus, parent)

    def _subscribe(self) -> None:
        self._events.on(MarketTickEvent, self._on_market_tick)

    def _on_market_tick(self, event: Any) -> None:
        if event.market_type is self._market():
            self.marketTick.emit(event)
