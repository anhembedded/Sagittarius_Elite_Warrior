# EPIC-035D — Retry, backoff and Retry-After for exchange calls

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M3 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 2 of [EPIC-035](../README.md).
**Risk:** 🟡 — a retry on a submit can duplicate an order; only reads and cancels may retry
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None

---

## 1. Context and problem
Audit M3 (a static finding, not re-verified in this session): a single transient failure (timeout, reset, DNS) puts the bot in ERROR, which needs a manual Stop/Start. `-1003` / `-1015` / HTTP 429 / 418 are classified but also lead to ERROR; `Retry-After` and used-weight headers are ignored; each order costs about three extra requests (client creation, ping, server time, account read). Cited: `src/modules/bots/application/services/bot_order_gateway.py:150-162`, `src/modules/trading/adapters/binance/binance_error_translator.py:327-330`, `src/modules/trading/application/orders/execute_order/handler.py:296-322`. Verify these before the first test.

This task is specified briefly: it is Phase 2 — Infrastructure resilience. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] Reads and cancels retry with exponential backoff and a cap; an order **submit** never retries on an unknown outcome (the existing lookup by client order id stays the only resolution).
- [ ] `Retry-After` and the rate-limit headers are honoured; a 429 / `-1003` pauses the whole gateway for the stated time, and a 418 backs off for its ban window.
- [ ] Rate-limit exhaustion HALTs the bot temporarily with a named reason and resumes by itself when the window ends; it is not ERROR.
- [ ] One client per venue session is reused; the per-order extra requests drop to the documented minimum (the number is measured and recorded).

## 3. Design
Retry belongs in one place below the gateway, as a policy object (retry-with-backoff, a vetted pattern), not at each call site. The bots gateway and the manual-order path share it.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/bot_order_gateway.py` | as the criteria require |
| `src/modules/trading/adapters/binance/binance_error_translator.py` | as the criteria require |
| `src/modules/trading/application/orders/execute_order/handler.py` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_a_timeout_on_a_cancel_retries_and_succeeds` (red before: ERROR)
- `test_a_submit_with_an_unknown_outcome_is_looked_up_never_resent`
- `test_retry_after_is_honoured`
- `test_a_rate_limit_halts_temporarily_and_resumes`

Not run yet.

## Resume
Not started.
