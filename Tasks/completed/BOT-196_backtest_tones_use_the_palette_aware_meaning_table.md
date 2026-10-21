# BOT-196 — The backtest tables colour their tones with the palette-aware meaning table

**Status:** ✅ Done (2026-10-20)
**Board:** The backtest tables and figures take the meaning table's tone on the application's palette, none in High Contrast: delivered inside [EPIC-043C](epics/EPIC-043_financial_visual_language/completed/EPIC-043C_pnl_tones_and_state_badges.md), which gave every table one `_tone` hook and every label `paint_label_tone`, so the four sites had nothing of their own left to change.
**Source:** the independent review of the EPIC-033U pull request, round 1 (finding 3), 2026-10-19.
**Risk:** 🟢 — display only.
**Complexity:** S — four call sites and their tests.
**Depends on:** EPIC-033U merged.

---

## 1. Context and problem
`src/modules/backtesting/ui/metrics_detail_model.py`, `metric_comparison_model.py`, `backtest_stat_row.py` and `backtest_modals/metrics_detail_dialog.py` call `tone_colour(tone)` with no palette, which keeps the chart's bull and bear colours (3.0:1 and 3.5:1 on white).

## 2. Acceptance criteria
- [x] Each of the four sites passes `QGuiApplication.palette()`; the colours read at least 4.5:1 on a light and a dark base and are none in High Contrast.
- [x] The existing backtest tests that compare against `PROFIT_COLOUR` and `LOSS_COLOUR` are updated to the palette-aware colours; no assertion is weakened.

## 3. Design
Pass the palette at the call site, as `bots_table_models.py` does. `Tone.CAUTION` has no backtest use.

## 3a. Reuse
`tone_colour(tone, palette)` of `support/ui_kit/meaning_colours.py`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| the four files above and their tests | pass the palette |

## 5. Testing
Unit tier: the four tables return the palette-aware colour on a light and a dark base and none with High Contrast replaced.

## 6. Docs touched
none, because no document describes these colours.

## Implementation notes (written when done)
Done inside `EPIC-043C` (the coordinating session pointed at the overlap): the two models (`metrics_detail_model.py`, `metric_comparison_model.py`) answer `RowTableModel._tone` instead of `tone_colour(tone)` in `_role_data`, so the palette is the one in use at each paint; the two label painters (`backtest_stat_row.py`, `metrics_detail_dialog.py`) are `paint_label_tone`, which also repaints on a scheme change, which neither did. `test_metrics_detail_model.py` and `test_metric_comparison_model.py` compare against the meaning table on the application's palette instead of `BULL_COLOR`/`BEAR_COLOR` (nothing weakened), and a new test reads the difference on a white and on a black base and in High Contrast. Not run: a real Windows session.
