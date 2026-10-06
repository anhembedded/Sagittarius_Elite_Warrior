# BUG-157 — Backtest mode: after Reset layout, the banner and chart-view bar sit in the wrong place when the app is reopened

- **Reported:** 2026-10-06 (the user, in chat, with two screenshots)
- **Severity:** 🟢 P3 — the Backtest layout is misplaced after a restart; the area stays usable
- **Status:** Open
- **Board:** Backtest mode: after Reset layout and a restart, the "Trading is OFF" banner and the chart-view bar jump into the middle of the window, beside the Run setup panel. Not investigated yet.
- **Context:** Restore the window layout (Window → Reset layout, saved layout on start) → `shell/` and `src/modules/backtesting/` → workbench layout, `ui/` layer
- **Environment:** Windows (the user's desktop). App commit, engine commit and Python version not captured. Backtest mode, Spot, BTCUSDT, Ema Crossover, 30m, trading off.

## Reproduction
1. In the Backtest mode, reset the layout.
2. Close the app and open it again.

**Expected:** the layout as Reset layout produced it.
**Actual (the user's words, translated):** "when resetting the layout, this bar jumps here when the app is reopened." In the first screenshot the "Trading is OFF. Data view only." banner and the chart-view bar (Candlestick, Equity curve, Side by side, Strategy indicators, Volume, Buy/sell flags, filters) start to the right of the Run setup panel, below an empty strip, and the Run setup panel starts below them; the user outlined that strip.

**Frequency:** Not yet established (one occurrence reported). Which of the two screenshots shows the state before the restart was not stated. Not yet reproduced here.

## Symptom
- The user's words: "khi rest layout mà cái thanh này nhảy về đây khi mở app lại".
- The misplaced bars, outlined by the user: [`BUG-157_bar_moved_after_reopen.webp`](BUG-157_bar_moved_after_reopen.webp).
- The second screenshot sent with it, where the banner spans the full width under the toolbar and the chart-view bar sits above the chart: [`BUG-157_second_screenshot.webp`](BUG-157_second_screenshot.webp).
- The banner itself is reported as [BUG-156](BUG-156_trading_off_banner_takes_a_full_width_strip.md).

## Root cause
Not yet established. The user asked for the report only; no investigation was done.

## Fix
Not started.

## Regression test
Not written.

## Verification
Not run.

## Suggested next steps
- Confirm with the user which screenshot is after the restart, and the exact steps (menu used for the reset, close and reopen).
- Then follow `fix-bug-rule.md`.
