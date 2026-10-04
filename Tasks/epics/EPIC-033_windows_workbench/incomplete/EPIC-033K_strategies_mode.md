# EPIC-033K — Strategies mode: arm and watch strategies and bots, laid out as HLD §11.2.1 designs it

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "Đừng bị UI hiện tại dẫn dắt nhé, bạn có quyền xây lại triết lý và desihn của tất cả UI" (do not be led by the current UI; you may rebuild the philosophy and design of the whole UI); the modes come from EPIC-033O's approved information architecture, not from the screens that exist today.
**Risk:** 🔴 — arms live strategies
**Complexity:** M
**Epic:** [EPIC-033](../README.md)
**SPEC:** SPEC-010 when specified; the Bots work of EPIC-029
**Depends on:** EPIC-033O (approved design of this mode), EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G, EPIC-033N

---

## 1. Context and problem
Arming a strategy lives in a card inside each desk, the last signal in another card on Dev Board, and the Grid bot of EPIC-029 has its own Bots tab, a workbench of its own beside the others: there is no place where a person sees everything that trades for them.

## 2. Acceptance criteria
- [ ] The central widget and default docks are exactly those HLD §11.2.1 lists for this mode (the one list; this task does not copy it). The docks follow the selection in the central table.
- [ ] Arm, Disarm, Start Bot, Stop Bot are actions with confirmations where they start live trading.
- [ ] Every command of the mode is an action in its menu and, when frequent, its toolbar; every table and read-out is built from its spec; the mode passes the conformance suite with no baseline row.
- [ ] The SPECs above still pass their "Proven by" tests; any changed flow updates its SPEC in the same pull request.

## 3. Design
The mode's wireframe approved in EPIC-033O is the design; this task builds it on `WorkbenchShell` with stock controls. Presenters, coordinators and view models are reused where their behaviour fits the approved design; views are new. It replaces: the strategy and last-signal cards, the bot chart preview, and the Bots tab's `BotsView` (`src/modules/bots/ui/bots_screen/`, `EPIC-029F`). Its presenter, view model and per-kind panels are reused, and its `item_view_config` stock-control lines leave their baseline.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| The mode's package under `src/modules/*/ui/` | New views on the workbench; contributions in `module.py` |
| The replaced screens' views | Deleted |

## 5. Testing
Integration: conformance suite for the mode, the SPEC journeys. Desktop E2E: open, use, rearrange, restart.

## Implementation notes (written when done)
Not started.
