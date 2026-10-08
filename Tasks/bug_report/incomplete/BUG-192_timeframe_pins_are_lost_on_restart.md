# BUG-192 — Pinned timeframes are lost when the app is closed and reopened

- **Reported:** 2026-10-08 (the owner, in chat, with a screenshot of the Select Timeframe dialog)
- **Severity:** 🟢 P3 — the owner re-pins the intervals every session
- **Status:** Open
- **Board:** The Pinned ticks in the chart's Select Timeframe dialog are not kept after the app restarts.
- **Context:** Live chart toolbar → Select Timeframe dialog → `src/support/charting/` (not yet located)
- **Environment:** Windows, owner's desktop app; commit not captured.

## Reproduction
1. Open a chart and open the Select Timeframe dialog.
2. Tick the Pinned box on some intervals (the screenshot shows 1m, 5m, 15m, 1h and 1d ticked).
3. Close the dialog, close the app, then reopen the app and the dialog.

Expected: the same intervals are pinned. Actual: the pins are not kept. Frequency: as reported by the owner; not yet reproduced by a session.

## Symptom
Owner's report: "cái pin này ko save khi thoát app mở lại" (the pins are not saved after quitting and reopening the app). The screenshot shows the dialog with "Current: 1h" and five intervals pinned before the restart.

## Root cause
Not yet established. Not investigated, by the owner's instruction.

## Fix
None yet.

## Regression test
Not written.

## Verification
Not run.

## Suggested next steps
Find where the pinned set is held and whether it is written to the remembered-state store the shell already uses for per-viewer UI state. Write a test that pins, rebuilds the dialog's owner from the store, and expects the same set.
