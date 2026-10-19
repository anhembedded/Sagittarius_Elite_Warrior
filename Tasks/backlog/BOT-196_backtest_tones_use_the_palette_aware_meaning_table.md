# BOT-196 — The backtest tables colour their tones with the palette-aware meaning table

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** Backtesting still asks `tone_colour(tone)` without a palette at four sites, so its profit colour is 3.0:1 on a white base and ignores High Contrast; passing the palette is a one-argument change at each ([EPIC-033U](epics/EPIC-033_windows_workbench/completed/EPIC-033U_bots_tab_meaning_colours.md)).
**Source:** the independent review of the EPIC-033U pull request, round 1 (finding 3), 2026-10-19.
**Risk:** 🟢 — display only.
**Complexity:** S — four call sites and their tests.
**Depends on:** EPIC-033U merged.

---

## 1. Context and problem
`src/modules/backtesting/ui/metrics_detail_model.py`, `metric_comparison_model.py`, `backtest_stat_row.py` and `backtest_modals/metrics_detail_dialog.py` call `tone_colour(tone)` with no palette, which keeps the chart's bull and bear colours (3.0:1 and 3.5:1 on white).

## 2. Acceptance criteria
- [ ] Each of the four sites passes `QGuiApplication.palette()`; the colours read at least 4.5:1 on a light and a dark base and are none in High Contrast.
- [ ] The existing backtest tests that compare against `PROFIT_COLOUR` and `LOSS_COLOUR` are updated to the palette-aware colours; no assertion is weakened.

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
Pending.
