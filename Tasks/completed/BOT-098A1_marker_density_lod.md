# BOT-098A1 — Pixel-budget LOD for truthful Backtest trade markers

**Parent:** `BOT-098`  
**Source:** [`BUG-006`](../bug_report/BUG-006.md)  
**Priority:** P1  
**Status:** Completed

## Goal

Extend `BOT-098A` from timestamp-window virtualization to on-screen density
control. Keep exact marker history as source of truth, but select a bounded,
truthful visual representation from the current viewport and chart width.

## Design contract

- Low density: render exact labels unchanged.
- High density: group only markers with the same text, color and direction in
  stable X buckets; render the representative label as `<label> ×<count>`.
- Never aggregate `MUA (LONG)` with `ĐÓNG LONG` or a future SHORT semantic.
- Pixel width, not candle count or a machine-specific timing threshold, owns
  the display budget.
- Pan/zoom changes only display detail. Stored markers and Backtest results
  are immutable.

## Verification

Follow the four regression layers in `BUG-006`. Desktop visual/runtime probe
is opt-in; ordinary sanity remains boot/DI/QML construction only. Full CI is
the final gate.

Performance evidence: [`BOT-098A1 marker density performance`](../reports/BOT-098A1_marker_density_performance.md).

Full CI: native CMake, Ruff, 1,018 primary tests and 28 sanity tests passed.
The real-Qt interaction probe confirms cached-frame pan/zoom previews keep the
exact data range unchanged during the gesture and commit one exact render when
the mouse is released or the wheel burst ends.
