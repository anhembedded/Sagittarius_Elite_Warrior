# EPIC-029G — Every bot has its own chart, and one Grid overlay draws the planner, the backtest and the running bot

**Status:** ✅ Done (2026-10-04)
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

- [x] **The move.** `ChartCoordinator` lives in `src/support/charting/live_chart/`, behind a
  support-owned `CandleFeed` ABC with three operations: `load_history(...)`, `sync(...)` (the desks
  sync before reading today, `chart_coordinator.py:47-50,163`) and `start_stream(owner_id, ...)`.
  The worker runner, today the engine's `IThreadManager`, is injected (ADR D15, review round 1).
  - The trading desks use it through a small adapter over `IHistoricalKlines` and `IMarketStream`.
  - Every existing desk chart test passes unmodified.
  - The old path is deleted, with no duplicate left behind.
- [x] **Horizontal lines.** `PriceLevelLayer` draws keyed horizontal lines: price, colour, style
  and an optional right-edge label.
  - It attaches to a `ChartCard`'s price plot through its public API.
  - `chart_card.py`'s line count does not grow; the ratchet passes.
- [x] **The overlay data.** `GridOverlay` is computed in `bots/domain`, Qt-free, from a plan plus
  an optional runtime or backtest result. It holds:
  - the range edges;
  - each level, with its side and state (resting buy, resting sell, empty or partial);
  - the stop loss and take profit;
  - the fills;
  - the average cost;
  - optional suggestion bands (the ATR range, the Bollinger upper and lower bands).
- [x] **One drawer.** One `GridOverlayDrawer` in `bots/ui` draws a `GridOverlay` onto a `ChartCard`
  and a `PriceLevelLayer`. The planner preview, the backtest result view and the running bot's
  chart all call it, and a test proves the three draw identical items for the same overlay.
- [x] **Live updates.** The running bot's chart streams live candles under its own owner id,
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

Five commits on `claude/wizardly-cerf-fc5b5x` (PR3 of EPIC-029):

| Commit | What it delivered |
| :--- | :--- |
| `fix(trading): do not report an asset as sold when every split part was dust` | Carried from the PR #320 re-review: an asset whose split parts were all below the exchange minimum is reported as dust only. Red test first. |
| `refactor(charting): move the desk's live chart coordinator into support` | `ICandleFeed` (`support/charting/contracts/`), `LiveChartCoordinator` (`support/charting/live_chart/`), `MarketDataCandleFeed` (`market_data/contracts/`). The trading file is gone, with no copy left; its tests moved with it, every assertion unchanged. |
| `feat(charting): draw keyed horizontal price lines and bands on a chart` | `PriceLevelLayer`; `chart_card.py` unchanged. |
| `feat(bots): compute a Grid's chart overlay from its plan and its activity` | `BotOverlay` gains bands, fills and three roles; `grid_overlay(GridOverlaySource)`; `GridKind.overlay` delegates to it. |
| `feat(bots): give every bot its own chart, drawn by one overlay drawer` | `LiveCandleChart` (shared by `DeskChart` and `BotChart`), `overlay_items`, `BotOverlayDrawer`, `BotChart`, `BotTickFeed`, the preview. |

**Departures from the task text, each for a reason:**

- **`ICandleFeed`, not `CandleFeed`, in `support/charting/contracts/`.** The repository names a port `I*` in an `i_*.py` file under `contracts/` (`test_contract_file_naming.py`, `BUG-127`). It has four operations, not three: `stop_stream` releases an owner's stream, which the desk's `stop()` always did.
- **One adapter, in `market_data/contracts/`, not one per module `ui/`.** The adapter wraps market_data's own three ports. Two copies (trading's and bots') would have been identical, so it sits beside the ports it adapts, and both modules build it.
- **The coordinator's own tests moved with it** (`tests/unit/support/charting/live_chart/`). They now build it over `MarketDataCandleFeed` with the same verified fakes, and every assertion is the one it was. The desk chart tests run unmodified.
- **`LiveCandleChart`, a shared base, was added.** The first `BotChart` repeated seven of `DeskChart`'s members, and the duplicated-member census rose from 64 to 73. The loading and candle code moved up into one base that both charts subclass. The census fell to 63, and its baseline is tightened to 63.
- **The Grid overlay is a `BotOverlay`, not a separate `GridOverlay` type.** The kind seam (`IBotKind.overlay`) already returns `BotOverlay`. One shape keeps the drawer kind-agnostic: it styles by role, so a later kind reuses it by reusing roles.
- **The drawer is `BotOverlayDrawer` in `bots/ui/chart/`,** for the same reason.
- **"Three surfaces" are three uses of one `BotChart`:** `show_symbol` (the planner preview), `draw_history` (the backtest result) and `follow` (the running bot). `029D` and `029F`, which build those screens, embed it. The identity test draws one overlay through all three and compares both the items and what lands on each card.
- **Ticks reach a bot chart through `BotTickFeed`.** It is the bots module's own `BaseFeed` over market_data's published `MarketTickEvent`; neither `MarketTickFeed` nor an allowlist entry is involved.
- **The ATR suggestion is two zones, one per edge.** Each zone is where an edge sits if the range is `range_atr_low` to `range_atr_high` daily ATRs wide around the last price: the band the range-versus-ATR check judges. The Bollinger band is drawn when the caller computes one; `MarketView` carries no candles, so the planner preview passes none today.
- **The chart theme gained named series colours** (stop loss, range edge, average cost, bands), so no new file reads the palette (`test_app_styling_only_shrinks.py`).
- **`bots` now declares `market_data` as a dependency** (`test_module_declarations.py`).
- **The preview registers `modules/bots/ui`** in `scripts/preview_qml.py`.

**`DeskChart` behaviour, three small changes from the move** (none harmful, found by the review):
the armed strategy's overlay advances on a closed candle *after* the candle is drawn (it ran just
before); a timeframe change with no symbol shown no longer restarts with an empty symbol; and
`apply_candle` filters on the interval as well, which repeats the desk's own `_on_tick` filter.

**Review round 1 (PR #321): PASS, three should-fix and four nits, all addressed in one commit.**
- **The range edge's label read as a blank box** (light text on a light fill). A label's text is now
  whichever of light and dark contrasts more with its fill (WCAG 2 ratio, `label_text_color`). The
  earlier claim that the preview was inspected for this was wrong: it was looked at only before the
  range edges were drawn.
- **HLD 03** names `MarketDataCandleFeed` as the consumer of `IMarketDataSync` and `IMarketStream`,
  and records it as the one adapter in a module's `contracts/`, an exception and not a precedent.
- **The ADR D15 row** now records what shipped: `ICandleFeed` with four operations, one adapter, and
  the cleaner factory shape left for later.
- `029D` and `029F` gained the criterion that they host `BotChart` and draw only through it.
- Nits: the coordinator's mapped history is drawn as it comes (no second mapping on the Qt thread); a
  bot chart is quiet again after `shutdown()`; an ATR zone never goes below zero and the docstring says
  the centring is the drawing's own suggestion; the preview's average cost no longer hides under a level.

**Review round 2 (PR #321): one blocking finding, which round 1's own fix introduced.**
- **R2-1: a stopped bot chart kept drawing the bus's ticks, and following again drew each closed
  candle twice.** `shutdown()` never disconnected the Feed's `candle` signal, and once round 1 made
  the chart quiet again, a second `follow()` connected the same slot a second time. `BotChart` now
  keeps the Feed it follows, and `shutdown()` disconnects it before going quiet. A red test pins each
  case: no tick is drawn after `shutdown()`, and one closed candle after a re-follow is one bar.
- Nit: going quiet (release the stream, clear live) is `LiveCandleChart._go_quiet()`, so the live
  state is written only by the class that owns it.

**Known limit, for `029F`:** lines and bands ignore the plot's auto-range, as the last price line does, so a level, stop loss or take profit outside the candles' range is off screen until the user zooms out. The Bots tab may want a "fit levels" view.

**Verification.**
- Unit tests:
  - `PriceLevelLayer`: lines and bands by key; replace and clear.
  - The Grid overlay, computed from the report's example plan.
  - The drawer: identical items on all three surfaces; colours by role; a new overlay replaces the old; fills at their time and price.
  - `BotChart`: no network on the planner preview; a stream under `bot.<id>` whose release leaves a desk's stream alone; only its market's candle at its interval is applied; a forming candle updates the last bar; after `shutdown()` no tick is drawn and a re-follow draws each candle once.
- The full test suites for the architecture, bots, charting, presentation (previews included) and trading UI, plus all integration tests, pass. `ci-local.ps1 -SkipTests` passes with a clean log.
- The preview was rendered offscreen and looked at.
- The full gate is GitHub Actions' `ci-local.ps1 -Full` on the PR.

**Not verified:** a bot chart against the real exchange stream, which arrives with `029E`/`029F` and is checked in `029H`.

## Resume (optional; while unfinished)
