# EPIC-033H — Market mode: watch the market — chart central, Watchlist, Order book and Indicators panels

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "Đừng bị UI hiện tại dẫn dắt nhé, bạn có quyền xây lại triết lý và desihn của tất cả UI" (do not be led by the current UI; you may rebuild the philosophy and design of the whole UI); the modes come from EPIC-033O's approved information architecture, not from the screens that exist today.
**Risk:** 🟢 — read-only data
**Complexity:** M
**Epic:** [EPIC-033](../README.md)
**SPEC:** [SPEC-002](../../../../Docs/SPEC/SPEC-002_watch_the_live_market.md), [SPEC-003](../../../../Docs/SPEC/SPEC-003_check_the_exchange_connection.md)
**Depends on:** EPIC-033O (approved design of this mode), EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G, EPIC-033N

---

## 1. Context and problem
Watching the market is spread over three screens today: Watchlist (a page with one table), the Dev Board chart, and the order-book widget, none of which can sit beside the others.

## 2. Acceptance criteria
- [ ] The chart is central; Watchlist, Order book and Indicators are docks; picking a symbol in the Watchlist drives the chart and the order book.
- [ ] Connection state shows in the status bar in text; Tools → Check Connection runs SPEC-003.
- [ ] Every command of the mode is an action in its menu and, when frequent, its toolbar; every table and read-out is built from its spec; the mode passes the conformance suite with no baseline row.
- [ ] The SPECs above still pass their "Proven by" tests; any changed flow updates its SPEC in the same pull request.

## 3. Design
The mode's wireframe approved in EPIC-033O is the design; this task builds it on `WorkbenchShell` with stock controls. Presenters, coordinators and view models are reused where their behaviour fits the approved design; views are new. It replaces: the Watchlist screen and the market half of Dev Board.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| The mode's package under `src/modules/*/ui/` | New views on the workbench; contributions in `module.py` |
| The replaced screens' views | Deleted |

## 5. Testing
Integration: conformance suite for the mode, the SPEC journeys. Desktop E2E: open, use, rearrange, restart.

## Implementation notes (written when done)
Not started.
