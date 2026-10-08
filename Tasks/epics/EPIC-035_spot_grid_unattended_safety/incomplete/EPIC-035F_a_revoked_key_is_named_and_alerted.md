# EPIC-035F — A key revoked mid-run is named, not mistaken for a switch-off

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M4 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 2 of [EPIC-035](../README.md).
**Risk:** 🟡 — after revocation the orders cannot be cancelled, so the user must be told at once
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** EPIC-035C

---

## 1. Context and problem
Audit M4: the next order after a revocation fails its connection check and is classed as a switch-off, so the bot goes HALTED without a cancel; nothing detects the revocation between orders. Cited: `src/modules/bots/application/services/bot_order_gateway.py:75-80`, `src/modules/bots/application/services/grid_task_guard.py:99-105`. Verify.

This task is specified briefly: it is Phase 2 — Infrastructure resilience. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] `-2015` / `-2008` (and a key-rejection class from the translator) map to a named reason `KEY_REJECTED`, distinct from `SWITCH_OFF`.
- [ ] A rejected key HALTs the bot and says plainly that its orders may still rest and cannot be cancelled from this app.
- [ ] The key is probed on a bounded interval while a bot holds orders, so a revocation is found between orders.
- [ ] The alert goes through `EPIC-035K` once it exists.

## 3. Design
Do not park on `KEY_REJECTED` (the park would fail); record the unmanaged-orders fact instead.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/bot_order_gateway.py` | as the criteria require |
| `src/modules/bots/application/services/grid_task_guard.py` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_a_rejected_key_halts_with_key_rejected_not_switch_off` (red before: `SWITCH_OFF`)
- `test_the_key_is_probed_between_orders`

Not run yet.

## Resume
Not started.
