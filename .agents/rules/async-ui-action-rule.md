---
name: Async UI Action Ownership Rule
description: Action identity, stale-callback fencing and cooperative cancellation for every background task started from the UI; the Coordinator pattern.
trigger: on_file_change
patterns:
  - src/**/*presenter*.py
  - src/**/*coordinator*.py
---

# Async UI actions

The area behind the most real bugs here (`BUG-018`, `023`, `031`, `033`, `041`). Read all of it.

## 1. Ownership and cancellation
- Every user-initiated background action that can change UI lifecycle state (backtest, sync, load, render) has an immutable action context: `action_id`/generation, kind, input snapshot, start time, explicit terminal outcome. `[review: G1]`
- Worker signals and callbacks carry the action identity; a receiving slot verifies the action is still active before touching ViewModel, FSM, chart data or starting follow-up work. Stale callbacks are ignored and logged. `[review: G1]`
- Cancellation is cooperative and idempotent; a cancelled action never publishes success/failure afterwards and restores the pre-action state, never a blind `IDLE`. Long use cases check cancellation in every pass; progress is throttled before the UI thread (`ProgressThrottle`). `[review: G2]`
- `fsm.transition_to(X)` while already in `X` raises; `@safe_ui_action` swallows it and the slot dies mid-way — put nothing important after a call that can throw (`BUG-018`). A worker that never locked the UI must not emit unlock. `[review: G5]`

## 2. Coordinators (`PRO-001`/`002`, `EPIC-003`)
- When a Presenter's background logic outgrows one file, split by feature slice into `<name>/coordinators/<feature>_coordinator.py`: Presenter-owned, constructor-injected (`thread_manager`, `dispatcher`, the specific view-model signals), never self-resolving, never DI-registered or discoverable. `[guard: `grep -rn "Coordinator\|Presenter" src | grep "singleton(\|bind("` is empty; review: G4]`
- A Coordinator owns **no** FSM state and **no** action-id bookkeeping — one owner (the Presenter, or one shared tracker it hands out). Extract bespoke tracking into a shared tracker before splitting. The Presenter keeps the FSM, `_connect_ui_signals()`/`_connect_engine_events()` and final say over UI-visible state. `[review: G3]`
