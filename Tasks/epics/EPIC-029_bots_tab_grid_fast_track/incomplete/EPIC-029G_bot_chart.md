# EPIC-029G — Every bot has its own chart, and one Grid overlay draws the planner, the backtest and the running bot

**Status:** 🔵 Backlog
**Source:** [`PRO-006`](../../../proposal/PRO-006.md). The user's words, 2026-10-03: *"Bot phải có
cái chart nữa để vẽ những chỉ báo đặc trưng của bot đó"* ("a bot must have its own chart to draw
that bot's own indicators"). The design is in ADR D15 and D16.
**Risk:** 🟡 — it moves the desks' live-chart coordinator into `support/charting`, so the desks'
charts are the regression surface.
**Complexity:** M — move one coordinator behind an ABC, add one chart layer, compute one overlay,
and draw it in three places.
**Epic:** [EPIC-029](../README.md)
**Depends on:** `EPIC-029C` (plan and levels for the overlay data).

---

## 1. Context and problem

Three things stand in the way of a bot chart:

- **`ChartCard` has no horizontal price lines and cannot grow.** It draws candles, indicator lines,
  vertical regions and markers (`src/support/charting/chart_card/chart_card.py:705-760`). It is
  881 lines, baselined, and cannot grow (`baseline_god_files.json`). A Grid's levels, stop loss
  and take profit are horizontal lines.
- **The desk's live chart is locked inside trading.** History and live candles come from
  `ChartCoordinator` (229 lines), which lives in trading's ui
  (`trading/ui/desk/desk_screen/chart_coordinator.py`). The `bots` module cannot import it.
- **The tick feed sits behind a frozen allowlist.** `MarketTickFeed` is reached by trading only
  through an allowlist line that may only shrink.

## 2. Acceptance criteria

- [ ] **The move.** `ChartCoordinator` lives in `src/support/charting/live_chart/`, behind a
  support-owned `CandleFeed` ABC with `load_history(...)` and `start_stream(owner_id, ...)`.
  - The trading desks use it through a small adapter over `IHistoricalKlines` and `IMarketStream`.
  - Every existing desk chart test passes unmodified.
  - The old path is deleted, with no duplicate left behind.
- [ ] **Horizontal lines.** `PriceLevelLayer` draws keyed horizontal lines: price, colour, style
  and an optional right-edge label.
  - It attaches to a `ChartCard`'s price plot through its public API.
  - `chart_card.py`'s line count does not grow; the ratchet passes.
- [ ] **The overlay data.** `GridOverlay` is computed in `bots/domain`, Qt-free, from a plan plus
  an optional runtime or backtest result. It holds:
  - the range edges;
  - each level, with its side and state (resting buy, resting sell, empty or partial);
  - the stop loss and take profit;
  - the fills;
  - the average cost;
  - optional suggestion bands (the ATR range, the Bollinger upper and lower bands).
- [ ] **One drawer.** One `GridOverlayDrawer` in `bots/ui` draws a `GridOverlay` onto a `ChartCard`
  and a `PriceLevelLayer`. The planner preview, the backtest result view and the running bot's
  chart all call it, and a test proves the three draw identical items for the same overlay.
- [ ] **Live updates.** The running bot's chart streams live candles under its own owner id,
  `bot.<id>`. Ticks reach it through the bots event handler marshalled by a Qt signal, not through
  `MarketTickFeed`, and no allowlist entry is added.

## 3. Design

- **Move shared logic up** (`fix-bug-rule.md` §1, P6) rather than copy it. The ABC lives in
  support, so support never imports a module. The modules' `ui/` packages implement the adapters
  with the market_data contracts they already depend on.
- **`PriceLevelLayer`** owns `pg.InfiniteLine(angle=0)` items per key and replaces them on each
  `set_levels(key, levels)`. It holds no state beyond the drawn items.
- **The overlay** is data only: a frozen dataclass with tuples. Computing it lives with the plan
  and the runtime, never in Qt code.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/support/charting/live_chart/chart_coordinator.py`, `candle_feed.py` (new, moved) | the shared coordinator and its ABC |
| `src/support/charting/chart_card/price_level_layer.py` (new) | horizontal lines |
| `src/modules/trading/ui/desk/desk_screen/chart_coordinator.py` | deleted, after the move |
| `src/modules/trading/ui/desk/desk_screen/desk_chart.py` | uses the support coordinator with an adapter |
| `src/modules/bots/domain/grid/grid_overlay.py` (new) | overlay data |
| `src/modules/bots/ui/chart/grid_overlay_drawer.py`, `bot_chart.py` (new) | drawer, bot chart |
| `tests/unit/support/charting/**`, `tests/unit/modules/bots/**` | below |

## 5. Testing

- **Unit:**
  - `PriceLevelLayer` replaces lines by key, and leaves none behind after a clear;
  - the overlay is computed from the report's example plan;
  - the drawer produces identical items across the three surfaces.
- **Regression:** the desk chart tests pass unmodified after the move. The ratchet shows
  `chart_card.py` did not grow.
- **Preview:** the bot chart in `preview.py` draws a sample Grid.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
