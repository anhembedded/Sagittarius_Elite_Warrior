# EPIC-033K — Bots mode: create, judge, run and watch bots, laid out as HLD §11.2.1 designs it

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "Đừng bị UI hiện tại dẫn dắt nhé, bạn có quyền xây lại triết lý và desihn của tất cả UI" (do not be led by the current UI; you may rebuild the philosophy and design of the whole UI); the modes come from EPIC-033O's approved information architecture, not from the screens that exist today.
**Risk:** 🔴 — arms live strategies
**Complexity:** M
**Epic:** [EPIC-033](../README.md)
**SPEC:** SPEC-014 (the Bots tab of `EPIC-029F`, rebuilt as the mode); SPEC-010 when specified
**Depends on:** EPIC-033O (approved design of this mode), EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G, EPIC-033N

---

## 1. Context and problem
Arming a strategy lives in a card inside each desk and the last signal in another card on Dev Board, while `EPIC-029F` (PR #333) builds the Bots tab as its own `WorkbenchSurface` holding a push button, a splitter and hand-configured tables. There is no one workbench where a person sees everything that trades for them; `EPIC-029` already decided that place is Bots, with signal strategies becoming a bot kind (`EPIC-029L`).

## 2. Acceptance criteria
- [ ] The central widget and default docks are exactly those HLD §11.2.1 lists for this mode (the one list; this task does not copy it). The chart and the Plan, Orders, Fills and Log docks follow the selection in the Bots dock.
- [ ] The Bots menu and toolbar hold exactly HLD §11.2.3's commands; each bot kind contributes its panel and its toolbar, shown while a bot of that kind is selected; SPEC-014's behaviour (lifecycle-gated actions, one action at a time, the Stop dialog's *keep* default, the close guard) is unchanged.
- [ ] A strategy armed on a venue is listed as its own row with Arm and Disarm actions until `EPIC-029L`.
- [ ] Every command of the mode is an action in its menu and, when frequent, its toolbar; every table and read-out is built from its spec; the mode passes the conformance suite with no baseline row.
- [ ] The SPECs above still pass their "Proven by" tests; any changed flow updates its SPEC in the same pull request.

## 3. Design
The mode's wireframe approved in EPIC-033O is the design; this task builds it on `WorkbenchShell` with stock controls. Presenters, coordinators and view models are reused where their behaviour fits the approved design; views are new. It replaces: the Bots tab's view (its presenter, coordinators, fenced reads and view model are kept; its 7 `item_view_config` lines leave `baseline_stock_controls.json` with it), the strategy and last-signal cards.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| The mode's package under `src/modules/*/ui/` | New views on the workbench; contributions in `module.py` |
| The replaced screens' views | Deleted |

## 5. Testing
Integration: conformance suite for the mode, the SPEC journeys. Desktop E2E: open, use, rearrange, restart.

## Implementation notes (written when done)
Not started.
