# BUG-158 — Backtest mode: choosing Equity curve or Side by side does not change the chart

- **Reported:** 2026-10-06 (the user, in chat, with one screenshot)
- **Severity:** 🟡 P2 — the equity curve and the side-by-side view cannot be reached, so a backtest result cannot be read as equity
- **Status:** Fixed (2026-10-06)
- **Board:** Backtest mode: Equity curve and Side by side left the price chart unchanged before a run. Cause: `BackTestView.set_chart_mode` re-rendered only when a result existed, and a preview redraw forced candles. Fixed: the one `_render_chart` path serves every state (empty equity series without a result) and the preview delegates to it.
- **Context:** Read a backtest result → `src/modules/backtesting/` → chart-view bar and result chart, `ui/` layer
- **Environment:** Windows (the user's desktop). App commit, engine commit and Python version not captured. Backtest mode, Spot, BTCUSDT, Ema Crossover, 30m, Range Custom…, trading off; no backtest had been run ("No trades to show." in Trades).

## Reproduction
1. Open the Backtest mode.
2. On the chart-view bar choose Equity curve.
3. Choose Side by side.

**Expected:** step 2 shows the equity curve; step 3 shows the price chart and the equity curve side by side.
**Actual (the user's words, translated):** "choosing Equity, the chart does not switch to Equity; choosing Side by side, nothing happens either." The screenshot shows Equity curve checked and the "Live Chart: BTCUSDT" price chart (empty axes 0–1) still shown.

**Frequency:** Not yet established (one occurrence reported). Whether a backtest result is needed for the views to change was not recorded. Not yet reproduced here.

## Symptom
- The user's words: "chọn Equity, nhưng chart ko nhảy qua Equity, chọn Side by side cũng k có hiện tượng gì".
- Screenshot, Equity curve checked and the unchanged chart outlined by the user: [`BUG-158_equity_curve_selected.webp`](BUG-158_equity_curve_selected.webp).

- The Backtest Output log of the same run logs each choice (`[DEV] chart_mode_changed mode='equity'`, `'both'`, `'ohlc'`) while the chart stays the same ([BUG-161](BUG-161_backtest_does_not_run.md)).

## Root cause
`src/modules/backtesting/ui/backtest_view.py` `set_chart_mode` re-rendered only `if self._last_result is not None`, and `_render_chart` read `self._last_result.equity_curve` unguarded. Before a run (or after one that produced no result, [BUG-161](BUG-161_backtest_does_not_run.md)) choosing a mode only stored the flag; the dev log line `chart_mode_changed` fired from the coordinator, which is why the Output log showed the choices while the chart stayed put. `on_preview_data_ready` had its own copy of the candle drawing that ignored the mode, so a preview refresh also undid the choice.

## Fix
`_render_chart` is now the single path for every state: it takes the equity curve from a helper that is empty without a result, so Equity draws an empty line series and Side by side adds an empty equity pane over the price candles. `set_chart_mode` always renders; `on_preview_data_ready` delegates to `_render_chart` and keeps its `chartPreviewRendered` signal.

## Regression test
`tests/unit/modules/backtesting/ui/test_backtest_chart_mode_before_run.py`: Equity and Side by side before any run, back to candles, and a preview refresh keeping the mode. Three of four were red on the unfixed view (`candlestick == 'line'`, `_equity_subplot_added is False`).

## Verification
Backtesting unit and integration suites plus `tests/unit/architecture`: 1795 passed. Commit tier (`ci-local.ps1 -SkipTests`): PASS. The mode tests assert the host's chart type and the equity pane, i.e. that the new render path ran. Not checked on a real Windows desktop.
