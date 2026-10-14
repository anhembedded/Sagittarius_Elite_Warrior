# BUG-207 — On the bot chart, the Upper/Lower range markers sit on the top and bottom grid levels and one hides the level label

- **Reported:** 2026-10-14 (owner screenshot, real-money Spot Mainnet bot `ke95g7`, grid 2348–2667, 6 arithmetic grids; relayed by the coordinator session)
- **Severity:** 🟢 P3 — presentation only, but the owner read "Up on L6" as a red flag and L0 (a resting Buy) had no visible label
- **Status:** ✅ Fixed (2026-10-14)
- **Board:** A range limit that is also a grid level was drawn as a second line with its own tag at the same price and right-edge anchor, so the tags overprinted (Lower hid L0, Upper sat beside L6); fixed in the shared overlay model by folding a coinciding limit into the level's label ("L6 · range top"), one label per price.
- **Context:** Bots → bot chart ([SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)) → `src/modules/bots/domain/grid/grid_overlay.py` (the one overlay computation for the planner preview, the backtest and the running bot), drawn through `ui/chart/overlay_items.py` and `src/support/charting/chart_card/price_level_layer.py`
- **Environment:** Desktop app on `master-warrior` after `BUG-204`, offscreen preview render. Nothing was placed, tested or simulated against Binance mainnet.

## Reproduction
1. Open the bot chart (preview `bot_chart`: 60,000–70,000, 10 arithmetic grids) so a limit equals a level.
2. Look at the right-edge tags at the lowest and highest price.
3. Expected: one tag per price, every level visible. Actual (preview render before the fix): a blue "Lower" tag covers L0 at the bottom; at the top two tags share the price.

## Symptom
Owner: at 2667 the tags read "Up | L6" side by side; at 2348 only "Lower" shows, no "L0", although L0 is a resting Buy at 2348 and L1 at 2401.16 is labelled; "Up on L6" read as a red flag.

## Root cause
In an arithmetic grid the limits are the outermost levels, so the coinciding price is expected and correct; the defect is two markers for one price. `grid_overlay._edge_lines` always emitted "Lower" and "Upper" as `RANGE_EDGE` lines beside the level lines (`grid_overlay.py`, `grid_overlay`), and `PriceLevelLayer._line` (`price_level_layer.py`) gives every line its own label at `position=1.0` with the same `RIGHT_EDGE_TAG_ANCHORS`, so two tags at one price overprint. Which one is visible follows the sort `(price, role.value, label)`: `BUY_LEVEL < RANGE_EDGE` draws "Lower" last, over L0; `RANGE_EDGE < SELL_LEVEL` draws L6 last, over "Upper" — hence the top/bottom inconsistency.

## Fix
`grid_overlay` (the one computation all three surfaces share, so none can differ): a limit equal to a level's price is folded into that level's label ("L0 · range bottom", "L6 · range top"), in the level's own side colour, and only a limit no level sits on keeps its `RANGE_EDGE` line and "range bottom"/"range top" label. Every level keeps its tag.

## Regression test
`tests/unit/modules/bots/domain/grid/test_grid_overlay.py`:
- `test_a_limit_that_is_a_level_draws_one_label_in_the_levels_colour` — one line per price, "L0 · range bottom" / "L10 · range top", level roles. Red before the fix: two lines at 60,000 (`BUY_LEVEL "L0"` and `RANGE_EDGE "Lower"`).
- `test_a_limit_between_levels_keeps_its_own_line` — a limit no level sits on keeps its own label (two labels where two prices exist). Red before the fix: the upper limit also drew its own "Upper" line.
- `test_every_level_keeps_a_label_when_the_limits_merge_into_it`.
- `test_the_plan_alone_draws_its_levels_edges_and_exits` now asserts no `RANGE_EDGE` line when both limits are levels; the old `test_equal_prices_draw_in_one_stable_order`, which pinned the doubled labels, is replaced by the first test above.

## Addendum (owner, relayed 2026-10-14)
The owner also read "Up" as a possible take-profit line; TP (2805) and SL (2259) have their own markers. The limits are therefore named "range top" / "range bottom" ("L6 · range top", "L0 · range bottom"), never "Up"/"Upper"/"Lower". TP and SL keep their own roles, labels "TP"/"SL" and styles (solid, width 2, goldenrod / loss colour), which no level or range line shares. The chart has no legend or tooltip for lines (checked: none in `ui/chart` or `price_level_layer.py`), so the labels are the only text. Tests: `test_range_labels_cannot_be_read_as_exits`, `tests/unit/modules/bots/ui/chart/test_bot_chart.py::test_an_exit_never_shares_a_style_with_a_range_bound_or_a_level`.

## Verification
- Preview render of `bot_chart` before and after (offscreen, `build_preview`): before, a blue "Lower" tag covers L0; after, "L0 · range bottom" in the buy colour, all other level tags unchanged.
- `pytest tests/unit/modules/bots tests/unit/support/charting tests/integration/modules/bots`: 3770 passed. Commit tier: `ci-local.ps1 -SkipTests` PASS.
- Not covered: a limit that differs from its level by less than a tick (a price the plan rounded) still draws two lines; equality is exact. Not verified on a real-money run.

## Docs touched
`Docs/VOCABULARY/README.md` (Bot overlay: one label per price); the SPEC does not specify the label text.
