# EPIC-035F — A key revoked mid-run is named, not mistaken for a switch-off

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M4 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 2 of [EPIC-035](../README.md).
**Risk:** 🟡 — after revocation the orders cannot be cancelled, so the user must be told at once
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** EPIC-035C

---

## 1. Context and problem
Audit M4: the next order after a revocation fails its connection check and is classed as a switch-off, so the bot goes HALTED without a cancel; nothing detects the revocation between orders. Cited: `src/modules/bots/application/services/bot_order_gateway.py:75-80`, `src/modules/bots/application/services/grid_task_guard.py:99-105`. Verify.

**Claim verified ✅ on `be67b47`, end to end, with two refinements.**
- `bot_order_gateway.py:75-80` is `SWITCH_OFF_GATES`, which holds `CONNECTION_NOT_READY`; `grid_task_guard.py:99-105` is `_orders_may_rest`, which excludes the `SWITCH_OFF` reason from parking. The link between them is in trading: the execute and cancel handlers turned *every* failed connection check, the `KEY_REJECTED` kind included, into `CONNECTION_NOT_READY` and dropped the kind. Reproduced on the composed app and the fake exchange (its key policy answers `-2015`) by making the new gate answer `CONNECTION_NOT_READY` again: the bot halts with `switch_off`, detail `L2 SELL: connection_not_ready`.
- Nothing probed the key: the only `check_connection()` call in the bots module is `holding()`, inside a stop.
- Refinement 1: a `-2015` that arrives on the order itself, not on the connection check, was a different wrong answer: the translator filed it `UNKNOWN`, the gateway made it a FAULT, and the bot went to ERROR, with the park then failing and only noting that its orders may still rest.
- Refinement 2: a cancel refused for the key during a Stop was `REFUSED`, so the stop waited and retried a rejection no retry can mend.

This task is specified briefly: it is Phase 2 — Infrastructure resilience. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [x] `-2015` / `-2008` (and a key-rejection class from the translator) map to a named reason `KEY_REJECTED`, distinct from `SWITCH_OFF`: the connection check's `KEY_REJECTED` kind became its own order gate (`ExecuteOrderSafetyGate.KEY_REJECTED`, via `connection_block`), the translator names `-2015`, `-2008` and `-2014` `OrderRejectionReason.KEY_REJECTED` (one code set, `KEY_REJECTED_CODES`, shared with the connection check), the gateway makes both an `OrderOutcomeKind.KEY_REJECTED`, and the bot records `GridReason.KEY_REJECTED`. Evidence: `test_a_connection_the_exchange_rejects_the_key_of_is_its_own_gate`, `test_a_rejected_key_is_its_own_gate`, the three translator rows (all red before), `test_a_rejected_key_halts_with_key_rejected_not_switch_off` and `test_a_key_rejected_on_the_order_itself_is_the_same_halt` (red: `order_refused`, and ERROR), and the integration journey `test_the_next_order_after_a_revocation_halts_with_key_rejected_not_switch_off` (mutated to the old behaviour it reads `switch_off`).
- [x] A rejected key HALTs the bot and says plainly that its orders may still rest and cannot be cancelled from this app: "…the exchange rejected the API key; orders of this bot may still rest on the exchange, and this app cannot cancel them until a working key is added", on the bot's state line. At Start it refuses the start; at Stop (a cancel or an exit slice) it halts instead of waiting. Evidence: the same tests plus `test_a_key_rejected_while_starting_refuses_the_start_by_name` and `test_a_stop_the_exchange_refuses_for_the_key_halts_by_name_instead_of_waiting` (red: STOPPING with a retry waiting).
- [x] The key is probed on a bounded interval while a bot holds orders, so a revocation is found between orders: `GridKeyProbe` asks the venue's connection check once per `KEY_PROBE_EVERY_SECONDS` (60 s) in the states that hold or lay orders, on the bot's own worker, and acts only on a *rejected key* (a network fault or a failed read changes nothing). Evidence: `test_the_key_is_probed_between_orders` (red: still RUNNING), `test_the_key_is_probed_on_a_bounded_interval_and_not_before`, `test_a_probe_that_cannot_reach_the_exchange_does_not_halt_the_bot`, `test_a_bot_at_rest_is_not_probed`, and the integration journey `test_a_revocation_is_found_between_orders_by_the_probe`.
- [ ] The alert goes through `EPIC-035K` once it exists: **waits for `EPIC-035K`.** Until then "alerted" is a named reason plus the plain statement on the bot's state line. There is **no notice bar in the Bots screen** (the bar the SPEC describes belongs to the Connect step and shows connect failures); the state line is the user-visible surface. A bar that shows a halt is `EPIC-035W`'s strip, not built here.

## 3. Design
Do not park on `KEY_REJECTED` (the park would fail); record the unmanaged-orders fact instead.

Done: `GridTaskGuard` skips the park for the reasons whose halt leaves the ladder where it is (`_CANNOT_CANCEL`: `SWITCH_OFF`, `KEY_REJECTED`), and the unmanaged-orders fact is the reason's detail. The probe is a collaborator (`grid_key_probe.py`), not a new executor method: the executor is over its public-surface limit, so it rides the price watch's existing beat, `GridExecutor.on_price_age_check`, which now posts the age check and the key probe as two tasks (docstring updated; the name is `EPIC-035A`'s and is left, because renaming it would touch `EPIC-035J`'s files). The probe keeps its own 60 s interval on the bot's monotonic clock, so the beat's cadence does not set the cost. `GridRunContext` gained the `monotonic` clock the probe measures it on.

**Scope left out:** the Futures account-control gate (`account_control_gate.py`) still answers `CONNECTION_NOT_READY` for a failed check; no bot reaches it.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/bot_order_gateway.py` | `KEY_REJECTED` outcome (gate and raised refusal, submit and cancel); `key_rejected()` |
| `src/modules/bots/application/services/grid_task_guard.py` | no park for a rejected key |
| `src/modules/bots/application/services/grid_key_probe.py` (new), `grid_executor.py`, `grid_run_context.py`, `grid_executor_factory.py` | the probe and its wiring |
| `src/modules/bots/application/services/{grid_order_failure,grid_stop_sequence,grid_resume_sequence}.py`, `domain/grid/grid_runtime.py` | the halt and its words; a stop and a resume that meet it |
| `src/modules/trading/application/orders/{connection_gate.py (new),execute_order/handler.py,cancel_order/handler.py}`, `contracts/execute_order_result.py` | the gate |
| `src/modules/trading/contracts/order_rejection_reason.py`, `adapters/binance/{binance_error_translator,connection_failure}.py` | the reason and the one set of codes |
| `src/modules/trading/ui/execute_order_block_reason.py`, `src/modules/strategy/cli/trade_once_formatter.py` | the new gate's words (their tables are exhaustive) |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | one row in §5, one in §8 |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Unit tier in `tests/unit/modules/bots/application/services/test_grid_key_rejected.py` (real executor on the simulated venue), the handler tests beside `test_execute_order_safety_gates.py` and `test_cancel_order.py`, the translator rows; integration tier in `tests/integration/modules/bots/test_a_revoked_key_on_the_fake_exchange.py` (composed app, fake exchange refusing the key with `-2015`). Eleven tests were observed red before the change (six bots, two handler, three translator rows); the two locks (`…cannot_reach_the_exchange…`, `…at_rest_is_not_probed`) held already. Green after: those, `tests/unit/modules/bots`, `tests/unit/modules/trading`, `tests/unit/architecture`, `tests/integration/modules/bots`.

## Implementation notes
- The translator's `-2015` / `-2008` / `-2014` rows are written from the same code set the connection check already uses, verified against the fake server's key policy, not against a live Binance answer (egress is blocked here).
- The probe costs one account read per minute per bot holding orders.

## Resume
Done, apart from the alert, which is `EPIC-035K`'s.
