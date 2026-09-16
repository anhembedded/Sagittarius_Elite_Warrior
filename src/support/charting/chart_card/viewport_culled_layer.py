from __future__ import annotations

from abc import ABC, abstractmethod


class ViewportCulledLayer(ABC):
    """
    @brief Contract for any chart overlay layer whose item count can grow
    with backtest history (markers, background regions, ...): materialize
    only what the current viewport needs, never the full stored series.

    @details `viewport_windowing.py`'s own docstring states the intent this
    formalizes: "a new indicator or strategy signal overlay added later
    automatically windows the same way, with no per-indicator perf work
    needed." That intent held for candles/volume/indicator curves and for
    `MarkerLayer`, but `IndicatorManager.set_script_regions()` (BOT-032) was
    added as a few standalone methods that never went through it — every
    span for the whole backtest became a permanent `LinearRegionItem`, with
    no per-viewport culling at all. Measured cost of that gap (BUG-024): a
    2,065-span "Long Term Trend Zone" backtest took a pan/zoom step from
    ~26ms to ~235ms median, a ~9x regression, entirely from items that were
    never on screen.

    Subclassing this and registering the instance with
    `IndicatorManager._layers` is what prevents a repeat: `refresh_window()`
    is abstract, so a layer that forgets to implement real viewport culling
    fails at construction (`TypeError: Can't instantiate abstract class ...`)
    instead of shipping and only surfacing as a user-reported lag months
    later.
    """

    @abstractmethod
    def refresh_window(self, min_x: float, max_x: float) -> None:
        """Materializes only the items intersecting `[min_x, max_x]` (plus a
        small edge margin so items don't visibly pop in/out while panning).
        Called by `ChartCard` on every pan/zoom, and once right after this
        layer's content is (re)set."""

    @abstractmethod
    def clear_all(self) -> None:
        """Removes every item this layer owns, for every key — called when
        the chart itself is torn down or fully re-rendered."""
