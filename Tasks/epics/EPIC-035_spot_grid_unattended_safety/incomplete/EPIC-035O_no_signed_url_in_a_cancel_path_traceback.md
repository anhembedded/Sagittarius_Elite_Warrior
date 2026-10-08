# EPIC-035O — No signed URL in a cancel-path traceback

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M12 / BUG-180 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 3 of [EPIC-035](../README.md).
**Risk:** 🟡 — a signed URL in a log is a credential-adjacent leak
**Complexity:** S
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None

---

## 1. Context and problem
Audit M12 and [`BUG-180`](../../../bug_report/incomplete/BUG-180_a_network_failure_in_a_connection_check_logs_the_signed_request_url_at_error.md): on the cancel path a `requests` error reaches `logger.exception`, so the traceback carries the signed URL (the audit marks it inferred). Cited: `src/modules/trading/adapters/binance/spot/spot_trading_client.py:139`, `src/modules/bots/application/services/bot_order_gateway.py:156`, `src/modules/trading/adapters/binance/connection_failure.py:150-155`. Fix at the mechanism: one transport-error sanitiser used by every path (`fix-bug-rule.md` §1), and close `BUG-180` through `create-bug-report-rule.md`.

This task is specified briefly: it is Phase 3 — Alerting and transparency. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] A network failure on the cancel path logs no signed URL, signature or API key anywhere in the message, the traceback or the chained exception.
- [ ] The order-send and connection-check paths use the same sanitiser (one mechanism).
- [ ] `BUG-180` is updated per the bug rule and its board line written.

## 3. Design
A single sanitiser at the transport boundary that rewrites the exception before anything logs it.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/adapters/binance/spot/spot_trading_client.py` | as the criteria require |
| `src/modules/trading/adapters/binance/connection_failure.py` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_a_cancel_failure_logs_no_signature` (red before; scans the captured log and the traceback text)

Not run yet.

## Resume
Not started.
