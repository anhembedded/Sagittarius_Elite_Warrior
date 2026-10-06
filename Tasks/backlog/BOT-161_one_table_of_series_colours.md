# BOT-161 — Every data series colour comes from one table, and the domain names no colour

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-06, choosing to keep the last stock-controls ratchet out of `EPIC-033M` ("Task riêng, giữ ratchet": a separate task, keep the ratchet).
**Risk:** 🟡 — a strategy's markers and an indicator's lines change where their colour is decided; a wrong mapping recolours a chart.
**Complexity:** M — about 34 literals in 13 files across `strategy/domain`, `strategy/ui` and `support/indicators`.
**Epic:** [EPIC-033](../epics/EPIC-033_windows_workbench/README.md)
**Depends on:** `EPIC-033M` (merged)

---

## 1. Context and problem
`EPIC-033M` turned every rule of `tests/unit/architecture/test_stock_controls_only.py` into a ban except `color_literal`, which still lists the hex strings of data series in `baseline_stock_controls.json`: indicator lines (`support/indicators/indicator_scripts/*_script.py`), strategy markers and lines (`modules/strategy/domain/strategies/ema_trend_pullback_strategy.py`, `long_term_trend_zone_strategy.py`, `modules/strategy/ui/strategy_overlay/strategy_indicator_lines.py`) and the chart's bull and bear (`support/charting/chart_card/theme.py`). Two of those files are in a module's `domain/`, which should not know what a line looks like.

## 2. Acceptance criteria
- [ ] One table names every data series colour by its meaning (an indicator's line, a strategy's entry, a band), and every reader asks the table by name.
- [ ] No file under `modules/*/domain` holds a colour; a strategy says which series it draws, the UI decides its colour.
- [ ] `color_literal` is zero outside the one table, the table is the guard's single named exemption, and `baseline_stock_controls.json` is deleted: `test_stock_controls_only.py` is a ban outright.
- [ ] Every chart shows the same colours as before (a test reads each series' colour through the table).

## 3. Design
Not started. The meaning table `src/support/ui_kit/meaning_colours.py` (profit, loss) and `chart_card/theme.py` (bull, bear, take profit, levels) are the precedent; whether series colours join `theme.py` or a sibling is this task's first decision.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `support/indicators/indicator_scripts/*_script.py` | Read their line colours from the table |
| `modules/strategy/domain/strategies/*.py` | Name series, not colours |
| `tests/unit/architecture/test_stock_controls_only.py` | Becomes a ban; the baseline file goes |

## 5. Testing
Architecture guards; a unit test per moved colour reading the same value through the table; the chart previews.

## Implementation notes (written when done)
Not started.
