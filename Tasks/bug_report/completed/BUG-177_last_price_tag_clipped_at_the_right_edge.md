# BUG-177 — The live chart's last-price tag is cut ("2,56" for "2,565.43"); the left axis shows "750" for "2,750"

- **Reported:** 2026-10-07 (the owner's screenshot, via the coordinator: Windows, 2560x1440, DPR 1, Trade mode, ETHUSDT live candle chart, master `6aa3586`)
- **Severity:** 🟡 P2 — the price the trader reads off the chart is unreadable; no order is affected
- **Status:** ✅ Fixed (2026-10-07) for the price tag, whose mechanism was reproduced; the left-axis half was not reproduced (see Root cause)
- **Board:** The right-edge price tag (`InfLineLabel`, `position=1.0`) was centred on the plot's right edge, so half of it stood outside the view box, which clips its children: the last price read "2,56". Fixed: the tag's right edge is anchored on the position (`RIGHT_EDGE_TAG_ANCHORS`), for the last price and for every price-level tag. The left-axis cut did not reproduce; its geometry is now measured too.
- **Context:** Trade mode (Docs/SPEC/ chart journeys) → `src/support/charting/chart_card/` → ChartCard / `LastPriceLine` / `PriceLevelLayer`
- **Environment:** Owner: Windows, 2560x1440, DPR 1, master `6aa3586`. Reproduced on Linux, Qt `offscreen`, PySide6 6.11.1, at 1024x700, 1366x768 and 1920x1080 and on a bare `ChartCard` from 446 to 1920 px wide.

## Reproduction
1. Trade mode, any venue, a chart with candles; the last price inside the visible price range.
2. Look at the last-price tag on the right edge.

Expected the whole price; actual the left half only. At 1024x700 the tag spanned x 388–448 in a 428 px viewport (the plot ends at about 418). Every width reproduces it: the overhang is half the tag's width, not a function of the window.

## Symptom
The owner's screenshot (not in the repository): red tag "2,56", left axis "750", "700". The tag text is `2,565.43`, 58 px wide at the owner's font; "2,56" is the left half.

## Root cause
`price_line.py` built the tag with `labelOpts={"position": 1.0, ...}` and no anchors. pyqtgraph's `InfLineLabel` picks `anchors = [(0.5, 0), (0.5, 1)]` for a horizontal line, so the text is **centred** on `position`; at `1.0` that is the view box's right edge, and the view box clips its children (`ItemClipsChildrenToShape`), so the right half was never drawn. The same defect was in `price_level_layer.py` (`position: 0.98`, centred: a 60 px tag overhangs unless the plot is wider than 3,000 px), the family of "a tag at the right edge" that a bot's grid and a strategy's stop levels use.

The reported "plot area wider than the viewport / dock overlapping the axis" is not what happens: the viewport maps to scene `(0, 0, w, h)`, the layout is exactly the viewport and the dock sits beside the chart (measured in the booted Trade mode at the three conformance sizes).

**Not reproduced: the left axis.** Every tick text of every plot's left and bottom axis lies inside its axis and inside the viewport, at 446–1920 px, for prices around 0.5, 2,700 and 25,000, and in the booted Trade mode (`axis_problems`). The owner's "750" would be a text 10 px wider than its axis; an axis that is 10 px short is what pyqtgraph does when the tick text is wider than the width it measured, which this environment did not produce (locale grouping "2,750" is the owner's; here pyqtgraph writes "2750"). The check now guards it; a screenshot of the owner's window would settle it. Also seen, not changed: the volume plot's left axis is narrower than the price plot's, so the two plots' areas start at different x.

## Fix
- `price_line.py`: `RIGHT_EDGE_TAG_ANCHORS = [(1.0, 0.0), (1.0, 1.0)]`, used by `LastPriceLine`: the tag's right edge is on the plot's right edge.
- `price_level_layer.py`: the same pair and `position` 1.0 for a level's tag, so the tag family has one rule.

## Regression test
- `tests/unit/support/charting/test_chart_tags_stay_visible.py` (12 tests, widths 446, 700, 1024, 1920): the last-price tag, a price-level tag and the axes lie inside the viewport and the plot. The tag tests are red before the fix (`tag (962, 339, 1022, 362) leaves the viewport (0, 0, 1002, 442)`), green after.
- `tests/integration/presentation/ui/test_trade_chart_tags_are_visible.py`: the booted Trade mode at 1024x700, 1366x768, 1920x1080, both venues. Red before (`tag (388, 118, 448, 141) leaves the viewport (0, 0, 428, 228)`), green after.
- The geometry measure is `tests/unit/support/charting/chart_geometry.py`.

## Verification
Local, `QT_QPA_PLATFORM=offscreen`: the two files above and `tests/unit/support/charting` (386 passed). The full gate is the PR's GitHub Actions run. Not verified: the owner's Windows window (DPR 1, 2560x1440).
