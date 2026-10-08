# EPIC-035P — A duplicate partial fill counts once

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding L1 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 4 of [EPIC-035](../README.md).
**Risk:** 🟡 — double counting inflates inventory and then halts the bot
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None

---

## 1. Context and problem
Audit L1: `BotOrderFill` carries no trade id, so a duplicated partial-fill event is counted twice; the trading budget then refuses the oversized SELL and the bot HALTs. Cited: `src/modules/bots/contracts/bot_order_events.py:17-25`, `src/modules/trading/adapters/binance/venue_event_emitter.py:79-90`. Verify.

This task is specified briefly: it is Phase 4 — Accuracy. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] The fill event carries the exchange trade id.
- [ ] The executor ignores a fill whose (order id, trade id) it has already applied.
- [ ] The reconciler's replay uses the same key.

## 3. Design
Idempotent consumer on a natural key.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/contracts/bot_order_events.py` | as the criteria require |
| `src/modules/trading/adapters/binance/venue_event_emitter.py` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_a_duplicated_partial_fill_is_counted_once` (red before)

Not run yet.

## Resume
Not started.
