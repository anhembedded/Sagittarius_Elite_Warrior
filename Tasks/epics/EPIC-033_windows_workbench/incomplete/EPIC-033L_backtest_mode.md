# EPIC-033L — Backtest mode: test a strategy on stored history, laid out as HLD §11.2.1 designs it

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "Đừng bị UI hiện tại dẫn dắt nhé, bạn có quyền xây lại triết lý và desihn của tất cả UI" (do not be led by the current UI; you may rebuild the philosophy and design of the whole UI); the modes come from EPIC-033O's approved information architecture, not from the screens that exist today.
**Risk:** 🟡 — the most styled area (61 `setStyleSheet` calls)
**Complexity:** L
**Epic:** [EPIC-033](../README.md)
**SPEC:** SPEC-009 when specified
**Depends on:** EPIC-033O (approved design of this mode), EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G, EPIC-033N

---

## 1. Context and problem
Backtest is a page whose parameter bar of pill dropdowns clips at 1366 px, scrolls a chart inside a page scroll, and owns 16 hand-styled dialogs.

## 2. Acceptance criteria
- [ ] Run setup is a dock (or one Run Settings… dialog) with market, symbol, strategy, timeframe, range, timezone, capital and execution; Run is an action (F5) and Stop replaces it while running.
- [ ] The central widget and default docks are exactly those HLD §11.2.1 lists for this mode (the one list; this task does not copy it). Every remaining dialog is a stock `QDialog` with `QDialogButtonBox`.
- [ ] Every command of the mode is an action in its menu and, when frequent, its toolbar; every table and read-out is built from its spec; the mode passes the conformance suite with no baseline row.
- [ ] The SPECs above still pass their "Proven by" tests; any changed flow updates its SPEC in the same pull request.

## 3. Design
The mode's wireframe approved in EPIC-033O is the design; this task builds it on `WorkbenchShell` with stock controls. Presenters, coordinators and view models are reused where their behaviour fits the approved design; views are new. It replaces: the Backtest screen and its 16 dialogs.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| The mode's package under `src/modules/*/ui/` | New views on the workbench; contributions in `module.py` |
| The replaced screens' views | Deleted |

## 5. Testing
Integration: conformance suite for the mode, the SPEC journeys. Desktop E2E: open, use, rearrange, restart.

## Implementation notes (written when done)
Not started.
