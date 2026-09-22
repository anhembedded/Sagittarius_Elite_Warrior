# EPIC-026A — `SPEC-006`, cancel one open order, is written and proven

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §1.4 — the user (2026-09-20): *"chi nhỏ task"*
("split it into small tasks"); this is the first of stage 0's three.
**Risk:** 🟢 — documentation and, at most, one integration test; no production code changes.
**Complexity:** S — the code exists (`EPIC-024B` shipped cancel-one on the Dev Board); the work is
to say what it does and point at the evidence.
**Epic:** [`EPIC-026`](../README.md)
**SPEC:** `SPEC-006` — reserved 🔵 in [`Docs/SPEC/README.md`](../../../../Docs/SPEC/README.md)
**Depends on:** None

---

## 1. Context and problem

`IOrderSubmission.cancel()` exists and is exercised by
`tests/unit/modules/trading/application/orders/test_cancel_order.py` and by the Dev Board's order
book; `CancelOrderCommandHandler` refuses on any venue but Testnet
(`src/modules/trading/application/orders/cancel_order/handler.py:93`). Yet `SPEC-006` is a reserved
row with no file. By the SPEC index's own rule a capability with no "Proven by" table is a plan,
and stage 3 will change this flow's venue gate — a change to a flow must update its SPEC in the
same pull request, which needs the SPEC to exist first.

## 2. Acceptance criteria

- [ ] `Docs/SPEC/SPEC-006_cancel_one_open_order.md` exists, follows `SPEC-000_template.md`, and is
      listed ✅ in the index's main table (the reserved row removed).
- [ ] Every named failure of the handler is a row in §5: venue disabled, trading off, connection
      not ready, order unknown to the exchange, already filled or cancelled, network failure.
- [ ] §6 states what the use case does not promise: it does not confirm the cancellation itself —
      the user data stream's order update is the truth, as `SPEC-005` §6 says of fills.
- [ ] §8 cites only test paths that exist, plus one **the user runs it** row (cancel on the Dev
      Board, confirm on the Testnet web UI). `tests/unit/architecture/test_spec_index_is_consistent.py`
      is green.
- [ ] If a named failure has no test, the test is added in this task (unit tier, from the interface
      per `testing-rule.md`), not deferred.

## 3. Design

The pattern is `SPEC-005`: trigger, preconditions naming the venue and the switch, the main flow
as the handler's actual steps in order, a failure table whose "why not a crash" column cites the
result type's members, and a "Proven by" table split by tier. The SPEC is written **from the
handler's code and tests**, not from memory: read `cancel_order/handler.py` and its result type
first, then `test_cancel_order.py`, and let a mismatch between them become a bug report rather
than prose that papers over it.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `Docs/SPEC/SPEC-006_cancel_one_open_order.md` | New, from the template |
| `Docs/SPEC/README.md` | Move `SPEC-006` from the reserved table to the main table as ✅ |
| `tests/unit/modules/trading/application/orders/test_cancel_order.py` | Only if a §5 row is uncovered: one test per uncovered row |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Index and file consistent | `.venv/bin/python -m pytest tests/unit/architecture/test_spec_index_is_consistent.py -q` | unit (guard) | green; red before the index row moves |
| Cited paths exist | same guard | unit (guard) | green |
| Failure rows covered | `.venv/bin/python -m pytest tests/unit/modules/trading/application/orders/test_cancel_order.py -q` | unit | green |
| Human row | the user cancels one order from the Dev Board and sees it gone on the Testnet web UI | human | recorded in this file's Implementation notes |
| Documentation guards | `python3 scripts/check_skill_prompt_references.py` | doc | clean |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
