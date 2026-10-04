# EPIC-033J — Data mode: keep history complete, laid out as HLD §11.2.1 designs it

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "Đừng bị UI hiện tại dẫn dắt nhé, bạn có quyền xây lại triết lý và desihn của tất cả UI" (do not be led by the current UI; you may rebuild the philosophy and design of the whole UI); the modes come from EPIC-033O's approved information architecture, not from the screens that exist today.
**Risk:** 🟡 — destructive commands
**Complexity:** M
**Epic:** [EPIC-033](../README.md)
**SPEC:** [SPEC-001](../../../../Docs/SPEC/SPEC-001_sync_a_symbols_history.md); SPEC-008 when specified
**Depends on:** EPIC-033O (approved design of this mode), EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G, EPIC-033N

---

## 1. Context and problem
Data Management is a page of metric cards, a header with Vacuum and Purge, and a column of full-width 40 px buttons, the fifth hidden by its own scroll area.

## 2. Acceptance criteria
- [ ] The central widget and default docks are exactly those HLD §11.2.1 lists for this mode (the one list; this task does not copy it).
- [ ] Data menu: Sync…, Scan, Repair Gap…, Compact Database, Delete Data…; the table's context menu repeats the per-row commands; Delete Data… confirms with a safe default.
- [ ] Record count and database size show in the status bar.
- [ ] Every command of the mode is an action in its menu and, when frequent, its toolbar; every table and read-out is built from its spec; the mode passes the conformance suite with no baseline row.
- [ ] The SPECs above still pass their "Proven by" tests; any changed flow updates its SPEC in the same pull request.

## 3. Design
The mode's wireframe approved in EPIC-033O is the design; this task builds it on `WorkbenchShell` with stock controls. Presenters, coordinators and view models are reused where their behaviour fits the approved design; views are new. It replaces: the Data Management screen.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| The mode's package under `src/modules/*/ui/` | New views on the workbench; contributions in `module.py` |
| The replaced screens' views | Deleted |

## 5. Testing
Integration: conformance suite for the mode, the SPEC journeys. Desktop E2E: open, use, rearrange, restart.

## Implementation notes (written when done)
Not started.
