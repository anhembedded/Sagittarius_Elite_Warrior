# BUG-053 — Multi-line subplot indicator script (MACD) gets one subplot ROW per LINE instead of one per script

**Reported date:** 2026-08-26
**Severity:** 🟠 P1 — every MACD (built-in `macd_full`) use on the Dev Board draws wrong: 3 stacked
rows instead of 1, squeezing the main candlestick plot and double/triple-registering the crosshair
for the same script.
**Status:** ✅ Fixed 2026-08-26 — root-caused, reproduced, regression-tested (red before fix, green
after), verified.

---

## 1. Symptom

Found while investigating [`BUG-034`](BUG-034_dev_board_live_chart_wrong_axis_scale.md) (Dev Board
Live Chart: candles missing, Y axis reads `-50..100`). A faithful headless reproduction of the Dev
Board's real flow — real `ChartCard`, real `IndicatorScriptRunner`, real `dev_showcase` +
`rsi_14` + `macd_full` scripts, 2000 synthetic ETH-priced candles fed through the actual
`draw()` pathway used in production — did **not** reproduce BUG-034's exact Y-range symptom (the
main plot's Y-range correctly tracked the synthetic data's real extent). It did, however, surface a
different, independently real defect in the same subsystem:

```
subplot rows: 5
  indicator 'dev_showcase:EMA 12'      -> plot id 140381948840576   (main_plot, correct — overlay)
  indicator 'dev_showcase:WMA 20'      -> plot id 140381948840576   (same, correct)
  indicator 'dev_showcase:EMA 26'      -> plot id 140381948840576   (same, correct)
  indicator 'dev_showcase:Widening band' -> plot id 140381948840576 (same, correct)
  indicator 'rsi_14:RSI 14'            -> plot id 140381949170368   (its own row, correct — 1 line)
  indicator 'macd_full:MACD'           -> plot id 140381946306176   (own row)
  indicator 'macd_full:Signal'         -> plot id 140381946385088   (DIFFERENT row)
  indicator 'macd_full:Histogram'      -> plot id 140381944531904   (DIFFERENT row)
```

`macd_full` (`MacdFullScript`) fans one MACD reading into 3 plotted lines — `MACD`, `Signal`,
`Histogram` — explicitly documented as belonging "on their own subplot row" (singular,
`macd_full_script.py`'s own docstring). Instead each of the 3 lines got a **brand new** subplot
row. With Volume(1) + RSI(1) + MACD's 3 separate rows(3) = 5 subplot rows at `stretch=1` each
against the main plot's `stretch=3`, the main candlestick plot is squeezed to ~3/8 of the chart's
vertical space whenever `macd_full` is enabled — and the crosshair layer gets registered 3 times
for what is visually one indicator (`ChartPlotLayout.add_subplot()`'s `_on_new_plot` callback fires
once per spurious row).

## 2. Root cause

`IndicatorScriptRunner.draw()` (`src/presentation/ui/components/indicator_scripts/runner.py`,
around line 344) calls `card.add_subplot_indicator(qualified, color)` once for **every new line
name** a non-overlay script produces, with no way to say "this line belongs to the same subplot as
that other line from the same script":

```python
if line_name not in active.registered_lines:
    if active.overlay:
        card.add_overlay_indicator(qualified, color)
    else:
        card.add_subplot_indicator(qualified, color)   # <- no shared-row concept
```

`ChartCard.add_subplot_indicator()` → `IndicatorManager.add_subplot()`
(`chart_card/indicator_manager.py`) had no notion of "reuse an existing row" either — every call
went straight to `ChartPlotLayout.add_subplot()`
(`chart_card/plot_layout.py`), which **unconditionally** appends a brand new `PlotItem` row
(`self._next_row += 1` on every call, no exceptions). For a script with only one plotted line
(RSI) this is correct — one call, one row. For a script that fans one reading into several lines
(MACD), the exact same call-once-per-line-name pattern produces one row **per line** instead of
one row **per script**, because nothing tracked "line X and line Y came from the same script."

This is an independently real defect, confirmed by code reading and by an existing test gap: the
pre-existing `test_a_non_overlay_script_draws_on_its_own_subplot`
(`tests/unit/presentation/ui/components/test_indicator_script_runner.py`) only ever called
`runner.draw()` for MACD's first line (`"macd_full:MACD"`) — it never exercised what happens when a
**second** line of the **same** script gets drawn, so the row-per-line bug had no test surface
that could have caught it.

**Relationship to BUG-034:** this defect lives in the exact subsystem BUG-034's report already
flagged (subplot creation for custom indicator scripts) and plausibly contributes to the squeezed/
wrong-looking main plot the user saw — but the synthetic repro built to investigate it did **not**
reproduce BUG-034's specific `-50..100` Y-axis reading, so this fix does **not** close BUG-034.
BUG-034 stays open; its report is updated with this finding as a new, ruled-**in** (not ruled out)
data point for the next investigation round, not a root cause claim.

## 3. Fix

Added an optional `group` key that flows `IndicatorScriptRunner.draw()` →
`ChartCard.add_subplot_indicator()` → `IndicatorManager.add_subplot()`:

- `IndicatorScriptRunner.draw()` now passes `group=key` (the script's registry key, e.g.
  `"macd_full"`) for every line of a non-overlay script — same key for every line of the same
  script, by construction (`key` is the loop variable over `self.active`, not per-line).
- `IndicatorManager.add_subplot(name, color, height_ratio=1, group=None)`: when `group` is given
  and already has a row (`self._group_plots`), reuses that existing `PlotItem` — adds a new curve
  to it via `sub_plot.plot(...)` and `_register()`, but does **not** call
  `ChartPlotLayout.add_subplot()` again and does **not** re-fire `_on_new_plot` (avoids the
  crosshair double-registration). Without `group` (every pre-existing caller — RSI, the Backtest
  screen's Equity subplot, `chart_card/__main__.py`'s demo), behavior is byte-for-byte unchanged:
  every call still gets its own fresh row.
- `IndicatorManager.remove()`: a grouped row is only torn down once its **last** member curve is
  removed (`self._group_members` ref-counts live curves per group) — removing one line of a still-
  active multi-line script (e.g. toggling something else off without disabling `macd_full` itself)
  must leave the shared row and its other curves alone.
- `ChartCard.add_subplot_indicator()` gained the same optional `group: str | None = None`
  parameter, forwarded through. `IBacktestChartHost`/`PythonBacktestChartHost` (the Backtest
  screen's chart port) were deliberately left untouched — its one `add_subplot_indicator()` caller
  (the Equity subplot) never needs grouping, and the port's own contract stays exactly as narrow as
  it was.

Every pre-existing call site keeps calling with `group=None` (the default), so single-line
subplots (RSI, Equity, the `chart_card/__main__.py` demo) are unaffected — proven by
`test_add_subplot_indicator_without_a_group_still_gets_its_own_row` below.

## 4. Regression tests

Two tests, at the two layers the defect actually spans (bug-fix-rule §3 — pick the tier where the
bug lives; a mock-only test at either layer alone could not have proven the fix, so both were
required):

1. `tests/unit/presentation/ui/components/test_chart_card.py::test_add_subplot_indicator_with_a_shared_group_reuses_one_row`
   — real `ChartCard` (needs Qt/offscreen), asserts `len(card.plot_layout.sub_plots)` stays at
   `+1` (not `+3`) after 3 grouped `add_subplot_indicator()` calls, and that all 3 curves land on
   the *same* `PlotItem`. **Confirmed red before the fix**
   (`TypeError: ChartCard.add_subplot_indicator() got an unexpected keyword argument 'group'`,
   since `group` didn't exist yet — the strongest possible "fails for the right reason": the
   feature the test exercises was entirely absent), green after.
2. `tests/unit/presentation/ui/components/test_chart_card.py::test_add_subplot_indicator_without_a_group_still_gets_its_own_row`
   — companion test proving the ungrouped path (RSI, Equity) is untouched; passed both before and
   after (guards against a fix that accidentally always groups).
3. `tests/unit/presentation/ui/components/test_indicator_script_runner.py::test_a_multi_line_subplot_script_tags_every_line_with_the_same_group`
   — the runner-level wiring contract: `draw()` for `macd_full`'s 3 lines must call
   `card.add_subplot_indicator(..., group=...)` with the **same** group value for every line.
   **Confirmed red before the fix** (`assert {None} == {'macd_full'}` — the runner wasn't passing
   `group` at all), green after.

Also re-ran the full pre-existing `test_chart_card.py` / `test_indicator_script_runner.py` /
`test_backtest_chart_host.py` suites (120 tests) — all pass, confirming the Backtest screen's
Equity-subplot path and every other `add_subplot_indicator` caller is unchanged.

## 5. Environment note

This session had no pre-built `.venv` and no sibling `Sagittarius_Engine` checkout (unlike a normal
dev machine per `.agents/ONBOARDING.md` §2) — both were bootstrapped from scratch (`python3.12 -m
venv .venv`, `pip install -r requirements.txt`, `pip install git+https://github.com/anhembedded/Sagittarius_Engine.git`,
plus system `libegl1`/`libgl1-mesa-dri` for headless Qt) to get a real `pytest -q` run rather than
trusting static reading alone, per `bug-fix-rule.md` §1–3.
