---
name: Async UI Action Ownership Rule
description: Action ownership, stale-callback fencing, and cooperative cancellation for every user-initiated background task, plus the Coordinator Pattern for when a Presenter becomes overloaded.
trigger: on_demand
---

# ASYNC UI ACTION OWNERSHIP & CANCELLATION

Read this when: modifying a Presenter, submitting work to `IThreadManager`, handling a
`CancellationToken`, writing a slot that receives results from a background worker, or splitting an
overloaded Presenter into Coordinators. This is the area that has produced the most real bugs in
this repo (`BUG-018`, `BUG-023`, `BUG-031`, `BUG-033`, `BUG-041`) — read all of it before making
changes, do not skim.

## 1. Action Ownership & Cancellation

- Every user-initiated background action that can alter UI lifecycle state (backtest, sync, load, render) MUST have an immutable action context: unique `action_id`/generation, action kind, immutable input snapshot, start time, and explicit terminal outcome.
- Worker signals and completion callbacks MUST carry the action identity. Before changing ViewModel state, FSM state, chart data, or starting a follow-up action, the receiving slot MUST verify that the action is still active. Stale callbacks are ignored and logged; they must never overwrite a newer user intent.
- Cancellation MUST be cooperative and idempotent. A cancelled action may not later publish success/failure UI state, and its final transition must restore the appropriate pre-action lifecycle state rather than blindly forcing `IDLE`.
- Long-running use cases MUST propagate cancellation checks through every computational pass, including validation/split passes. Progress events must be throttled or coalesced before reaching the UI thread.

## 2. Coordinator Pattern for an overloaded Presenter (`PRO-001`/`PRO-002`, `EPIC-003`)

- When a Presenter's background-action logic outgrows one file, split it by feature slice into `<name>/coordinators/<feature>_coordinator.py` — a Presenter-owned, constructor-injected class (`thread_manager`, `dispatcher`, and the specific `view_model` signals it handles), never something that resolves its own container or is independently discoverable/DI-registered. This is a distinct, sanctioned category from plain `logic/`/`helpers/` modules — those stay pure functions/stateless transforms; a Coordinator may hold state and submit its own background work.
- **A Coordinator MUST NOT own independent FSM state or its own action-ownership/cancellation bookkeeping** (the `action_id`/generation, stale-callback fencing, and cooperative-cancellation contract in §1). That bookkeeping has exactly one owner — the Presenter (or a single shared tracker the Presenter owns and hands to every Coordinator) — never reimplemented per-Coordinator. Coordinators that each keep their own action-id counter are the same "Single-Scope Cohesion" violation as scattering one FSM's Enum/matrix across files: one lifecycle fragmented into several sources of truth that can silently disagree. Before splitting a Presenter that already has bespoke action-ownership machinery (e.g. `BacktestPresenter`'s `_next_action_id`/`_active_action`/`BacktestActionKind`), extract that machinery into one shared, reusable tracker first — do not duplicate it across the new Coordinator files.
- The Presenter that owns a screen's Coordinators keeps the FSM, keeps `_connect_ui_signals()`/`_connect_engine_events()`, and keeps final say over UI-visible state; Coordinators do the work and report back through it, they do not become parallel mini-Presenters with their own UI-mode opinions.
