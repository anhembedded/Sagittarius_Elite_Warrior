# BOT-098F4 — Native marker, crosshair/tooltip and dev-FPS interaction

**Parent:** [`BOT-098F`](../backlog/BOT-098F_qt_quick_scene_graph_chart_renderer.md)  
**Depends on:** `BOT-098F1` / `F2` / `F2A` / `F3` ✅  
**Priority:** P1  
**Status:** In Progress

## Goal

Close the last native interaction gap before production migration: truthful
Backtest entry/exit markers, a final-candle crosshair/tooltip, and a
developer-only FPS diagnostic must render with the retained Qt Quick scene
graph without rebuilding candle, volume, or indicator geometry on pointer
movement.

## Contract

- Marker input is a separate versioned immutable snapshot. A `LONG_ENTRY` and
  `LONG_EXIT` retain distinct semantic IDs, colors and directions; no ambiguous
  `BUY`/`SELL` label may collapse them.
- Dense marker LOD may aggregate only equal semantic marker kinds and must
  retain represented counts. It must never merge entry and exit events.
- Pointer movement snaps to a real visible candle and changes only crosshair
  geometry plus cached tooltip payload; it may not rebuild OHLCV, volume,
  indicator or marker buffers.
- Dev FPS measures completed native frames only when dev mode is enabled; it
  remains absent from release/default UI.
- Keep PyQtGraph production fallback until `BOT-098F5` proves equivalent
  Backtest integration and full-interaction performance.

## Required proof

1. Python semantic/unit tests for marker snapshot validation, LOD separation
   and crosshair candle resolution.
2. Native QML sanity rejects stale/misaligned marker input and proves no
   geometry rebuild across pointer updates.
3. Windows visual probe samples distinct entry/exit colors and crosshair.
4. Opt-in desktop interaction probe uses real Qt mouse movement and reports
   dev FPS plus clean Qt messages.
5. Full CI passes.
