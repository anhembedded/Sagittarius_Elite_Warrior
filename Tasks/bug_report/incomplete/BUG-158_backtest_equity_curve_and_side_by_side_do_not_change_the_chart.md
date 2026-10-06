# BUG-158 — Backtest mode: choosing Equity curve or Side by side does not change the chart

- **Reported:** 2026-10-06 (the user, in chat, with one screenshot)
- **Severity:** 🟡 P2 — the equity curve and the side-by-side view cannot be reached, so a backtest result cannot be read as equity
- **Status:** Open
- **Board:** Backtest mode: choosing Equity curve or Side by side leaves the price chart unchanged. Not investigated yet.
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
Not yet established. The user asked for the report only; no investigation was done.

## Fix
Not started.

## Regression test
Not written.

## Verification
Not run.

## Suggested next steps
- Record whether the views change after a backtest has run, and the app and engine commits.
- Then follow `fix-bug-rule.md`.
