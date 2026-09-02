---
name: Async Action Ownership Rule
description: Action ownership, stale-callback fencing, cooperative cancellation for every user-initiated background action, and the Coordinator pattern for an overloaded controller.
trigger: on_demand
---

# ASYNC ACTION OWNERSHIP & CANCELLATION

Read this file when: editing a controller/presenter, submitting work to a
thread/task pool, handling a cancellation token, writing a callback that
receives a background worker's result, or splitting an overloaded controller.

This is the area that has produced the most real bugs in UI-bearing projects —
read it fully before editing, don't skim.

---

## 1. Action ownership & cancellation

- **Every user-initiated background action** that can change UI lifecycle state
  (a run, a sync, a load, a render) MUST have an **immutable action context**: a
  unique `action_id`/generation, the action kind, an immutable input snapshot,
  the start time, and an explicit terminal outcome.
- **Worker signals and completion callbacks MUST carry the action identity.**
  Before changing state, changing displayed data, or starting a follow-up
  action, the receiver MUST verify the action is **still active**. A stale
  callback is **ignored and logged** — it must never overwrite the user's newer
  intent.
- **Cancellation must be cooperative and idempotent.** A cancelled action may
  **not** publish success/failure state afterwards, and its final transition
  must restore the appropriate pre-action state rather than blindly forcing
  `IDLE`.
- **Long-running use cases MUST check cancellation in every computational
  pass**, including validation/splitting passes. Progress events must be
  **throttled or coalesced** before reaching the UI thread.

---

## 2. The Coordinator pattern for an overloaded controller

When a controller's background-action logic outgrows one file, split it **by
feature slice** into a class that is:

- **owned by the controller and constructor-injected** (thread manager,
  dispatcher, and exactly the signals it handles) — **not** something that
  resolves its own container, registers itself with DI, or is independently
  discoverable;
- a **distinct category** from pure `logic/`/`helpers/` modules: helpers are
  pure functions / stateless transforms, whereas a Coordinator **may hold
  state** and submit its own background work.

**A Coordinator MUST NOT own its own state machine or its own
action-ownership/cancellation bookkeeping** (`action_id`/generation, stale
fencing, the cooperative-cancellation contract in §1). That bookkeeping has
**exactly one** owner — the controller (or **one** shared tracker the
controller owns and hands to every Coordinator) — never reimplemented per
Coordinator.

Splitting a controller into Coordinators that each keep their own action-id
counter is exactly the **Single-Scope Cohesion** violation described in
[`code-quality-rule.md`](code-quality-rule.md): one lifecycle fragmented into
several sources of truth that can silently disagree.

**Before splitting** a controller that already has bespoke action-ownership
machinery: **extract that machinery into one shared, reusable tracker first** —
do not duplicate it across the new Coordinator files.

The controller that owns a screen's Coordinators keeps the FSM, keeps the UI
and system signal wiring, and keeps final say over visible state. Coordinators
**do the work and report back through it** — they do not become parallel
mini-controllers with their own opinions about UI mode.

---

## 3. FSMs and exception-swallowing decorators — two traps that travel together

- **Don't transition a state machine into the state it is already in.** A
  transition matrix usually declares no self-edge, so that call **throws**.
- **The more dangerous consequence is in the catching decorator**
  (`@safe_ui_action` or its equivalent) that many codebases wrap around UI
  handlers: the app **does not crash**, but the handler **dies mid-way** —
  every line after that call **never runs**, and nothing surfaces.

Two rules follow:

1. **Never put important work (refreshing data, emitting a completion signal)
   AFTER a call that can throw** inside a handler wrapped by an
   exception-swallowing decorator.
2. **A background worker that never locked the UI must not emit an unlock
   signal.** An unlock with no matching lock is an invalid transition waiting to
   happen.
