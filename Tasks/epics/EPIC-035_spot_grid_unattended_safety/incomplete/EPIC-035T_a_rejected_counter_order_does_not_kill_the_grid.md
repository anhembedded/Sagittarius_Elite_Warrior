# EPIC-035T — A rejected counter order does not kill the grid

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M11 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 4 of [EPIC-035](../README.md).
**Risk:** 🟡 — one exchange rejection ends a healthy ladder
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** EPIC-035C

---

## 1. Context and problem
Audit M11: an exchange error on a counter order (`LOT_SIZE`, `PERCENT_PRICE`, `MIN_NOTIONAL`, `-2010`) raises, the bot goes to ERROR and the whole ladder is cancelled; counter orders are not re-checked against percent price before submission; `-2010` has no named mapping. Cited: `src/modules/bots/application/services/bot_order_gateway.py:271-305`, `src/modules/trading/adapters/binance/binance_error_translator.py:323-335`. Verify.

This task is specified briefly: it is Phase 4 — Accuracy. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] A counter order is validated against the exchange filters (including percent price) before it is sent.
- [ ] A rejected counter order leaves that level EMPTY with a named reason and the bot keeps running; repeated rejections of the same level HALT with the existing level rule.
- [ ] `-2010` maps to a named reason.

## 3. Design
Reuse the Start-time filter checks for counter orders.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/bot_order_gateway.py` | as the criteria require |
| `src/modules/trading/adapters/binance/binance_error_translator.py` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_a_rejected_counter_order_leaves_the_level_empty_and_the_bot_running` (red before: ERROR)
- `test_minus_2010_has_a_named_reason`

Not run yet.

## Resume
Not started.
